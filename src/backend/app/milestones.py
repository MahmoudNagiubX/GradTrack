"""Team-scoped milestone reads and deadline management."""

from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.database import get_db_session
from app.models import Milestone, Team, User
from app.schemas import (
    MilestoneCreateRequest,
    MilestoneResponse,
    MilestoneUpdateRequest,
)
from app.teams import get_visible_team

router = APIRouter(prefix="/teams/{team_id}/milestones", tags=["milestones"])

DbSession = Annotated[Session, Depends(get_db_session)]
DeadlineStatus = Literal["scheduled", "due_soon", "overdue"]


def deadline_status(
    due_at: datetime,
    *,
    now: datetime | None = None,
) -> DeadlineStatus:
    """Derive planning status from UTC instants without persisting the result."""
    deadline = _as_utc(due_at)
    current_time = _as_utc(now or datetime.now(timezone.utc))

    if current_time > deadline:
        return "overdue"
    if deadline - current_time > timedelta(days=7):
        return "scheduled"
    return "due_soon"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _serialize_milestone(
    milestone: Milestone,
    *,
    now: datetime | None = None,
) -> MilestoneResponse:
    """Return UTC timestamps and the current derived deadline state."""
    return MilestoneResponse(
        id=milestone.id,
        team_id=milestone.team_id,
        name=milestone.name,
        description=milestone.description,
        due_at=_as_utc(milestone.due_at),
        deadline_status=deadline_status(milestone.due_at, now=now),
        created_at=_as_utc(milestone.created_at),
        updated_at=_as_utc(milestone.updated_at),
    )


def _require_milestone_writer(
    team_id: UUID,
    current_user: User,
    session: Session,
) -> Team:
    """Permit coordinators and the team's currently assigned supervisor only."""
    team = get_visible_team(team_id, current_user, session)
    if current_user.system_role in {"coordinator", "supervisor"}:
        return team

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized for this resource",
    )


def _milestone_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Milestone not found",
    )


@router.get("", response_model=list[MilestoneResponse])
def list_team_milestones(
    team_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> list[MilestoneResponse]:
    """List milestones for one authorized team in stable deadline order."""
    get_visible_team(team_id, current_user, session)
    milestones = session.scalars(
        select(Milestone)
        .where(Milestone.team_id == team_id)
        .order_by(Milestone.due_at.asc(), Milestone.id.asc())
    ).all()
    current_time = datetime.now(timezone.utc)
    return [
        _serialize_milestone(milestone, now=current_time) for milestone in milestones
    ]


@router.get("/{milestone_id}", response_model=MilestoneResponse)
def read_team_milestone(
    team_id: UUID,
    milestone_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> MilestoneResponse:
    """Read a milestone only through its authorized owning team."""
    get_visible_team(team_id, current_user, session)
    milestone = session.scalar(
        select(Milestone).where(
            Milestone.id == milestone_id,
            Milestone.team_id == team_id,
        )
    )
    if milestone is None:
        raise _milestone_not_found()
    return _serialize_milestone(milestone)


@router.post(
    "",
    response_model=MilestoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_team_milestone(
    team_id: UUID,
    payload: MilestoneCreateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> MilestoneResponse:
    """Create a team-owned milestone for a coordinator or assigned supervisor."""
    team = _require_milestone_writer(team_id, current_user, session)
    milestone = Milestone(
        team_id=team.id,
        name=payload.name,
        description=payload.description,
        due_at=payload.due_at,
    )
    session.add(milestone)
    try:
        session.commit()
        session.refresh(milestone)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Milestone could not be created",
        ) from None
    return _serialize_milestone(milestone)


@router.patch("/{milestone_id}", response_model=MilestoneResponse)
def update_team_milestone_deadline(
    team_id: UUID,
    milestone_id: UUID,
    payload: MilestoneUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> MilestoneResponse:
    """Change only a milestone deadline within the authorized owning team."""
    _require_milestone_writer(team_id, current_user, session)
    milestone = session.scalar(
        select(Milestone).where(
            Milestone.id == milestone_id,
            Milestone.team_id == team_id,
        )
    )
    if milestone is None:
        raise _milestone_not_found()

    milestone.due_at = payload.due_at
    try:
        session.commit()
        session.refresh(milestone)
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Milestone deadline could not be saved",
        ) from None
    return _serialize_milestone(milestone)
