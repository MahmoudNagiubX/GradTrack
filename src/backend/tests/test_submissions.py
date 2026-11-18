"""PostgreSQL-backed submission, lateness, and private download tests."""

from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from app import security, submission_storage, submissions
from app.auth import get_db_session
from app.database import SessionLocal, engine
from app.main import app
from app.models import (
    Milestone,
    MilestoneSubmission,
    SubmissionVersion,
    Team,
    TeamMembership,
    User,
)
from app.supervisor_assignments import assign_supervisor
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session as OrmSession

pytestmark = pytest.mark.postgresql


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


def _new_user(session: OrmSession, role: str = "student") -> User:
    user = User(
        email=f"{role}.{uuid4().hex}@example.test",
        password_hash="synthetic-test-only-hash",
        display_name=f"Synthetic {role.title()}",
        system_role=role,
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


def _new_milestone(
    session: OrmSession,
    team: Team,
    due_at: datetime,
    name: str = "Synthetic SRS",
) -> Milestone:
    milestone = Milestone(team_id=team.id, name=name, due_at=due_at)
    session.add(milestone)
    session.flush()
    return milestone


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {security.create_access_token(user.id)}"}


def _submissions_path(team: Team, milestone: Milestone) -> str:
    return f"/teams/{team.id}/milestones/{milestone.id}/submissions"


@pytest.fixture
def committed_submission_scenario(postgres_engine: Engine):
    """Provide committed rows for independent concurrent request sessions."""
    with SessionLocal() as session:
        student = _new_user(session)
        coordinator = _new_user(session, "coordinator")
        team = _new_team(session, student)
        milestone = _new_milestone(session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))
        session.commit()
        student_id = student.id
        coordinator_id = coordinator.id
        team_id, milestone_id = team.id, milestone.id
        scenario = (student, coordinator, team, milestone)

    try:
        yield scenario
    finally:
        with postgres_engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE submission_versions DISABLE TRIGGER "
                "trg_submission_versions_immutable"
            )
            try:
                connection.execute(
                    text(
                        "DELETE FROM submission_versions WHERE submission_id IN ("
                        "SELECT id FROM milestone_submissions "
                        "WHERE milestone_id = :id)"
                    ),
                    {"id": milestone_id},
                )
                connection.execute(
                    text("DELETE FROM milestone_submissions WHERE milestone_id = :id"),
                    {"id": milestone_id},
                )
                connection.execute(
                    text("DELETE FROM milestones WHERE id = :id"), {"id": milestone_id}
                )
                connection.execute(
                    text("DELETE FROM team_memberships WHERE team_id = :id"),
                    {"id": team_id},
                )
                connection.execute(
                    text("DELETE FROM teams WHERE id = :id"), {"id": team_id}
                )
                connection.execute(
                    text("DELETE FROM users WHERE id = :id"), {"id": student_id}
                )
                connection.execute(
                    text("DELETE FROM users WHERE id = :id"), {"id": coordinator_id}
                )
            finally:
                connection.exec_driver_sql(
                    "ALTER TABLE submission_versions ENABLE TRIGGER "
                    "trg_submission_versions_immutable"
                )


@pytest.fixture
def independent_api_sessions() -> Generator[None, None, None]:
    """Use a new SQLAlchemy session for each independently served request."""

    def override_db_session() -> Generator[OrmSession, None, None]:
        with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def _new_link(
    client: TestClient,
    team: Team,
    milestone: Milestone,
    student: User,
    url: str = "https://example.org/submissions/srs",
):
    return client.post(
        f"{_submissions_path(team, milestone)}/link",
        json={"url": url},
        headers=_headers(student),
    )


def test_link_submission_snapshots_deadline_and_is_immutable_after_edit(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    student = _new_user(db_session)
    coordinator = _new_user(db_session, "coordinator")
    team = _new_team(db_session, student)
    submitted_at = datetime(2026, 12, 1, 15, tzinfo=UTC)
    milestone = _new_milestone(db_session, team, submitted_at)
    monkeypatch.setattr(submissions, "_now_utc", lambda: submitted_at)

    response = _new_link(api_client, team, milestone, student)

    assert response.status_code == 201
    body = response.json()
    assert body["version_number"] == 1
    assert body["submitted_by"] == str(student.id)
    assert body["submitted_at"] == "2026-12-01T15:00:00Z"
    assert body["deadline_at_submission"] == "2026-12-01T15:00:00Z"
    assert body["is_late"] is False
    assert body["source_type"] == "link"
    assert body["url"] == "https://example.org/submissions/srs"
    assert body["review_status"] == "pending_review"
    assert "storage_key" not in body

    spoofed = api_client.post(
        f"{_submissions_path(team, milestone)}/link",
        json={
            "url": "https://example.org/another-srs",
            "submitted_at": "2000-01-01T00:00:00Z",
            "is_late": True,
        },
        headers=_headers(student),
    )
    assert spoofed.status_code == 422
    spoofed_errors = spoofed.json()["detail"]
    assert all(set(error) == {"loc", "msg", "type"} for error in spoofed_errors)
    assert "2000-01-01T00:00:00Z" not in spoofed.text

    changed_deadline = "2026-11-30T15:00:00Z"
    updated = api_client.patch(
        f"/teams/{team.id}/milestones/{milestone.id}",
        json={"due_at": changed_deadline},
        headers=_headers(coordinator),
    )
    assert updated.status_code == 200

    detail = api_client.get(
        f"{_submissions_path(team, milestone)}/{body['id']}",
        headers=_headers(student),
    )
    listing = api_client.get(
        _submissions_path(team, milestone), headers=_headers(student)
    )
    assert detail.status_code == 200
    assert detail.json()["deadline_at_submission"] == "2026-12-01T15:00:00Z"
    assert detail.json()["is_late"] is False
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [body["id"]]


@pytest.mark.parametrize(
    ("delta", "expected_late"),
    [
        (timedelta(microseconds=-1), False),
        (timedelta(0), False),
        (timedelta(microseconds=1), True),
    ],
    ids=["one-microsecond-before", "exactly-at-deadline", "one-microsecond-after"],
)
def test_submission_lateness_uses_strict_server_time_boundary(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    delta: timedelta,
    expected_late: bool,
) -> None:
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    deadline = datetime(2026, 12, 1, 15, tzinfo=UTC)
    milestone = _new_milestone(db_session, team, deadline)
    monkeypatch.setattr(submissions, "_now_utc", lambda: deadline + delta)

    response = _new_link(api_client, team, milestone, student)

    assert response.status_code == 201
    assert response.json()["is_late"] is expected_late


def test_duplicate_submission_returns_409_without_mutating_history(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    milestone = _new_milestone(db_session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(tmp_path))
    first = _new_link(api_client, team, milestone, student)
    second = api_client.post(
        f"{_submissions_path(team, milestone)}/file",
        files={
            "file": ("replacement.pdf", b"%PDF-1.7\nreplacement", "application/pdf")
        },
        headers=_headers(student),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert len(list(tmp_path.iterdir())) == 0
    versions = db_session.scalars(select(SubmissionVersion)).all()
    assert len(versions) == 1
    assert versions[0].url == "https://example.org/submissions/srs"
    assert versions[0].source_type == "link"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/srs",
        "javascript:alert(1)",
        "https://user:synthetic-secret@example.org/srs",
        "https://127.0.0.1/srs",
        "https://localhost/srs",
        "https://example.org/srs#fragment",
    ],
)
def test_link_submission_rejects_unsafe_urls_without_echoing_them(
    api_client: TestClient,
    db_session: OrmSession,
    url: str,
) -> None:
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    milestone = _new_milestone(db_session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))

    response = _new_link(api_client, team, milestone, student, url)

    assert response.status_code == 422
    assert "synthetic-secret" not in response.text
    assert "input" not in response.text
    assert db_session.scalar(select(func.count()).select_from(MilestoneSubmission)) == 0


def test_only_active_team_students_can_submit_and_cross_team_reads_are_hidden(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    student = _new_user(db_session)
    outsider = _new_user(db_session)
    coordinator = _new_user(db_session, "coordinator")
    supervisor = _new_user(db_session, "supervisor")
    team = _new_team(db_session, student)
    assign_supervisor(db_session, team.id, supervisor.id)
    milestone = _new_milestone(db_session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))
    private_root = tmp_path / "must-not-be-created-for-outsider"
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(private_root))

    outside_submit = _new_link(api_client, team, milestone, outsider)
    coordinator_submit = _new_link(api_client, team, milestone, coordinator)
    supervisor_submit = _new_link(api_client, team, milestone, supervisor)
    assert outside_submit.status_code == 404
    assert coordinator_submit.status_code == 403
    assert supervisor_submit.status_code == 403
    outside_file = api_client.post(
        f"{_submissions_path(team, milestone)}/file",
        files={"file": ("srs.txt", b"Synthetic SRS", "text/plain")},
        headers=_headers(outsider),
    )
    assert outside_file.status_code == 404
    assert not private_root.exists()

    inactive = _new_user(db_session)
    db_session.add(TeamMembership(team_id=team.id, user_id=inactive.id, role="member"))
    inactive.is_active = False
    db_session.flush()
    inactive_submit = _new_link(api_client, team, milestone, inactive)

    assert inactive_submit.status_code == 401
    assert db_session.scalar(select(func.count()).select_from(MilestoneSubmission)) == 0


def test_private_pdf_upload_and_authorized_attachment_download(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    student = _new_user(db_session)
    member = _new_user(db_session)
    outsider = _new_user(db_session)
    supervisor = _new_user(db_session, "supervisor")
    unrelated_supervisor = _new_user(db_session, "supervisor")
    coordinator = _new_user(db_session, "coordinator")
    team = _new_team(db_session, student)
    other_team = _new_team(db_session, outsider, "Synthetic Other Team")
    db_session.add(TeamMembership(team_id=team.id, user_id=member.id, role="member"))
    assign_supervisor(db_session, team.id, supervisor.id)
    milestone = _new_milestone(db_session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))
    private_root = tmp_path / "private submissions"
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(private_root))
    payload = b"%PDF-1.7\nsynthetic-only submission bytes"
    response = api_client.post(
        f"{_submissions_path(team, milestone)}/file",
        files={"file": ("Synthetic-SRS.pdf", payload, "application/pdf")},
        headers=_headers(student),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["source_type"] == "file"
    assert body["original_filename"] == "Synthetic-SRS.pdf"
    assert body["file_size_bytes"] == len(payload)
    assert body["media_type"] == "application/pdf"
    assert body["url"] is None
    assert "storage_key" not in body
    stored_files = list(private_root.iterdir())
    assert len(stored_files) == 1
    assert stored_files[0].name != "Synthetic-SRS.pdf"
    assert stored_files[0].read_bytes() == payload

    path = f"{_submissions_path(team, milestone)}/{body['id']}/download"
    download = api_client.get(path, headers=_headers(student))
    assert download.status_code == 200
    assert download.content == payload
    assert download.headers["content-type"] == "application/octet-stream"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["cache-control"] == "no-store"
    assert "attachment" in download.headers["content-disposition"]
    assert "Synthetic-SRS.pdf" in download.headers["content-disposition"]

    for authorized_reader in (member, supervisor, coordinator):
        assert (
            api_client.get(path, headers=_headers(authorized_reader)).status_code == 200
        )
    assert api_client.get(path).status_code == 401
    for unauthorized_reader in (outsider, unrelated_supervisor):
        assert (
            api_client.get(path, headers=_headers(unauthorized_reader)).status_code
            == 404
        )
    cross_team_path = (
        f"/teams/{other_team.id}/milestones/{milestone.id}/submissions/"
        f"{body['id']}/download"
    )
    assert (
        api_client.get(cross_team_path, headers=_headers(outsider)).status_code == 404
    )


def test_current_supervisor_access_is_revoked_after_reassignment(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    student = _new_user(db_session)
    coordinator = _new_user(db_session, "coordinator")
    previous_supervisor = _new_user(db_session, "supervisor")
    current_supervisor = _new_user(db_session, "supervisor")
    team = _new_team(db_session, student)
    assign_supervisor(db_session, team.id, previous_supervisor.id)
    milestone = _new_milestone(db_session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(tmp_path))
    uploaded = api_client.post(
        f"{_submissions_path(team, milestone)}/file",
        files={"file": ("srs.txt", b"Synthetic SRS", "text/plain")},
        headers=_headers(student),
    )
    assert uploaded.status_code == 201
    download_path = (
        f"{_submissions_path(team, milestone)}/{uploaded.json()['id']}/download"
    )
    assert (
        api_client.get(download_path, headers=_headers(previous_supervisor)).status_code
        == 200
    )

    reassigned = api_client.put(
        f"/teams/{team.id}/supervisor",
        json={"supervisor_id": str(current_supervisor.id)},
        headers=_headers(coordinator),
    )

    assert reassigned.status_code == 200
    assert (
        api_client.get(download_path, headers=_headers(previous_supervisor)).status_code
        == 404
    )
    assert (
        api_client.get(download_path, headers=_headers(current_supervisor)).status_code
        == 200
    )


def test_submission_file_route_fails_closed_but_link_and_health_remain_available(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    file_milestone = _new_milestone(
        db_session,
        team,
        datetime(2026, 12, 1, 15, tzinfo=UTC),
        name="File milestone",
    )
    link_milestone = _new_milestone(
        db_session,
        team,
        datetime(2026, 12, 2, 15, tzinfo=UTC),
        name="Link milestone",
    )
    monkeypatch.delenv("GRADTRACK_PRIVATE_UPLOAD_DIR", raising=False)

    unavailable = api_client.post(
        f"{_submissions_path(team, file_milestone)}/file",
        files={"file": ("srs.pdf", b"%PDF-1.7\nsynthetic", "application/pdf")},
        headers=_headers(student),
    )
    link = _new_link(api_client, team, link_milestone, student)
    health = api_client.get("/health")

    assert unavailable.status_code == 503
    assert unavailable.json() == {"detail": "Private file storage is unavailable"}
    assert link.status_code == 201
    assert health.status_code == 200


def test_invalid_multipart_shape_and_invalid_file_leave_no_submission_or_files(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    milestone = _new_milestone(db_session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(tmp_path))
    path = f"{_submissions_path(team, milestone)}/file"

    extra_field = api_client.post(
        path,
        data={"unexpected": "value"},
        files={"file": ("srs.txt", b"Synthetic SRS", "text/plain")},
        headers=_headers(student),
    )
    wrong_part_name = api_client.post(
        path,
        files={"other": ("srs.txt", b"Synthetic SRS", "text/plain")},
        headers=_headers(student),
    )
    bad_signature = api_client.post(
        path,
        files={"file": ("srs.pdf", b"not a PDF", "application/pdf")},
        headers=_headers(student),
    )
    empty = api_client.post(
        path,
        files={"file": ("empty.txt", b"", "text/plain")},
        headers=_headers(student),
    )

    assert extra_field.status_code == 422
    assert wrong_part_name.status_code == 422
    assert bad_signature.status_code == 422
    assert empty.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(MilestoneSubmission)) == 0
    assert list(tmp_path.iterdir()) == []


def test_database_failure_after_file_promotion_removes_file_and_rows(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    milestone = _new_milestone(db_session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(tmp_path))

    def fail_commit(_session: OrmSession) -> None:
        raise SQLAlchemyError("synthetic database failure")

    monkeypatch.setattr(OrmSession, "commit", fail_commit)
    response = api_client.post(
        f"{_submissions_path(team, milestone)}/file",
        files={"file": ("srs.pdf", b"%PDF-1.7\nsynthetic", "application/pdf")},
        headers=_headers(student),
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Submission could not be saved"}
    assert list(tmp_path.iterdir()) == []
    assert db_session.scalar(select(func.count()).select_from(MilestoneSubmission)) == 0


@pytest.mark.parametrize("failure_point", ["write", "promote"])
def test_private_storage_io_failures_leave_no_file_or_database_row(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_point: str,
) -> None:
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    milestone = _new_milestone(db_session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(tmp_path))

    def fail_io(*_args, **_kwargs) -> None:
        raise OSError("synthetic storage failure")

    if failure_point == "write":
        monkeypatch.setattr(submission_storage.os, "fsync", fail_io)
    else:
        monkeypatch.setattr(submission_storage.os, "link", fail_io)

    response = api_client.post(
        f"{_submissions_path(team, milestone)}/file",
        files={"file": ("srs.pdf", b"%PDF-1.7\nsynthetic", "application/pdf")},
        headers=_headers(student),
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Private file storage is unavailable"}
    assert list(tmp_path.iterdir()) == []
    assert db_session.scalar(select(func.count()).select_from(MilestoneSubmission)) == 0


def test_exact_20_mib_file_is_accepted_and_one_byte_over_is_rejected(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.submission_storage import MAX_FILE_SIZE_BYTES

    student = _new_user(db_session)
    team = _new_team(db_session, student)
    exact_milestone = _new_milestone(
        db_session,
        team,
        datetime(2026, 12, 1, 15, tzinfo=UTC),
        name="Exact limit",
    )
    oversized_milestone = _new_milestone(
        db_session,
        team,
        datetime(2026, 12, 2, 15, tzinfo=UTC),
        name="Over limit",
    )
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(tmp_path))
    exact_payload = b"%PDF-" + b"x" * (MAX_FILE_SIZE_BYTES - len(b"%PDF-"))

    exact = api_client.post(
        f"{_submissions_path(team, exact_milestone)}/file",
        files={"file": ("exact.pdf", exact_payload, "application/pdf")},
        headers=_headers(student),
    )
    over_limit = api_client.post(
        f"{_submissions_path(team, oversized_milestone)}/file",
        files={"file": ("over.pdf", exact_payload + b"x", "application/pdf")},
        headers=_headers(student),
    )

    assert exact.status_code == 201
    assert exact.json()["file_size_bytes"] == MAX_FILE_SIZE_BYTES
    assert over_limit.status_code == 413
    assert db_session.scalar(select(func.count()).select_from(MilestoneSubmission)) == 1
    assert len(list(tmp_path.iterdir())) == 1


def test_database_constraints_and_trigger_preserve_version_immutability(
    db_session: OrmSession,
) -> None:
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    milestone = _new_milestone(db_session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))
    submission = MilestoneSubmission(milestone_id=milestone.id)
    db_session.add(submission)
    db_session.flush()
    version = SubmissionVersion(
        submission_id=submission.id,
        version_number=1,
        submitted_by=student.id,
        submitted_at=datetime(2026, 11, 30, 15, tzinfo=UTC),
        deadline_at_submission=datetime(2026, 12, 1, 15, tzinfo=UTC),
        is_late=False,
        source_type="link",
        url="https://example.org/srs",
    )
    db_session.add(version)
    db_session.flush()
    db_session.commit()

    with pytest.raises(DBAPIError):
        db_session.execute(
            text(
                "UPDATE submission_versions SET is_late = true WHERE id = :version_id"
            ),
            {"version_id": version.id},
        )
    db_session.rollback()
    persisted = db_session.get(SubmissionVersion, version.id)
    assert persisted is not None
    assert persisted.is_late is False

    with pytest.raises(DBAPIError):
        db_session.execute(
            text("DELETE FROM submission_versions WHERE id = :version_id"),
            {"version_id": version.id},
        )
    db_session.rollback()
    assert db_session.get(SubmissionVersion, version.id) is not None


def test_database_rejects_versions_that_contain_both_source_types(
    db_session: OrmSession,
) -> None:
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    milestone = _new_milestone(db_session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))
    submission = MilestoneSubmission(milestone_id=milestone.id)
    db_session.add(submission)
    db_session.flush()
    db_session.add(
        SubmissionVersion(
            submission_id=submission.id,
            version_number=1,
            submitted_by=student.id,
            submitted_at=datetime(2026, 11, 30, 15, tzinfo=UTC),
            deadline_at_submission=datetime(2026, 12, 1, 15, tzinfo=UTC),
            is_late=False,
            source_type="file",
            storage_key="a" * 32,
            original_filename="Synthetic-SRS.pdf",
            file_size_bytes=128,
            media_type="application/pdf",
            url="https://example.org/srs",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_database_enforces_submission_version_foreign_keys(
    db_session: OrmSession,
) -> None:
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    milestone = _new_milestone(db_session, team, datetime(2026, 12, 1, 15, tzinfo=UTC))
    submission = MilestoneSubmission(milestone_id=milestone.id)
    db_session.add(submission)
    db_session.flush()
    submission_id = submission.id
    db_session.commit()

    db_session.add(
        SubmissionVersion(
            submission_id=uuid4(),
            version_number=1,
            submitted_by=student.id,
            submitted_at=datetime(2026, 11, 30, 15, tzinfo=UTC),
            deadline_at_submission=datetime(2026, 12, 1, 15, tzinfo=UTC),
            is_late=False,
            source_type="link",
            url="https://example.org/srs",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    db_session.add(
        SubmissionVersion(
            submission_id=submission_id,
            version_number=1,
            submitted_by=uuid4(),
            submitted_at=datetime(2026, 11, 30, 15, tzinfo=UTC),
            deadline_at_submission=datetime(2026, 12, 1, 15, tzinfo=UTC),
            is_late=False,
            source_type="link",
            url="https://example.org/srs",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_cross_team_milestone_and_unknown_submission_ids_are_not_disclosed(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    student_a = _new_user(db_session)
    student_b = _new_user(db_session)
    team_a = _new_team(db_session, student_a, "Synthetic Team A")
    team_b = _new_team(db_session, student_b, "Synthetic Team B")
    milestone_a = _new_milestone(
        db_session, team_a, datetime(2026, 12, 1, 15, tzinfo=UTC)
    )

    mismatch = _new_link(api_client, team_b, milestone_a, student_b)
    missing = api_client.get(
        f"{_submissions_path(team_a, milestone_a)}/{uuid4()}",
        headers=_headers(student_a),
    )

    assert mismatch.status_code == 404
    assert missing.status_code == 404


def test_concurrent_first_submissions_create_exactly_one_version(
    independent_api_sessions: None,
    committed_submission_scenario: tuple[User, User, Team, Milestone],
    postgres_engine: Engine,
) -> None:
    student, _coordinator, team, milestone = committed_submission_scenario
    path = f"{_submissions_path(team, milestone)}/link"
    headers = _headers(student)

    def submit() -> int:
        client = TestClient(app)
        try:
            return client.post(
                path,
                json={"url": "https://example.org/synthetic-srs"},
                headers=headers,
            ).status_code
        finally:
            client.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))

    assert sorted(results) == [201, 409]
    with SessionLocal() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(MilestoneSubmission)
                .where(MilestoneSubmission.milestone_id == milestone.id)
            )
            == 1
        )
        assert session.scalar(select(func.count()).select_from(SubmissionVersion)) == 1


def test_deadline_update_competing_with_submission_preserves_locked_snapshot(
    independent_api_sessions: None,
    committed_submission_scenario: tuple[User, User, Team, Milestone],
    postgres_engine: Engine,
) -> None:
    student, coordinator, team, milestone = committed_submission_scenario
    submission_at_lock = Event()
    allow_submission_commit = Event()
    deadline_update_started = Event()

    def pause_submission_commit(session: OrmSession) -> None:
        if any(
            isinstance(item, MilestoneSubmission)
            for item in session.identity_map.values()
        ):
            submission_at_lock.set()
            if not allow_submission_commit.wait(10):
                raise TimeoutError("submission commit gate timed out")

    def pause_deadline_update(
        _connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        if statement.lstrip().upper().startswith("UPDATE MILESTONES SET DUE_AT"):
            deadline_update_started.set()

    event.listen(OrmSession, "before_commit", pause_submission_commit)
    event.listen(engine, "before_cursor_execute", pause_deadline_update)
    try:

        def submit() -> int:
            client = TestClient(app)
            try:
                response = client.post(
                    f"{_submissions_path(team, milestone)}/link",
                    json={"url": "https://example.org/synthetic-srs"},
                    headers=_headers(student),
                )
                return response.status_code
            finally:
                client.close()

        def edit_deadline() -> int:
            client = TestClient(app)
            try:
                response = client.patch(
                    f"/teams/{team.id}/milestones/{milestone.id}",
                    json={"due_at": "2026-11-30T15:00:00Z"},
                    headers=_headers(coordinator),
                )
                return response.status_code
            finally:
                client.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            submission_future = pool.submit(submit)
            assert submission_at_lock.wait(10)
            deadline_future = pool.submit(edit_deadline)
            assert deadline_update_started.wait(10)
            allow_submission_commit.set()
            submission_status = submission_future.result(timeout=10)
            deadline_status = deadline_future.result(timeout=10)
    finally:
        allow_submission_commit.set()
        event.remove(OrmSession, "before_commit", pause_submission_commit)
        event.remove(engine, "before_cursor_execute", pause_deadline_update)

    assert submission_status == 201
    assert deadline_status == 200
    with SessionLocal() as session:
        version = session.scalar(select(SubmissionVersion))
        updated_milestone = session.get(Milestone, milestone.id)
        assert version is not None
        assert version.deadline_at_submission == datetime(2026, 12, 1, 15, tzinfo=UTC)
        assert version.is_late is False
        assert updated_milestone is not None
        assert updated_milestone.due_at == datetime(2026, 11, 30, 15, tzinfo=UTC)


def test_submission_lock_refreshes_deadline_changed_after_access_check(
    committed_submission_scenario: tuple[User, User, Team, Milestone],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    student, _coordinator, team, milestone = committed_submission_scenario
    submission_time = datetime(2026, 12, 1, 16, tzinfo=UTC)
    new_deadline = datetime(2026, 12, 2, 15, tzinfo=UTC)
    monkeypatch.setattr(submissions, "_now_utc", lambda: submission_time)

    with SessionLocal() as submission_session:
        current_user = submission_session.get(User, student.id)
        assert current_user is not None
        access = submissions._submission_access(
            team.id,
            milestone.id,
            current_user,
            submission_session,
        )
        assert access.milestone.due_at == datetime(2026, 12, 1, 15, tzinfo=UTC)

        with SessionLocal() as deadline_session:
            changed = deadline_session.get(Milestone, milestone.id)
            assert changed is not None
            changed.due_at = new_deadline
            deadline_session.commit()

        response = submissions._create_initial_submission(
            access,
            source_type="link",
            url="https://example.org/synthetic-srs",
        )

    assert response.deadline_at_submission == new_deadline
    assert response.is_late is False


def test_submission_rechecks_active_account_after_access_check(
    committed_submission_scenario: tuple[User, User, Team, Milestone],
) -> None:
    student, _coordinator, team, milestone = committed_submission_scenario

    with SessionLocal() as submission_session:
        current_user = submission_session.get(User, student.id)
        assert current_user is not None
        access = submissions._submission_access(
            team.id,
            milestone.id,
            current_user,
            submission_session,
        )

        with SessionLocal() as account_session:
            account = account_session.get(User, student.id)
            assert account is not None
            account.is_active = False
            account_session.commit()

        with pytest.raises(HTTPException) as rejected:
            submissions._create_initial_submission(
                access,
                source_type="link",
                url="https://example.org/synthetic-srs",
            )

    assert rejected.value.status_code == 401
