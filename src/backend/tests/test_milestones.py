"""PostgreSQL-backed milestone persistence, authorization, and API tests."""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from app import security
from app.auth import get_db_session
from app.main import app
from app.models import Milestone, Team, TeamMembership, User
from app.supervisor_assignments import assign_supervisor
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_db_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _new_user(
    session: Session,
    role: str = "student",
    *,
    password: str | None = None,
) -> User:
    user = User(
        email=f"{role}.{uuid4().hex}@example.com",
        password_hash=(
            security.hash_password(password)
            if password is not None
            else "synthetic-test-only-hash"
        ),
        display_name=f"Synthetic {role.title()}",
        system_role=role,
    )
    session.add(user)
    session.flush()
    return user


def _new_team(session: Session, leader: User, name: str = "Synthetic Team") -> Team:
    team = Team(name=name)
    session.add(team)
    session.flush()
    session.add(TeamMembership(team_id=team.id, user_id=leader.id, role="leader"))
    session.flush()
    return team


def _headers(user: User) -> dict[str, str]:
    token = security.create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


def _new_milestone(
    session: Session,
    team: Team,
    name: str,
    due_at: datetime,
    *,
    id: UUID | None = None,
) -> Milestone:
    milestone = Milestone(
        id=id or uuid4(),
        team_id=team.id,
        name=name,
        due_at=due_at,
    )
    session.add(milestone)
    session.flush()
    return milestone


@pytest.mark.postgresql
def test_team_members_and_authorized_roles_receive_empty_milestone_lists(
    api_client: TestClient, db_session: Session
) -> None:
    leader = _new_user(db_session)
    member = _new_user(db_session)
    supervisor = _new_user(db_session, "supervisor")
    coordinator = _new_user(db_session, "coordinator")
    team = _new_team(db_session, leader)
    db_session.add(TeamMembership(team_id=team.id, user_id=member.id, role="member"))
    assign_supervisor(db_session, team.id, supervisor.id)

    unauthenticated = api_client.get(f"/teams/{team.id}/milestones")
    assert unauthenticated.status_code == 401

    for user in (leader, member, supervisor, coordinator):
        response = api_client.get(
            f"/teams/{team.id}/milestones", headers=_headers(user)
        )
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.postgresql
def test_milestone_list_sorts_by_due_time_then_uuid(
    api_client: TestClient, db_session: Session
) -> None:
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    later_due = datetime(2026, 12, 2, 15, tzinfo=timezone.utc)
    same_due = datetime(2026, 12, 1, 15, tzinfo=timezone.utc)
    _new_milestone(db_session, team, "Later", later_due, id=UUID(int=1))
    _new_milestone(db_session, team, "Tie second", same_due, id=UUID(int=3))
    _new_milestone(db_session, team, "Tie first", same_due, id=UUID(int=2))

    response = api_client.get(f"/teams/{team.id}/milestones", headers=_headers(student))

    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == [
        "Tie first",
        "Tie second",
        "Later",
    ]


@pytest.mark.postgresql
def test_coordinator_and_current_supervisor_can_create_and_edit_milestones(
    api_client: TestClient, db_session: Session
) -> None:
    student = _new_user(db_session)
    supervisor = _new_user(db_session, "supervisor")
    coordinator = _new_user(db_session, "coordinator")
    team = _new_team(db_session, student)
    assign_supervisor(db_session, team.id, supervisor.id)

    coordinator_create = api_client.post(
        f"/teams/{team.id}/milestones",
        headers=_headers(coordinator),
        json={
            "name": "  Proposal  ",
            "description": "Initial proposal.",
            "due_at": "2026-12-01T17:00:00+02:00",
        },
    )
    assert coordinator_create.status_code == 201
    coordinator_body = coordinator_create.json()
    assert coordinator_body["name"] == "Proposal"
    assert coordinator_body["deadline_status"] in {
        "scheduled",
        "due_soon",
        "overdue",
    }
    assert datetime.fromisoformat(
        coordinator_body["due_at"].replace("Z", "+00:00")
    ) == datetime(2026, 12, 1, 15, tzinfo=timezone.utc)
    for timestamp in (coordinator_body["created_at"], coordinator_body["updated_at"]):
        assert datetime.fromisoformat(timestamp.replace("Z", "+00:00")).utcoffset() == (
            timedelta(0)
        )
    normalized_milestone = db_session.get(Milestone, UUID(coordinator_body["id"]))
    assert normalized_milestone is not None
    assert normalized_milestone.due_at == datetime(2026, 12, 1, 15, tzinfo=timezone.utc)

    coordinator_due = datetime.now(timezone.utc) - timedelta(hours=1)
    coordinator_update = api_client.patch(
        f"/teams/{team.id}/milestones/{coordinator_body['id']}",
        headers=_headers(coordinator),
        json={"due_at": coordinator_due.isoformat()},
    )
    assert coordinator_update.status_code == 200
    assert coordinator_update.json()["deadline_status"] == "overdue"

    supervisor_create = api_client.post(
        f"/teams/{team.id}/milestones",
        headers=_headers(supervisor),
        json={"name": "SRS", "due_at": "2026-12-10T15:00:00Z"},
    )
    assert supervisor_create.status_code == 201

    changed_due = datetime.now(timezone.utc) - timedelta(days=1)
    deadline_update = api_client.patch(
        f"/teams/{team.id}/milestones/{supervisor_create.json()['id']}",
        headers=_headers(supervisor),
        json={"due_at": changed_due.isoformat()},
    )

    assert deadline_update.status_code == 200
    assert deadline_update.json()["deadline_status"] == "overdue"
    assert (
        datetime.fromisoformat(deadline_update.json()["due_at"].replace("Z", "+00:00"))
        == changed_due
    )
    persisted = db_session.get(Milestone, UUID(supervisor_create.json()["id"]))
    assert persisted is not None
    assert persisted.due_at == changed_due
    assert persisted.due_at.utcoffset() == timedelta(0)


@pytest.mark.postgresql
def test_cross_phase_auth_team_and_milestone_flow_enforces_current_scope(
    api_client: TestClient, db_session: Session
) -> None:
    student_password = "synthetic-student-password"
    student_email = f"{uuid4().hex}@example.com"
    registration = api_client.post(
        "/auth/register",
        json={
            "email": student_email,
            "display_name": "Synthetic Team Leader",
            "password": student_password,
        },
    )
    assert registration.status_code == 201
    student_login = api_client.post(
        "/auth/login",
        json={"email": student_email, "password": student_password},
    )
    assert student_login.status_code == 200
    student_headers = {
        "Authorization": f"Bearer {student_login.json()['access_token']}"
    }

    team_response = api_client.post(
        "/teams", headers=student_headers, json={"name": "Synthetic Milestone Team"}
    )
    assert team_response.status_code == 201
    team_id = team_response.json()["id"]

    member_password = "synthetic-member-password"
    member_email = f"{uuid4().hex}@example.com"
    member_registration = api_client.post(
        "/auth/register",
        json={
            "email": member_email,
            "display_name": "Synthetic Team Member",
            "password": member_password,
        },
    )
    assert member_registration.status_code == 201
    member_login = api_client.post(
        "/auth/login",
        json={"email": member_email, "password": member_password},
    )
    assert member_login.status_code == 200
    member_headers = {"Authorization": f"Bearer {member_login.json()['access_token']}"}
    added_member = api_client.post(
        f"/teams/{team_id}/members",
        headers=student_headers,
        json={"user_id": member_registration.json()["id"]},
    )
    assert added_member.status_code == 201

    coordinator_password = "synthetic-coordinator-password"
    coordinator = _new_user(db_session, "coordinator", password=coordinator_password)
    supervisor_password = "synthetic-supervisor-password"
    supervisor = _new_user(db_session, "supervisor", password=supervisor_password)
    replacement_password = "synthetic-replacement-password"
    replacement_supervisor = _new_user(
        db_session, "supervisor", password=replacement_password
    )
    unassigned_supervisor = _new_user(db_session, "supervisor")

    coordinator_login = api_client.post(
        "/auth/login",
        json={"email": coordinator.email, "password": coordinator_password},
    )
    supervisor_login = api_client.post(
        "/auth/login",
        json={"email": supervisor.email, "password": supervisor_password},
    )
    replacement_login = api_client.post(
        "/auth/login",
        json={
            "email": replacement_supervisor.email,
            "password": replacement_password,
        },
    )
    assert coordinator_login.status_code == supervisor_login.status_code == 200
    assert replacement_login.status_code == 200
    coordinator_headers = {
        "Authorization": f"Bearer {coordinator_login.json()['access_token']}"
    }
    supervisor_headers = {
        "Authorization": f"Bearer {supervisor_login.json()['access_token']}"
    }
    replacement_headers = {
        "Authorization": f"Bearer {replacement_login.json()['access_token']}"
    }

    assignment = api_client.put(
        f"/teams/{team_id}/supervisor",
        headers=coordinator_headers,
        json={"supervisor_id": str(supervisor.id)},
    )
    assert assignment.status_code == 200

    base_time = datetime.now(timezone.utc)
    proposal = api_client.post(
        f"/teams/{team_id}/milestones",
        headers=supervisor_headers,
        json={
            "name": "Proposal",
            "due_at": (base_time + timedelta(days=20)).isoformat(),
        },
    )
    srs = api_client.post(
        f"/teams/{team_id}/milestones",
        headers=supervisor_headers,
        json={
            "name": "SRS",
            "due_at": (base_time + timedelta(days=10)).isoformat(),
        },
    )
    assert proposal.status_code == srs.status_code == 201

    student_list = api_client.get(
        f"/teams/{team_id}/milestones", headers=student_headers
    )
    member_list = api_client.get(f"/teams/{team_id}/milestones", headers=member_headers)
    assert student_list.status_code == 200
    assert member_list.status_code == 200
    assert [item["name"] for item in student_list.json()] == ["SRS", "Proposal"]
    assert [item["id"] for item in member_list.json()] == [
        item["id"] for item in student_list.json()
    ]
    assert all("deadline_status" in item for item in student_list.json())

    forbidden_create = api_client.post(
        f"/teams/{team_id}/milestones",
        headers=student_headers,
        json={"name": "Student-created", "due_at": base_time.isoformat()},
    )
    forbidden_member_create = api_client.post(
        f"/teams/{team_id}/milestones",
        headers=member_headers,
        json={"name": "Member-created", "due_at": base_time.isoformat()},
    )
    forbidden_update = api_client.patch(
        f"/teams/{team_id}/milestones/{srs.json()['id']}",
        headers=student_headers,
        json={"due_at": (base_time + timedelta(days=5)).isoformat()},
    )
    assert forbidden_create.status_code == forbidden_update.status_code == 403
    assert forbidden_member_create.status_code == 403

    changed_due = base_time + timedelta(days=3)
    updated = api_client.patch(
        f"/teams/{team_id}/milestones/{srs.json()['id']}",
        headers=supervisor_headers,
        json={"due_at": changed_due.isoformat()},
    )
    student_after_update = api_client.get(
        f"/teams/{team_id}/milestones", headers=student_headers
    )
    member_after_update = api_client.get(
        f"/teams/{team_id}/milestones", headers=member_headers
    )
    assert updated.status_code == 200
    assert student_after_update.json()[0]["due_at"] == updated.json()["due_at"]
    assert student_after_update.json()[0]["deadline_status"] == "due_soon"
    assert member_after_update.json()[0]["due_at"] == updated.json()["due_at"]

    unassigned_read = api_client.get(
        f"/teams/{team_id}/milestones", headers=_headers(unassigned_supervisor)
    )
    unassigned_create = api_client.post(
        f"/teams/{team_id}/milestones",
        headers=_headers(unassigned_supervisor),
        json={"name": "Unassigned Proposal", "due_at": base_time.isoformat()},
    )
    unassigned_update = api_client.patch(
        f"/teams/{team_id}/milestones/{srs.json()['id']}",
        headers=_headers(unassigned_supervisor),
        json={"due_at": base_time.isoformat()},
    )
    reassignment = api_client.put(
        f"/teams/{team_id}/supervisor",
        headers=coordinator_headers,
        json={"supervisor_id": str(replacement_supervisor.id)},
    )
    former_supervisor_read = api_client.get(
        f"/teams/{team_id}/milestones", headers=supervisor_headers
    )
    replacement_read = api_client.get(
        f"/teams/{team_id}/milestones", headers=replacement_headers
    )
    assert unassigned_read.status_code == 404
    assert unassigned_create.status_code == unassigned_update.status_code == 404
    assert reassignment.status_code == 200
    assert former_supervisor_read.status_code == 404
    assert replacement_read.status_code == 200
    assert len(replacement_read.json()) == 2

    other_student = _new_user(db_session)
    other_team = _new_team(db_session, other_student, "Synthetic Other Team")
    other_team_read = api_client.get(
        f"/teams/{team_id}/milestones", headers=_headers(other_student)
    )
    mismatched_detail = api_client.get(
        f"/teams/{other_team.id}/milestones/{srs.json()['id']}",
        headers=_headers(other_student),
    )
    assert other_team_read.status_code == 404
    assert mismatched_detail.status_code == 404


@pytest.mark.postgresql
def test_invalid_or_scope_overriding_requests_do_not_change_saved_data(
    api_client: TestClient, db_session: Session
) -> None:
    coordinator = _new_user(db_session, "coordinator")
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    create_with_owner_override = api_client.post(
        f"/teams/{team.id}/milestones",
        headers=_headers(coordinator),
        json={
            "name": "Proposal",
            "due_at": "2026-12-01T15:00:00Z",
            "team_id": str(uuid4()),
            "system_role": "coordinator",
        },
    )
    create_with_naive_deadline = api_client.post(
        f"/teams/{team.id}/milestones",
        headers=_headers(coordinator),
        json={"name": "Proposal", "due_at": "2026-12-01T15:00:00"},
    )
    assert create_with_owner_override.status_code == 422
    assert create_with_naive_deadline.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(Milestone)) == 0

    created = api_client.post(
        f"/teams/{team.id}/milestones",
        headers=_headers(coordinator),
        json={"name": "Proposal", "due_at": "2026-12-01T15:00:00Z"},
    )
    assert created.status_code == 201
    original_due_at = created.json()["due_at"]

    invalid_update = api_client.patch(
        f"/teams/{team.id}/milestones/{created.json()['id']}",
        headers=_headers(coordinator),
        json={"due_at": "2026-12-02T15:00:00Z", "team_id": str(uuid4())},
    )
    missing_milestone = api_client.patch(
        f"/teams/{team.id}/milestones/{uuid4()}",
        headers=_headers(coordinator),
        json={"due_at": "2026-12-02T15:00:00Z"},
    )
    unknown_detail = api_client.get(
        f"/teams/{team.id}/milestones/{uuid4()}",
        headers=_headers(coordinator),
    )
    assert invalid_update.status_code == 422
    assert missing_milestone.status_code == 404
    assert unknown_detail.status_code == 404
    assert db_session.get(Milestone, UUID(created.json()["id"])).due_at.isoformat() == (
        datetime.fromisoformat(original_due_at.replace("Z", "+00:00")).isoformat()
    )
    assert db_session.scalar(select(func.count()).select_from(Milestone)) == 1


@pytest.mark.postgresql
def test_database_enforces_milestone_team_deadline_name_and_length(
    db_session: Session,
) -> None:
    due_at = datetime.now(timezone.utc)
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    db_session.commit()

    blank_name = Milestone(team_id=team.id, name=" ", due_at=due_at)
    db_session.add(blank_name)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    oversized_name = Milestone(
        team_id=team.id,
        name="x" * 201,
        due_at=due_at,
    )
    db_session.add(oversized_name)
    with pytest.raises(DataError):
        db_session.flush()
    db_session.rollback()

    missing_deadline = Milestone(team_id=team.id, name="Proposal", due_at=None)
    db_session.add(missing_deadline)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    missing_team = Milestone(team_id=uuid4(), name="Proposal", due_at=due_at)
    db_session.add(missing_team)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    untrimmed_name = Milestone(team_id=team.id, name=" Proposal ", due_at=due_at)
    db_session.add(untrimmed_name)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@pytest.mark.postgresql
def test_milestone_creation_rolls_back_when_database_rejects_insert(
    api_client: TestClient, db_session: Session
) -> None:
    coordinator = _new_user(db_session, "coordinator")
    student = _new_user(db_session)
    team = _new_team(db_session, student)

    def invalidate_milestone_name(mapper, connection, milestone) -> None:
        milestone.name = " "

    event.listen(Milestone, "before_insert", invalidate_milestone_name)
    try:
        response = api_client.post(
            f"/teams/{team.id}/milestones",
            headers=_headers(coordinator),
            json={"name": "Proposal", "due_at": "2026-12-01T15:00:00Z"},
        )
    finally:
        event.remove(Milestone, "before_insert", invalidate_milestone_name)

    assert response.status_code == 409
    assert db_session.scalar(select(func.count()).select_from(Milestone)) == 0
