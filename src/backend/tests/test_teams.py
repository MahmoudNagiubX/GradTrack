"""PostgreSQL-backed integration tests for team management and isolation."""

from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from app import security
from app.auth import get_db_session
from app.main import app
from app.models import SupervisorAssignment, Team, TeamMembership, User
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgresql


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


def _new_user(db_session: Session, role: str = "student") -> User:
    user = User(
        email=f"{role}.{uuid4().hex}@example.com",
        password_hash="synthetic-test-only-hash",
        display_name=f"Synthetic {role.title()}",
        system_role=role,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _headers(user: User) -> dict[str, str]:
    token = security.create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


def _create_team(
    api_client: TestClient, user: User, name: str = "Synthetic Team"
) -> str:
    response = api_client.post("/teams", headers=_headers(user), json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_student_creates_team_and_becomes_its_first_leader(
    api_client: TestClient, db_session: Session
) -> None:
    student = _new_user(db_session)

    response = api_client.post(
        "/teams",
        headers=_headers(student),
        json={"name": "  Synthetic Capstone Team  "},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Synthetic Capstone Team"
    assert body["supervisor_id"] is None
    assert body["members"] == [
        {
            "user_id": str(student.id),
            "display_name": student.display_name,
            "role": "leader",
            "has_avatar": False,
        }
    ]
    team_id = UUID(body["id"])
    persisted_team = db_session.get(Team, team_id)
    persisted_membership = db_session.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == student.id,
        )
    )
    assert persisted_team is not None
    assert persisted_membership is not None
    assert persisted_membership.role == "leader"


@pytest.mark.parametrize("system_role", ("supervisor", "coordinator"))
def test_only_students_can_create_teams(
    api_client: TestClient, db_session: Session, system_role: str
) -> None:
    account = _new_user(db_session, system_role)

    response = api_client.post(
        "/teams", headers=_headers(account), json={"name": "Forbidden Team"}
    )

    assert response.status_code == 403
    assert db_session.scalar(select(func.count()).select_from(Team)) == 0


@pytest.mark.parametrize("name", ("", "   "))
def test_team_creation_rejects_empty_name(
    api_client: TestClient, db_session: Session, name: str
) -> None:
    student = _new_user(db_session)

    response = api_client.post("/teams", headers=_headers(student), json={"name": name})

    assert response.status_code == 422


def test_team_creation_does_not_accept_client_selected_privileged_fields(
    api_client: TestClient, db_session: Session
) -> None:
    student = _new_user(db_session)

    response = api_client.post(
        "/teams",
        headers=_headers(student),
        json={"name": "Synthetic Team", "system_role": "coordinator"},
    )

    assert response.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(Team)) == 0


def test_team_creation_rolls_back_team_when_leader_membership_insert_fails(
    api_client: TestClient, db_session: Session
) -> None:
    student = _new_user(db_session)

    def invalidate_membership_role(mapper, connection, membership) -> None:
        membership.role = "invalid"

    event.listen(TeamMembership, "before_insert", invalidate_membership_role)
    try:
        response = api_client.post(
            "/teams", headers=_headers(student), json={"name": "Atomic Team"}
        )
    finally:
        event.remove(TeamMembership, "before_insert", invalidate_membership_role)

    assert response.status_code == 409
    assert db_session.scalar(select(func.count()).select_from(Team)) == 0
    assert db_session.scalar(select(func.count()).select_from(TeamMembership)) == 0


def test_team_leader_adds_existing_student_as_member_and_duplicate_is_rejected(
    api_client: TestClient, db_session: Session
) -> None:
    leader = _new_user(db_session)
    new_member = _new_user(db_session)
    team_id = _create_team(api_client, leader)

    response = api_client.post(
        f"/teams/{team_id}/members",
        headers=_headers(leader),
        json={"user_id": str(new_member.id)},
    )
    duplicate = api_client.post(
        f"/teams/{team_id}/members",
        headers=_headers(leader),
        json={"user_id": str(new_member.id)},
    )

    assert response.status_code == 201
    assert response.json() == {
        "user_id": str(new_member.id),
        "display_name": new_member.display_name,
        "role": "member",
        "has_avatar": False,
    }
    assert duplicate.status_code == 409
    persisted = db_session.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == UUID(team_id),
            TeamMembership.user_id == new_member.id,
        )
    )
    assert persisted is not None
    assert persisted.role == "member"


def test_team_leader_cannot_choose_a_new_member_role(
    api_client: TestClient, db_session: Session
) -> None:
    leader = _new_user(db_session)
    new_member = _new_user(db_session)
    team_id = UUID(_create_team(api_client, leader))

    response = api_client.post(
        f"/teams/{team_id}/members",
        headers=_headers(leader),
        json={"user_id": str(new_member.id), "role": "leader"},
    )

    assert response.status_code == 422
    assert (
        db_session.scalar(
            select(TeamMembership).where(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == new_member.id,
            )
        )
        is None
    )


@pytest.mark.parametrize("target_kind", ("missing", "supervisor", "inactive"))
def test_team_leader_can_add_only_an_active_student(
    api_client: TestClient, db_session: Session, target_kind: str
) -> None:
    leader = _new_user(db_session)
    team_id = _create_team(api_client, leader)
    if target_kind == "missing":
        target_id = uuid4()
    elif target_kind == "supervisor":
        target_id = _new_user(db_session, "supervisor").id
    else:
        inactive_student = _new_user(db_session)
        inactive_student.is_active = False
        db_session.flush()
        target_id = inactive_student.id

    response = api_client.post(
        f"/teams/{team_id}/members",
        headers=_headers(leader),
        json={"user_id": str(target_id)},
    )

    assert response.status_code == 404


def test_member_and_other_team_leader_cannot_modify_team_membership(
    api_client: TestClient, db_session: Session
) -> None:
    leader_a = _new_user(db_session)
    leader_b = _new_user(db_session)
    member = _new_user(db_session)
    team_a = UUID(_create_team(api_client, leader_a, "Team A"))
    team_b = UUID(_create_team(api_client, leader_b, "Team B"))
    db_session.add(TeamMembership(team_id=team_a, user_id=member.id, role="member"))
    db_session.flush()

    member_attempt = api_client.post(
        f"/teams/{team_a}/members",
        headers=_headers(member),
        json={"user_id": str(_new_user(db_session).id)},
    )
    cross_team_attempt = api_client.post(
        f"/teams/{team_b}/members",
        headers=_headers(leader_a),
        json={"user_id": str(member.id)},
    )

    assert member_attempt.status_code == 403
    assert cross_team_attempt.status_code == 403


def test_team_listing_and_reading_are_scoped_by_membership_assignment_and_role(
    api_client: TestClient, db_session: Session
) -> None:
    student_a = _new_user(db_session)
    student_b = _new_user(db_session)
    assigned_supervisor = _new_user(db_session, "supervisor")
    other_supervisor = _new_user(db_session, "supervisor")
    coordinator = _new_user(db_session, "coordinator")
    team_a = UUID(_create_team(api_client, student_a, "Team A"))
    team_b = UUID(_create_team(api_client, student_b, "Team B"))
    unassigned_team = Team(name="Unassigned Team")
    db_session.add(unassigned_team)
    db_session.flush()
    db_session.add_all(
        [
            SupervisorAssignment(team_id=team_a, supervisor_id=assigned_supervisor.id),
            SupervisorAssignment(team_id=team_b, supervisor_id=other_supervisor.id),
        ]
    )
    db_session.flush()

    student_list = api_client.get("/teams", headers=_headers(student_a))
    supervisor_list = api_client.get("/teams", headers=_headers(assigned_supervisor))
    coordinator_list = api_client.get("/teams", headers=_headers(coordinator))
    student_own_read = api_client.get(f"/teams/{team_a}", headers=_headers(student_a))
    student_foreign_read = api_client.get(
        f"/teams/{team_b}", headers=_headers(student_a)
    )
    wrong_supervisor_read = api_client.get(
        f"/teams/{team_b}", headers=_headers(assigned_supervisor)
    )
    assigned_supervisor_read = api_client.get(
        f"/teams/{team_a}", headers=_headers(assigned_supervisor)
    )
    unassigned_supervisor_read = api_client.get(
        f"/teams/{unassigned_team.id}", headers=_headers(assigned_supervisor)
    )
    coordinator_unassigned_read = api_client.get(
        f"/teams/{unassigned_team.id}", headers=_headers(coordinator)
    )

    assert [item["id"] for item in student_list.json()] == [str(team_a)]
    assert [item["id"] for item in supervisor_list.json()] == [str(team_a)]
    assert {item["id"] for item in coordinator_list.json()} == {
        str(team_a),
        str(team_b),
        str(unassigned_team.id),
    }
    assert student_own_read.status_code == 200
    assert student_foreign_read.status_code == 404
    assert wrong_supervisor_read.status_code == 404
    assert assigned_supervisor_read.status_code == 200
    assert unassigned_supervisor_read.status_code == 404
    assert coordinator_unassigned_read.status_code == 200


@pytest.mark.parametrize(
    ("actor_kind", "operation"),
    [
        ("student", "assign"),
        ("student", "reassign"),
        ("team_leader", "assign"),
        ("team_leader", "reassign"),
        ("supervisor", "assign"),
        ("supervisor", "reassign"),
    ],
)
def test_only_coordinator_can_assign_or_reassign_supervisor(
    api_client: TestClient,
    db_session: Session,
    actor_kind: str,
    operation: str,
) -> None:
    team = Team(name="Assignment Boundary Team")
    actor = _new_user(
        db_session, "supervisor" if actor_kind == "supervisor" else "student"
    )
    selected_supervisor = _new_user(db_session, "supervisor")
    db_session.add(team)
    db_session.flush()
    if actor_kind == "team_leader":
        db_session.add(TeamMembership(team_id=team.id, user_id=actor.id, role="leader"))
    current_supervisor_id = None
    if operation == "reassign":
        current_supervisor = _new_user(db_session, "supervisor")
        current_supervisor_id = current_supervisor.id
        db_session.add(
            SupervisorAssignment(team_id=team.id, supervisor_id=current_supervisor.id)
        )
        db_session.flush()

    response = api_client.put(
        f"/teams/{team.id}/supervisor",
        headers=_headers(actor),
        json={"supervisor_id": str(selected_supervisor.id)},
    )

    assert response.status_code == 403
    assignment = db_session.get(SupervisorAssignment, team.id)
    if operation == "assign":
        assert assignment is None
    else:
        assert assignment is not None
        assert assignment.supervisor_id == current_supervisor_id


def test_coordinator_can_assign_and_reassign_only_to_a_supervisor(
    api_client: TestClient, db_session: Session
) -> None:
    coordinator = _new_user(db_session, "coordinator")
    team = Team(name="Coordinator Assignment Team")
    first_supervisor = _new_user(db_session, "supervisor")
    next_supervisor = _new_user(db_session, "supervisor")
    invalid_target = _new_user(db_session)
    db_session.add(team)
    db_session.flush()

    first = api_client.put(
        f"/teams/{team.id}/supervisor",
        headers=_headers(coordinator),
        json={"supervisor_id": str(first_supervisor.id)},
    )
    invalid = api_client.put(
        f"/teams/{team.id}/supervisor",
        headers=_headers(coordinator),
        json={"supervisor_id": str(invalid_target.id)},
    )
    reassigned = api_client.put(
        f"/teams/{team.id}/supervisor",
        headers=_headers(coordinator),
        json={"supervisor_id": str(next_supervisor.id)},
    )

    assert first.status_code == 200
    assert first.json()["supervisor_id"] == str(first_supervisor.id)
    assert invalid.status_code == 422
    assert reassigned.status_code == 200
    assert reassigned.json()["supervisor_id"] == str(next_supervisor.id)
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(SupervisorAssignment)
            .where(SupervisorAssignment.team_id == team.id)
        )
        == 1
    )
    current_assignment = db_session.get(SupervisorAssignment, team.id)
    assert current_assignment is not None
    assert current_assignment.supervisor_id == next_supervisor.id


def test_supervisor_assignment_requires_an_existing_team(
    api_client: TestClient, db_session: Session
) -> None:
    coordinator = _new_user(db_session, "coordinator")
    supervisor = _new_user(db_session, "supervisor")

    response = api_client.put(
        f"/teams/{uuid4()}/supervisor",
        headers=_headers(coordinator),
        json={"supervisor_id": str(supervisor.id)},
    )

    assert response.status_code == 404


def test_coordinator_cannot_assign_inactive_supervisor(
    api_client: TestClient, db_session: Session
) -> None:
    coordinator = _new_user(db_session, "coordinator")
    inactive_supervisor = _new_user(db_session, "supervisor")
    inactive_supervisor.is_active = False
    team = Team(name="Inactive Supervisor Team")
    db_session.add(team)
    db_session.flush()

    response = api_client.put(
        f"/teams/{team.id}/supervisor",
        headers=_headers(coordinator),
        json={"supervisor_id": str(inactive_supervisor.id)},
    )

    assert response.status_code == 422
    assert db_session.get(SupervisorAssignment, team.id) is None


def test_end_to_end_student_team_coordinator_supervisor_flow(
    api_client: TestClient, db_session: Session
) -> None:
    student_password = "synthetic-student-passphrase"
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
    assert registration.json()["system_role"] == "student"

    student_login = api_client.post(
        "/auth/login",
        json={"email": student_email, "password": student_password},
    )
    assert student_login.status_code == 200
    student_headers = {
        "Authorization": f"Bearer {student_login.json()['access_token']}"
    }

    member_password = "synthetic-member-passphrase"
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

    team = api_client.post(
        "/teams",
        headers=student_headers,
        json={"name": "Synthetic Integrated Team"},
    )
    assert team.status_code == 201

    member = api_client.post(
        f"/teams/{team.json()['id']}/members",
        headers=student_headers,
        json={"user_id": member_registration.json()["id"]},
    )
    assert team.json()["members"][0]["role"] == "leader"
    assert member.status_code == 201
    assert member.json()["role"] == "member"

    coordinator_password = "synthetic-coordinator-passphrase"
    coordinator = _new_user(db_session, "coordinator")
    coordinator.password_hash = security.hash_password(coordinator_password)
    db_session.flush()
    coordinator_login = api_client.post(
        "/auth/login",
        json={"email": coordinator.email, "password": coordinator_password},
    )
    assert coordinator_login.status_code == 200
    coordinator_headers = {
        "Authorization": f"Bearer {coordinator_login.json()['access_token']}"
    }

    supervisor_password = "synthetic-supervisor-passphrase"
    supervisor = _new_user(db_session, "supervisor")
    supervisor.password_hash = security.hash_password(supervisor_password)
    db_session.flush()
    supervisor_login = api_client.post(
        "/auth/login",
        json={"email": supervisor.email, "password": supervisor_password},
    )
    assert supervisor_login.status_code == 200
    supervisor_headers = {
        "Authorization": f"Bearer {supervisor_login.json()['access_token']}"
    }

    assignment = api_client.put(
        f"/teams/{team.json()['id']}/supervisor",
        headers=coordinator_headers,
        json={"supervisor_id": str(supervisor.id)},
    )
    supervisor_team_list = api_client.get("/teams", headers=supervisor_headers)
    supervisor_team_read = api_client.get(
        f"/teams/{team.json()['id']}", headers=supervisor_headers
    )

    assert assignment.status_code == 200
    assert assignment.json()["supervisor_id"] == str(supervisor.id)
    assert [item["id"] for item in supervisor_team_list.json()] == [team.json()["id"]]
    assert supervisor_team_read.status_code == 200
    assert supervisor_team_read.json()["supervisor_id"] == str(supervisor.id)
    assert {item["role"] for item in supervisor_team_read.json()["members"]} == {
        "leader",
        "member",
    }
