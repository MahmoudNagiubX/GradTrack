"""PostgreSQL integration checks for the Phase 1 persistence foundation."""

from uuid import uuid4

import pytest
from app.database import engine
from app.main import app
from app.models import (
    SupervisorAssignment,
    Team,
    TeamMembership,
    User,
)
from app.supervisor_assignments import assign_supervisor
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

pytestmark = pytest.mark.postgresql


def _user(
    session: Session,
    email: str,
    *,
    system_role: str = "student",
) -> User:
    user = User(
        email=email,
        password_hash="synthetic-test-hash",
        display_name="Synthetic Test User",
        system_role=system_role,
    )
    session.add(user)
    session.flush()
    return user


def _team(session: Session, name: str = "Synthetic Test Team") -> Team:
    team = Team(name=name)
    session.add(team)
    session.flush()
    return team


def test_database_health_endpoint_checks_postgresql() -> None:
    response = TestClient(app).get("/health/database")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_user_persistence_and_timezone_aware_timestamps(db_session: Session) -> None:
    user = _user(db_session, f"{uuid4().hex}@example.test")
    db_session.commit()

    persisted = db_session.get(User, user.id)

    assert persisted is not None
    assert persisted.email == user.email
    assert persisted.password_hash == "synthetic-test-hash"
    assert persisted.system_role == "student"
    assert persisted.is_active is True
    assert persisted.created_at is not None
    assert persisted.created_at.tzinfo is not None
    assert persisted.updated_at is not None
    assert persisted.updated_at.tzinfo is not None


def test_email_must_be_normalized_and_unique(db_session: Session) -> None:
    _user(db_session, "first@example.test")
    duplicate = User(
        email="first@example.test",
        password_hash="synthetic-test-hash",
        display_name="Synthetic Duplicate",
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    unnormalized = User(
        email=" Second@example.test ",
        password_hash="synthetic-test-hash",
        display_name="Synthetic Unnormalized",
    )
    db_session.add(unnormalized)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_system_role_is_limited_to_approved_values(db_session: Session) -> None:
    invalid = User(
        email=f"{uuid4().hex}@example.test",
        password_hash="synthetic-test-hash",
        display_name="Synthetic Invalid Role",
        system_role="team_leader",
    )
    db_session.add(invalid)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_team_can_be_unassigned_and_name_cannot_be_blank(db_session: Session) -> None:
    team = _team(db_session)

    assert db_session.get(SupervisorAssignment, team.id) is None

    blank_team = Team(name="   ")
    db_session.add(blank_team)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_membership_is_unique_and_role_is_team_scoped(db_session: Session) -> None:
    team = _team(db_session)
    user = _user(db_session, f"{uuid4().hex}@example.test")
    membership = TeamMembership(team_id=team.id, user_id=user.id, role="leader")
    db_session.add(membership)
    db_session.flush()

    duplicate = TeamMembership(team_id=team.id, user_id=user.id, role="member")
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_membership_foreign_keys_are_enforced(db_session: Session) -> None:
    membership = TeamMembership(team_id=uuid4(), user_id=uuid4(), role="member")
    db_session.add(membership)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_membership_role_is_restricted_to_team_roles(db_session: Session) -> None:
    team = _team(db_session)
    user = _user(db_session, f"{uuid4().hex}@example.test")
    membership = TeamMembership(
        team_id=team.id,
        user_id=user.id,
        role="coordinator",
    )
    db_session.add(membership)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_supervisor_assignment_validates_role_and_reassigns_one_current_record(
    db_session: Session,
) -> None:
    team = _team(db_session)
    first = _user(
        db_session,
        f"{uuid4().hex}@example.test",
        system_role="supervisor",
    )
    second = _user(
        db_session,
        f"{uuid4().hex}@example.test",
        system_role="supervisor",
    )
    student = _user(db_session, f"{uuid4().hex}@example.test")

    assignment = assign_supervisor(db_session, team.id, first.id)
    db_session.flush()
    assignment_team_id = assignment.team_id

    with pytest.raises(ValueError, match="supervisor"):
        assign_supervisor(db_session, team.id, student.id)

    reassigned = assign_supervisor(db_session, team.id, second.id)
    db_session.flush()

    assert reassigned.team_id == assignment_team_id == team.id
    assert reassigned.supervisor_id == second.id
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(SupervisorAssignment)
            .where(SupervisorAssignment.team_id == team.id)
        )
        == 1
    )


def test_supervisor_assignment_foreign_keys_are_enforced(
    db_session: Session,
) -> None:
    assignment = SupervisorAssignment(team_id=uuid4(), supervisor_id=uuid4())
    db_session.add(assignment)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_database_engine_is_configured_for_postgresql(postgres_engine: Engine) -> None:
    assert engine.dialect.name == "postgresql"
    assert postgres_engine.dialect.name == "postgresql"
