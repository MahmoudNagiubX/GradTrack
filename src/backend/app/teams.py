"""Team management with team-scoped membership and assignment checks."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    CurrentUser,
    require_system_roles,
    require_team_leader,
    stream_avatar,
)
from app.config import Settings
from app.database import get_db_session
from app.models import SupervisorAssignment, Team, TeamMembership, User
from app.schemas import (
    SupervisorAssignmentRequest,
    SupervisorAssignmentResponse,
    TeamCreateRequest,
    TeamMemberAddRequest,
    TeamMemberProfileResponse,
    TeamMemberResponse,
    TeamResponse,
)
from app.supervisor_assignments import assign_supervisor

router = APIRouter(prefix="/teams", tags=["teams"])

DbSession = Annotated[Session, Depends(get_db_session)]
Student = Annotated[User, Depends(require_system_roles("student"))]
Coordinator = Annotated[User, Depends(require_system_roles("coordinator"))]
TeamLeaderMembership = Annotated[TeamMembership, Depends(require_team_leader())]


def _serialize_teams(teams: list[Team], session: Session) -> list[TeamResponse]:
    """Build team responses using batched membership and assignment queries."""
    if not teams:
        return []

    team_ids = [team.id for team in teams]
    member_rows = session.execute(
        select(
            TeamMembership.team_id,
            TeamMembership.user_id,
            User.display_name,
            TeamMembership.role,
            User.avatar_storage_key,
        )
        .join(User, User.id == TeamMembership.user_id)
        .where(TeamMembership.team_id.in_(team_ids))
        .order_by(
            TeamMembership.team_id,
            TeamMembership.joined_at,
            TeamMembership.user_id,
        )
    ).all()
    assignment_rows = session.execute(
        select(SupervisorAssignment.team_id, SupervisorAssignment.supervisor_id).where(
            SupervisorAssignment.team_id.in_(team_ids)
        )
    ).all()

    members_by_team: dict[UUID, list[TeamMemberResponse]] = {
        team_id: [] for team_id in team_ids
    }
    for team_id, user_id, display_name, role, avatar_storage_key in member_rows:
        members_by_team[team_id].append(
            TeamMemberResponse(
                user_id=user_id,
                display_name=display_name,
                role=role,
                has_avatar=bool(avatar_storage_key),
            )
        )

    supervisors_by_team = {
        team_id: supervisor_id for team_id, supervisor_id in assignment_rows
    }
    return [
        TeamResponse(
            id=team.id,
            name=team.name,
            created_at=team.created_at,
            supervisor_id=supervisors_by_team.get(team.id),
            members=members_by_team[team.id],
        )
        for team in teams
    ]


def get_visible_team(team_id: UUID, current_user: User, session: Session) -> Team:
    """Return the team only to members, its current supervisor, or a coordinator."""
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    if current_user.system_role == "coordinator":
        # Coordinator scope is temporarily global for the single-programme pilot.
        return team

    if current_user.system_role == "supervisor":
        assignment = session.get(SupervisorAssignment, team_id)
        if assignment is not None and assignment.supervisor_id == current_user.id:
            return team
    elif (
        session.scalar(
            select(TeamMembership.id).where(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == current_user.id,
            )
        )
        is not None
    ):
        return team

    # Avoid exposing whether a team exists to an unauthorized account.
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Team not found",
    )


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreateRequest, student: Student, session: DbSession
) -> TeamResponse:
    """Create a team and its first leader membership in one transaction."""
    team = Team(name=payload.name)
    session.add(team)
    try:
        session.flush()
        session.add(TeamMembership(team_id=team.id, user_id=student.id, role="leader"))
        session.commit()
        session.refresh(team)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Team could not be created",
        ) from None

    return _serialize_teams([team], session)[0]


@router.get("", response_model=list[TeamResponse])
def list_teams(current_user: CurrentUser, session: DbSession) -> list[TeamResponse]:
    """List only teams accessible to this account's system role."""
    query = select(Team)
    if current_user.system_role == "student":
        query = query.join(TeamMembership, TeamMembership.team_id == Team.id).where(
            TeamMembership.user_id == current_user.id
        )
    elif current_user.system_role == "supervisor":
        query = query.join(
            SupervisorAssignment, SupervisorAssignment.team_id == Team.id
        ).where(SupervisorAssignment.supervisor_id == current_user.id)
    elif current_user.system_role != "coordinator":
        return []

    teams = list(session.scalars(query.order_by(Team.created_at, Team.id)).all())
    return _serialize_teams(teams, session)


@router.get("/{team_id}", response_model=TeamResponse)
def read_team(
    team_id: UUID, current_user: CurrentUser, session: DbSession
) -> TeamResponse:
    """Read one team only when membership, assignment, or coordinator scope permits."""
    team = get_visible_team(team_id, current_user, session)
    return _serialize_teams([team], session)[0]


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_team_member(
    team_id: UUID,
    payload: TeamMemberAddRequest,
    student_leader: Student,
    leader_membership: TeamLeaderMembership,
    session: DbSession,
) -> TeamMemberResponse:
    """Add an existing active student as a regular member of this team."""
    if (
        leader_membership.team_id != team_id
        or leader_membership.user_id != student_leader.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this resource",
        )

    user = session.get(User, payload.user_id)
    if user is None or not user.is_active or user.system_role != "student":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active student account not found",
        )

    membership = TeamMembership(
        team_id=team_id,
        user_id=user.id,
        role="member",
    )
    session.add(membership)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The account is already a team member",
        ) from None

    return TeamMemberResponse(
        user_id=user.id,
        display_name=user.display_name,
        role="member",
        has_avatar=user.has_avatar,
    )


@router.put(
    "/{team_id}/supervisor",
    response_model=SupervisorAssignmentResponse,
)
def assign_or_reassign_supervisor(
    team_id: UUID,
    payload: SupervisorAssignmentRequest,
    _coordinator: Coordinator,
    session: DbSession,
) -> SupervisorAssignment:
    """Set the team's current supervisor; coordinator scope is global in this pilot."""
    if session.get(Team, team_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    supervisor = session.get(User, payload.supervisor_id)
    if supervisor is None or not supervisor.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Selected account must be an active supervisor",
        )

    try:
        assignment = assign_supervisor(session, team_id, supervisor.id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Selected account must be an active supervisor",
        ) from None

    try:
        session.commit()
        session.refresh(assignment)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Supervisor assignment could not be saved",
        ) from None

    return assignment


@router.get(
    "/{team_id}/members/{user_id}/profile",
    response_model=TeamMemberProfileResponse,
)
def read_team_member_profile(
    team_id: UUID,
    user_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> TeamMemberProfileResponse:
    """Read a teammate's non-sensitive profile within an authorized team space."""
    get_visible_team(team_id, current_user, session)

    membership = session.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    return TeamMemberProfileResponse(
        id=user.id,
        display_name=user.display_name,
        team_role=membership.role,
        faculty=user.faculty,
        department=user.department,
        academic_level=user.academic_level,
        bio=user.bio,
        has_avatar=user.has_avatar,
    )


@router.get(
    "/{team_id}/members/{user_id}/avatar",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {
                "image/png": {},
                "image/jpeg": {},
            },
            "description": "The team member's profile avatar.",
        },
        404: {"description": "Avatar not found"},
        503: {"description": "Avatar file is unavailable"},
    },
)
def read_team_member_avatar(
    team_id: UUID,
    user_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> StreamingResponse:
    """Stream an authorized team member's profile avatar."""
    get_visible_team(team_id, current_user, session)

    membership = session.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team member not found",
        )

    user = session.get(User, user_id)
    if user is None or not user.is_active or not user.avatar_storage_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar not found",
        )

    return stream_avatar(
        user.avatar_storage_key,
        Settings.from_environment().private_upload_dir,
    )
