"""PostgreSQL-backed tests for manual authentication and role dependencies."""

import base64
import json
from collections.abc import Callable, Generator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

import jwt
import pytest
from app import security
from app.auth import (
    get_current_team_membership,
    require_system_roles,
    require_team_leader,
)
from app.database import get_db_session
from app.main import app
from app.models import Team, TeamMembership, User
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
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


def _registration_payload(**overrides: object) -> dict[str, object]:
    return {
        "email": f"{uuid4().hex}@example.com",
        "display_name": "Synthetic Student",
        "password": "Synthetic!Passphrase2026",
        **overrides,
    }


@pytest.fixture
def role_user_factory(db_session: Session):
    """Provision non-student roles directly in test setup, never through HTTP."""

    def create_user(role: Literal["supervisor", "coordinator"]) -> User:
        user = User(
            email=f"{role}.{uuid4().hex}@example.com",
            password_hash="synthetic-test-only-hash",
            display_name=f"Synthetic {role.title()}",
            system_role=role,
        )
        db_session.add(user)
        db_session.flush()
        return user

    return create_user


def _signed_token(user_id: UUID, *, expired: bool = False) -> str:
    now = datetime.now(UTC)
    expires_at = now - timedelta(minutes=1) if expired else now + timedelta(minutes=15)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now - timedelta(minutes=2) if expired else now,
            "exp": expires_at,
            "type": "access",
        },
        security.settings.auth_secret_key,
        algorithm="HS256",
    )


@pytest.mark.parametrize("requested_role", ("supervisor", "coordinator", "team_leader"))
def test_registration_persists_argon2_hash_and_forces_student_role(
    api_client: TestClient, db_session: Session, requested_role: str
) -> None:
    payload = _registration_payload(
        email="  STUDENT.Example@Example.com  ",
        system_role=requested_role,
    )

    response = api_client.post("/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "student.example@example.com"
    assert body["system_role"] == "student"
    assert "password" not in body
    assert "password_hash" not in body

    persisted = db_session.scalar(
        select(User).where(User.email == "student.example@example.com")
    )
    assert persisted is not None
    assert persisted.system_role == "student"
    assert persisted.password_hash != payload["password"]
    assert persisted.password_hash.startswith("$argon2id$")


@pytest.mark.parametrize(
    ("field", "value"),
    (("email", "not-an-email"), ("display_name", "   ")),
)
def test_registration_rejects_invalid_identity_fields(
    api_client: TestClient, field: str, value: str
) -> None:
    response = api_client.post(
        "/auth/register", json=_registration_payload(**{field: value})
    )

    assert response.status_code == 422


def test_registration_rejects_duplicate_normalized_email(
    api_client: TestClient,
) -> None:
    payload = _registration_payload(email="Student.Example@Example.com")

    first = api_client.post("/auth/register", json=payload)
    duplicate = api_client.post(
        "/auth/register",
        json={**payload, "email": " student.example@example.com "},
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "An account with this email already exists"}


def test_registration_rejects_weak_password(api_client: TestClient) -> None:
    response = api_client.post(
        "/auth/register", json=_registration_payload(password="weak")
    )

    assert response.status_code == 422


def test_registration_rejects_15_character_password(api_client: TestClient) -> None:
    password = "x" * 15

    response = api_client.post(
        "/auth/register", json=_registration_payload(password=password)
    )

    assert response.status_code == 422
    assert password not in response.text


def test_registration_and_login_accept_16_character_password(
    api_client: TestClient,
) -> None:
    payload = _registration_payload(password="x" * 16)

    registered = api_client.post("/auth/register", json=payload)
    login = api_client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )

    assert registered.status_code == 201
    assert login.status_code == 200


def test_registration_and_login_preserve_long_unicode_passphrase(
    api_client: TestClient,
) -> None:
    password = f"  {'あいことば ' * 11}  "
    payload = _registration_payload(password=password)

    registered = api_client.post("/auth/register", json=payload)
    exact_login = api_client.post(
        "/auth/login",
        json={"email": payload["email"], "password": password},
    )
    trimmed_login = api_client.post(
        "/auth/login",
        json={"email": payload["email"], "password": password.strip()},
    )

    assert registered.status_code == 201
    assert exact_login.status_code == 200
    assert trimmed_login.status_code == 401


def test_login_returns_bearer_token_and_me_exposes_only_public_fields(
    api_client: TestClient,
) -> None:
    payload = _registration_payload()
    registered = api_client.post("/auth/register", json=payload)

    login = api_client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    token = login.json()["access_token"]
    me = api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert registered.status_code == 201
    assert login.status_code == 200
    assert login.json()["token_type"] == "Bearer"
    assert login.json()["expires_in"] == 900
    assert me.status_code == 200
    assert set(me.json()) == {"id", "email", "display_name", "system_role"}
    assert me.json()["system_role"] == "student"
    assert "password" not in me.json()
    assert "password_hash" not in me.json()


def test_login_does_not_disclose_unknown_or_wrong_password(
    api_client: TestClient,
) -> None:
    payload = _registration_payload()
    api_client.post("/auth/register", json=payload)

    wrong_password = api_client.post(
        "/auth/login",
        json={"email": payload["email"], "password": "Wrong!Passphrase2026"},
    )
    unknown_user = api_client.post(
        "/auth/login",
        json={"email": "missing@example.com", "password": "Wrong!Passphrase2026"},
    )

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert "password_hash" not in wrong_password.text
    assert "password_hash" not in unknown_user.text


def test_invalid_missing_tampered_and_expired_tokens_are_denied(
    api_client: TestClient,
) -> None:
    user_id = uuid4()
    valid_token = _signed_token(user_id)
    header, payload, signature = valid_token.split(".")
    tampered_header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .decode()
        .rstrip("=")
    )
    cases = (
        {},
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": f"Bearer {tampered_header}.{payload}.{signature}"},
        {"Authorization": f"Bearer {_signed_token(user_id, expired=True)}"},
        {"Authorization": f"Bearer {valid_token}"},
    )

    for headers in cases:
        response = api_client.get("/auth/me", headers=headers)
        assert response.status_code == 401
        assert response.json() == {"detail": "Could not validate credentials"}


def test_inactive_user_is_rejected_at_login_and_after_token_issue(
    api_client: TestClient, db_session: Session
) -> None:
    payload = _registration_payload()
    api_client.post("/auth/register", json=payload)
    login = api_client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    user = db_session.scalar(select(User).where(User.email == payload["email"]))
    assert user is not None
    user.is_active = False
    db_session.commit()

    disabled_login = api_client.post(
        "/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    disabled_me = api_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert disabled_login.status_code == 401
    assert disabled_me.status_code == 401


def test_auth_endpoints_fail_closed_without_a_signing_secret(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        security,
        "settings",
        replace(security.settings, auth_secret_key=None),
    )

    response = api_client.post("/auth/register", json=_registration_payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "Authentication is not configured"}


def test_system_role_dependency_denies_students_from_coordinator_access(
    db_session: Session,
    role_user_factory: Callable[[Literal["supervisor", "coordinator"]], User],
) -> None:
    student = User(
        email=f"student.{uuid4().hex}@example.com",
        password_hash="synthetic-test-only-hash",
        display_name="Synthetic Student",
        system_role="student",
    )
    db_session.add(student)
    db_session.flush()
    coordinator = role_user_factory("coordinator")
    require_coordinator = require_system_roles("coordinator")

    with pytest.raises(HTTPException) as denied:
        require_coordinator(current_user=student)

    assert denied.value.status_code == 403
    assert require_coordinator(current_user=coordinator) is coordinator
    with pytest.raises(ValueError, match="system role"):
        require_system_roles("team_leader")


def test_team_membership_scope_and_leader_dependency_are_team_specific(
    db_session: Session,
) -> None:
    student = User(
        email="leader@example.com",
        password_hash="synthetic-hash",
        display_name="Synthetic Leader",
        system_role="student",
    )
    team = Team(name="Synthetic Scoped Team")
    db_session.add_all([student, team])
    db_session.flush()
    membership = TeamMembership(team_id=team.id, user_id=student.id, role="leader")
    db_session.add(membership)
    db_session.flush()
    member_user = User(
        email=f"member.{uuid4().hex}@example.com",
        password_hash="synthetic-test-only-hash",
        display_name="Synthetic Member",
        system_role="student",
    )
    db_session.add(member_user)
    db_session.flush()
    member = TeamMembership(team_id=team.id, user_id=member_user.id, role="member")
    db_session.add(member)
    db_session.flush()

    scoped_membership = get_current_team_membership(
        team_id=team.id, current_user=student, session=db_session
    )
    assert require_team_leader()(membership=scoped_membership) is membership

    with pytest.raises(HTTPException) as member_denied:
        require_team_leader()(membership=member)
    assert member_denied.value.status_code == 403

    with pytest.raises(HTTPException) as denied:
        get_current_team_membership(
            team_id=uuid4(), current_user=student, session=db_session
        )

    assert denied.value.status_code == 403
