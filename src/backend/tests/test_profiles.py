"""Tests for GT-32 profile management, avatar upload/stream/deletion, and team reads."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from app import security
from app.auth import get_db_session
from app.config import Settings
from app.main import app
from app.models import (
    Team,
    TeamMembership,
    User,
)
from app.submission_storage import (
    MAX_AVATAR_SIZE_BYTES,
    open_stored_file,
    private_storage_root,
)
from app.supervisor_assignments import assign_supervisor
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

pytestmark = pytest.mark.postgresql

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

TINY_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C"
    b"\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b"
    b"\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7)"
    b",01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff"
    b"\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00"
    b"\x00?\x00\xbf\x00\xff\xd9"
)


@pytest.fixture(autouse=True)
def private_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "private_uploads"
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(root))
    return root


@pytest.fixture
def api_client(db_session: OrmSession) -> Generator[TestClient, None, None]:
    def override_db_session() -> Generator[OrmSession, None, None]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _new_user(
    session: OrmSession,
    role: str = "student",
    display_name: str | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        email=f"{role}.{uuid4().hex}@example.com",
        password_hash="synthetic-test-only-hash",
        display_name=display_name or f"Synthetic {role.title()}",
        system_role=role,
        is_active=is_active,
    )
    session.add(user)
    session.flush()
    return user


def _new_team(session: OrmSession, leader: User, name: str = "Synthetic Team") -> Team:
    team = Team(name=name)
    session.add(team)
    session.flush()
    session.add(TeamMembership(team_id=team.id, user_id=leader.id, role="leader"))
    session.flush()
    return team


def _add_team_member(
    session: OrmSession, team: Team, user: User, role: str = "member"
) -> TeamMembership:
    membership = TeamMembership(team_id=team.id, user_id=user.id, role=role)
    session.add(membership)
    session.flush()
    return membership


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {security.create_access_token(user.id)}"}


# ==============================================================================
# Self-Service Profile: GET and PATCH /auth/me
# ==============================================================================


def test_read_own_profile_default(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Default Student")
    response = api_client.get("/auth/me", headers=_headers(user))

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(user.id)
    assert data["email"] == user.email
    assert data["display_name"] == "Default Student"
    assert data["system_role"] == "student"
    assert data["student_number"] is None
    assert data["faculty"] is None
    assert data["department"] is None
    assert data["academic_level"] is None
    assert data["bio"] is None
    assert data["has_avatar"] is False
    assert "password" not in data
    assert "password_hash" not in data
    assert "avatar_storage_key" not in data


def test_update_own_profile_partial(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Original Name")
    update_payload = {
        "display_name": "Updated Name",
        "student_number": "2024-CS/123",
        "faculty": "Faculty of Engineering",
        "department": "Computer Systems",
    }
    patch_res = api_client.patch(
        "/auth/me", json=update_payload, headers=_headers(user)
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["display_name"] == "Updated Name"
    assert data["student_number"] == "2024-CS/123"
    assert data["faculty"] == "Faculty of Engineering"
    assert data["department"] == "Computer Systems"
    assert data["academic_level"] is None
    assert data["bio"] is None

    # Subsequent GET verifies persistence in DB
    get_res = api_client.get("/auth/me", headers=_headers(user))
    assert get_res.status_code == 200
    assert get_res.json() == data


def test_update_own_profile_clear_fields(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Student One")
    api_client.patch(
        "/auth/me",
        json={
            "student_number": "ST-111",
            "bio": "Initial bio",
            "faculty": "Science",
        },
        headers=_headers(user),
    )

    # Explicit null clears optional fields, omitting faculty leaves it unchanged
    clear_payload = {
        "student_number": None,
        "bio": None,
    }
    clear_res = api_client.patch("/auth/me", json=clear_payload, headers=_headers(user))
    assert clear_res.status_code == 200
    data = clear_res.json()
    assert data["student_number"] is None
    assert data["bio"] is None
    assert data["faculty"] == "Science"


def test_update_own_profile_empty_body(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "No-Op Student")
    res = api_client.patch("/auth/me", json={}, headers=_headers(user))
    assert res.status_code == 200
    assert res.json()["display_name"] == "No-Op Student"


def test_update_own_profile_forbidden_fields_rejected(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Hacker Wannabe")

    forbidden_cases = [
        {"system_role": "coordinator"},
        {"is_active": False},
        {"id": str(uuid4())},
        {"email": "hacked@example.test"},
        {"password_hash": "stolen_hash"},
        {"avatar_storage_key": "0" * 32},
        {"created_at": "2026-01-01T00:00:00Z"},
    ]

    for case in forbidden_cases:
        res = api_client.patch("/auth/me", json=case, headers=_headers(user))
        assert res.status_code == 422, f"Case {case} was not rejected with 422"

    # Confirm user's system_role and email were untouched in DB
    db_session.refresh(user)
    assert user.system_role == "student"
    assert user.is_active is True


def test_update_own_profile_validation_errors(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Validator Student")

    invalid_cases = [
        ({"display_name": None}, 422),  # Cannot clear required display_name
        ({"display_name": "   "}, 422),  # Whitespace-only display_name
        ({"display_name": "x" * 161}, 422),  # Exceeds max length
        ({"student_number": "invalid@#$"}, 422),  # Invalid characters
        ({"faculty": "x" * 121}, 422),  # Exceeds max length
        ({"department": "x" * 121}, 422),  # Exceeds max length
        ({"academic_level": "x" * 41}, 422),  # Exceeds max length
        ({"bio": "x" * 501}, 422),  # Exceeds max length
    ]

    for payload, expected_status in invalid_cases:
        res = api_client.patch("/auth/me", json=payload, headers=_headers(user))
        assert res.status_code == expected_status, f"Failed for {payload}"


def test_update_own_profile_unauthenticated(api_client: TestClient) -> None:
    res = api_client.patch("/auth/me", json={"display_name": "Anonymous"})
    assert res.status_code == 401


# ==============================================================================
# Avatar: Upload, Stream, Replace, Delete
# ==============================================================================


def test_avatar_upload_valid_png_and_stream(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Avatar PNG Student")
    upload_res = api_client.post(
        "/auth/me/avatar",
        files={"file": ("profile.png", TINY_PNG, "image/png")},
        headers=_headers(user),
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["has_avatar"] is True

    # Own stream preview
    stream_res = api_client.get("/auth/me/avatar", headers=_headers(user))
    assert stream_res.status_code == 200
    assert stream_res.headers["Content-Type"] == "image/png"
    assert stream_res.headers["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in stream_res.headers["Cache-Control"]
    assert stream_res.content == TINY_PNG


def test_avatar_upload_valid_jpeg(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Avatar JPEG Student")
    upload_res = api_client.post(
        "/auth/me/avatar",
        files={"file": ("photo.jpg", TINY_JPEG, "image/jpeg")},
        headers=_headers(user),
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["has_avatar"] is True

    stream_res = api_client.get("/auth/me/avatar", headers=_headers(user))
    assert stream_res.status_code == 200
    assert stream_res.headers["Content-Type"] == "image/jpeg"
    assert stream_res.content == TINY_JPEG


def test_avatar_upload_rejects_unsupported_extensions(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Unsupported Ext Student")

    cases = [
        ("avatar.svg", b"<svg></svg>", "image/svg+xml"),
        ("avatar.gif", b"GIF89a", "image/gif"),
        ("avatar.pdf", b"%PDF-1.4", "application/pdf"),
        ("avatar.txt", b"plain text", "text/plain"),
        ("avatar.exe", b"MZ", "application/x-msdownload"),
    ]

    for filename, content, mime in cases:
        res = api_client.post(
            "/auth/me/avatar",
            files={"file": (filename, content, mime)},
            headers=_headers(user),
        )
        assert res.status_code == 422, f"Extension {filename} was not rejected"


def test_avatar_upload_rejects_spoofed_content(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Spoofer Student")
    # File named .png but with text content
    res = api_client.post(
        "/auth/me/avatar",
        files={"file": ("fake.png", b"not a png image", "image/png")},
        headers=_headers(user),
    )
    assert res.status_code == 422


def test_avatar_upload_rejects_oversized_file(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Oversized Student")
    oversized_data = TINY_PNG + b"0" * (MAX_AVATAR_SIZE_BYTES + 1024)
    res = api_client.post(
        "/auth/me/avatar",
        files={"file": ("huge.png", oversized_data, "image/png")},
        headers=_headers(user),
    )
    assert res.status_code == 413


def test_avatar_stream_missing_returns_404(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "No Avatar Student")
    res = api_client.get("/auth/me/avatar", headers=_headers(user))
    assert res.status_code == 404
    assert res.json()["detail"] == "Avatar not found"


def test_avatar_replacement_cleans_old_file(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Replacer Student")
    cfg_dir = Settings.from_environment().private_upload_dir

    # 1. Upload first avatar (PNG)
    api_client.post(
        "/auth/me/avatar",
        files={"file": ("first.png", TINY_PNG, "image/png")},
        headers=_headers(user),
    )
    db_session.refresh(user)
    first_key = user.avatar_storage_key
    assert first_key is not None
    # Verify first file exists on disk
    with open_stored_file(cfg_dir, first_key) as f:
        assert f.read() == TINY_PNG

    # 2. Upload replacement avatar (JPEG)
    replace_res = api_client.post(
        "/auth/me/avatar",
        files={"file": ("second.jpg", TINY_JPEG, "image/jpeg")},
        headers=_headers(user),
    )
    assert replace_res.status_code == 200
    db_session.refresh(user)
    second_key = user.avatar_storage_key
    assert second_key != first_key

    # Verify new file exists and streams JPEG
    with open_stored_file(cfg_dir, second_key) as f:
        assert f.read() == TINY_JPEG

    # Verify old file was deleted from disk
    storage_root = private_storage_root(cfg_dir, create=False)
    assert not (storage_root / first_key).exists()


def test_avatar_failed_replacement_preserves_old_file(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Cautious Student")

    # 1. Upload initial PNG
    api_client.post(
        "/auth/me/avatar",
        files={"file": ("good.png", TINY_PNG, "image/png")},
        headers=_headers(user),
    )
    db_session.refresh(user)
    initial_key = user.avatar_storage_key
    assert initial_key is not None

    # 2. Attempt invalid upload (spoofed content)
    fail_res = api_client.post(
        "/auth/me/avatar",
        files={"file": ("corrupt.png", b"corrupted bytes", "image/png")},
        headers=_headers(user),
    )
    assert fail_res.status_code == 422

    # 3. Verify original avatar is still preserved in DB and on disk
    db_session.refresh(user)
    assert user.avatar_storage_key == initial_key
    stream_res = api_client.get("/auth/me/avatar", headers=_headers(user))
    assert stream_res.status_code == 200
    assert stream_res.content == TINY_PNG


def test_avatar_delete_and_idempotency(
    api_client: TestClient, db_session: OrmSession
) -> None:
    user = _new_user(db_session, "student", "Deleter Student")
    cfg_dir = Settings.from_environment().private_upload_dir

    # Upload avatar
    api_client.post(
        "/auth/me/avatar",
        files={"file": ("del.png", TINY_PNG, "image/png")},
        headers=_headers(user),
    )
    db_session.refresh(user)
    key = user.avatar_storage_key
    assert key is not None

    # Delete avatar
    del_res = api_client.delete("/auth/me/avatar", headers=_headers(user))
    assert del_res.status_code == 200
    assert del_res.json()["has_avatar"] is False

    db_session.refresh(user)
    assert user.avatar_storage_key is None

    # File on disk is removed
    storage_root = private_storage_root(cfg_dir, create=False)
    assert not (storage_root / key).exists()

    # GET returns 404
    assert api_client.get("/auth/me/avatar", headers=_headers(user)).status_code == 404

    # Calling DELETE again is an idempotent 200 OK
    repeat_del = api_client.delete("/auth/me/avatar", headers=_headers(user))
    assert repeat_del.status_code == 200
    assert repeat_del.json()["has_avatar"] is False


# ==============================================================================
# Team-Scoped Profile and Avatar Reads
# ==============================================================================


def test_team_member_profile_read_by_teammate_supervisor_coordinator(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Leader Student")
    member = _new_user(db_session, "student", "Member Student")
    supervisor = _new_user(db_session, "supervisor", "Project Supervisor")
    coordinator = _new_user(db_session, "coordinator", "Course Coordinator")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)
    assign_supervisor(db_session, team.id, supervisor.id)
    db_session.commit()

    # Set profile data and avatar on member
    member.faculty = "Computer Science"
    member.department = "Information Systems"
    member.academic_level = "Fourth Year"
    member.bio = "Interested in distributed systems"
    member.student_number = "SECRET-STU-999"
    db_session.commit()

    api_client.post(
        "/auth/me/avatar",
        files={"file": ("avatar.png", TINY_PNG, "image/png")},
        headers=_headers(member),
    )

    url = f"/teams/{team.id}/members/{member.id}/profile"

    # 1. Teammate reads profile
    res_lead = api_client.get(url, headers=_headers(leader))
    assert res_lead.status_code == 200
    lead_data = res_lead.json()
    assert lead_data["id"] == str(member.id)
    assert lead_data["display_name"] == "Member Student"
    assert lead_data["team_role"] == "member"
    assert lead_data["faculty"] == "Computer Science"
    assert lead_data["department"] == "Information Systems"
    assert lead_data["academic_level"] == "Fourth Year"
    assert lead_data["bio"] == "Interested in distributed systems"
    assert lead_data["has_avatar"] is True
    # Crucial D4 check: student_number and email are NOT disclosed!
    assert "student_number" not in lead_data
    assert "email" not in lead_data

    # 2. Assigned supervisor reads profile
    res_sup = api_client.get(url, headers=_headers(supervisor))
    assert res_sup.status_code == 200
    assert res_sup.json() == lead_data

    # 3. Coordinator reads profile
    res_coord = api_client.get(url, headers=_headers(coordinator))
    assert res_coord.status_code == 200
    assert res_coord.json() == lead_data


def test_team_member_profile_read_unauthorized(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Leader Student")
    member = _new_user(db_session, "student", "Member Student")
    outsider_student = _new_user(db_session, "student", "Outsider Student")
    unassigned_sup = _new_user(db_session, "supervisor", "Unassigned Sup")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)
    db_session.commit()

    url = f"/teams/{team.id}/members/{member.id}/profile"

    # Outsider student gets 404 (team not found / access denied)
    assert api_client.get(url, headers=_headers(outsider_student)).status_code == 404

    # Unassigned supervisor gets 404
    assert api_client.get(url, headers=_headers(unassigned_sup)).status_code == 404

    # Non-member ID in valid team gets 404
    fake_id = uuid4()
    assert (
        api_client.get(
            f"/teams/{team.id}/members/{fake_id}/profile", headers=_headers(leader)
        ).status_code
        == 404
    )


def test_team_member_profile_read_former_supervisor_blocked(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Leader Student")
    member = _new_user(db_session, "student", "Member Student")
    former_sup = _new_user(db_session, "supervisor", "Former Supervisor")
    new_sup = _new_user(db_session, "supervisor", "New Supervisor")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)

    # Assign initial supervisor
    assign_supervisor(db_session, team.id, former_sup.id)
    db_session.commit()

    url = f"/teams/{team.id}/members/{member.id}/profile"
    assert api_client.get(url, headers=_headers(former_sup)).status_code == 200

    # Reassign supervisor
    assign_supervisor(db_session, team.id, new_sup.id)
    db_session.commit()

    # Former supervisor now gets 404
    assert api_client.get(url, headers=_headers(former_sup)).status_code == 404
    # New supervisor gets 200
    assert api_client.get(url, headers=_headers(new_sup)).status_code == 200


def test_team_member_avatar_stream_and_access_control(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Leader Student")
    member = _new_user(db_session, "student", "Member Student")
    outsider = _new_user(db_session, "student", "Outsider Student")
    supervisor = _new_user(db_session, "supervisor", "Project Supervisor")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)
    assign_supervisor(db_session, team.id, supervisor.id)
    db_session.commit()

    avatar_url = f"/teams/{team.id}/members/{member.id}/avatar"

    # Member has no avatar yet -> 404
    assert api_client.get(avatar_url, headers=_headers(leader)).status_code == 404

    # Member uploads avatar
    api_client.post(
        "/auth/me/avatar",
        files={"file": ("member.png", TINY_PNG, "image/png")},
        headers=_headers(member),
    )

    # Teammate can stream avatar
    stream_res = api_client.get(avatar_url, headers=_headers(leader))
    assert stream_res.status_code == 200
    assert stream_res.headers["Content-Type"] == "image/png"
    assert stream_res.content == TINY_PNG

    # Assigned supervisor can stream avatar
    sup_res = api_client.get(avatar_url, headers=_headers(supervisor))
    assert sup_res.status_code == 200
    assert sup_res.content == TINY_PNG

    # Outsider gets 404
    assert api_client.get(avatar_url, headers=_headers(outsider)).status_code == 404


def test_team_detail_reflects_name_change_and_avatar(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Original Leader Name")
    team = _new_team(db_session, leader)

    # Verify initial team detail
    initial_team = api_client.get(f"/teams/{team.id}", headers=_headers(leader))
    assert initial_team.status_code == 200
    member_info = initial_team.json()["members"][0]
    assert member_info["display_name"] == "Original Leader Name"
    assert member_info["has_avatar"] is False

    # Leader updates display_name and uploads avatar
    api_client.patch(
        "/auth/me",
        json={"display_name": "Updated Leader Name"},
        headers=_headers(leader),
    )
    api_client.post(
        "/auth/me/avatar",
        files={"file": ("leader.png", TINY_PNG, "image/png")},
        headers=_headers(leader),
    )

    # Verify team detail reflects changes
    updated_team = api_client.get(f"/teams/{team.id}", headers=_headers(leader))
    assert updated_team.status_code == 200
    updated_member = updated_team.json()["members"][0]
    assert updated_member["display_name"] == "Updated Leader Name"
    assert updated_member["has_avatar"] is True
