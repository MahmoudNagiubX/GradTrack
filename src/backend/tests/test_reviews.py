"""PostgreSQL-backed supervisor review and returned-version workflows."""

from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from app import security, submissions
from app.auth import get_db_session
from app.database import SessionLocal
from app.main import app
from app.models import (
    Milestone,
    MilestoneSubmission,
    SubmissionVersion,
    SupervisorReview,
    Team,
    TeamMembership,
    User,
)
from app.supervisor_assignments import assign_supervisor
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
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


@pytest.fixture
def independent_api_sessions() -> Generator[None, None, None]:
    def override_db_session() -> Generator[OrmSession, None, None]:
        with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    try:
        yield
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
    due_at: datetime | None = None,
    name: str = "Synthetic SRS",
) -> Milestone:
    milestone = Milestone(
        team_id=team.id,
        name=name,
        due_at=due_at or datetime(2026, 12, 1, 15, tzinfo=UTC),
    )
    session.add(milestone)
    session.flush()
    return milestone


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {security.create_access_token(user.id)}"}


def _submissions_path(team: Team, milestone: Milestone) -> str:
    return f"/teams/{team.id}/milestones/{milestone.id}/submissions"


def _review_path(team: Team, milestone: Milestone, version_id: str) -> str:
    return f"{_submissions_path(team, milestone)}/{version_id}/review"


def _submit_link(
    client: TestClient,
    team: Team,
    milestone: Milestone,
    student: User,
    *,
    revision: bool = False,
    url: str = "https://example.org/synthetic-srs",
):
    suffix = "/revisions/link" if revision else "/link"
    return client.post(
        f"{_submissions_path(team, milestone)}{suffix}",
        json={"url": url},
        headers=_headers(student),
    )


def _review(
    client: TestClient,
    team: Team,
    milestone: Milestone,
    version_id: str,
    supervisor: User,
    decision: str,
    feedback: str | None = None,
):
    return client.post(
        _review_path(team, milestone, version_id),
        json={"decision": decision, "feedback": feedback},
        headers=_headers(supervisor),
    )


def _create_pending_submission(
    client: TestClient,
    session: OrmSession,
    supervisor: User,
    name: str = "Synthetic Review Team",
) -> tuple[User, Team, Milestone, dict]:
    student = _new_user(session)
    team = _new_team(session, student, name)
    milestone = _new_milestone(session, team)
    assign_supervisor(session, team.id, supervisor.id)
    response = _submit_link(client, team, milestone, student)
    assert response.status_code == 201
    return student, team, milestone, response.json()


def test_pending_inbox_is_current_supervisor_scoped_and_includes_review_context(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    another_supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, version = _create_pending_submission(
        api_client, db_session, supervisor, "Assigned Team"
    )
    other_student = _new_user(db_session)
    other_team = _new_team(db_session, other_student, "Other Team")
    other_milestone = _new_milestone(db_session, other_team)
    assign_supervisor(db_session, other_team.id, another_supervisor.id)
    other_submission = _submit_link(
        api_client, other_team, other_milestone, other_student
    )
    assert other_submission.status_code == 201

    history = api_client.get(
        _submissions_path(team, milestone), headers=_headers(student)
    )
    inbox = api_client.get(
        "/supervisor/submissions/pending", headers=_headers(supervisor)
    )
    other_inbox = api_client.get(
        "/supervisor/submissions/pending", headers=_headers(another_supervisor)
    )

    assert inbox.status_code == 200
    assert len(inbox.json()) == 1
    assert history.status_code == 200
    assert history.json()[0]["review_status"] == "pending_review"
    item = inbox.json()[0]
    assert item["id"] == version["id"]
    assert item["version_number"] == 1
    assert item["submitted_by"] == str(student.id)
    assert item["team_id"] == str(team.id)
    assert item["team_name"] == "Assigned Team"
    assert item["milestone_id"] == str(milestone.id)
    assert item["milestone_name"] == "Synthetic SRS"
    assert item["submitter_name"] == student.display_name
    assert item["review_status"] == "pending_review"
    assert item["is_late"] is False
    assert "storage_key" not in item
    assert db_session.scalar(select(func.count()).select_from(SupervisorReview)) == 0
    parent = db_session.scalar(
        select(MilestoneSubmission).where(
            MilestoneSubmission.milestone_id == milestone.id
        )
    )
    assert parent is not None and parent.review_status == "pending_review"
    assert other_inbox.status_code == 200
    assert [row["id"] for row in other_inbox.json()] == [other_submission.json()["id"]]


def test_pending_inbox_is_empty_for_unassigned_supervisor_and_forbidden_to_students(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student = _new_user(db_session)

    empty = api_client.get(
        "/supervisor/submissions/pending", headers=_headers(supervisor)
    )
    forbidden = api_client.get(
        "/supervisor/submissions/pending", headers=_headers(student)
    )

    assert empty.status_code == 200
    assert empty.json() == []
    assert forbidden.status_code == 403


def test_return_records_version_scoped_feedback_and_returned_status(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, version = _create_pending_submission(
        api_client, db_session, supervisor
    )

    returned = _review(
        api_client,
        team,
        milestone,
        version["id"],
        supervisor,
        "returned",
        "  Revise the evaluation section.  ",
    )
    history = api_client.get(
        _submissions_path(team, milestone), headers=_headers(student)
    )
    review = api_client.get(
        _review_path(team, milestone, version["id"]), headers=_headers(student)
    )
    parent = db_session.scalar(
        select(MilestoneSubmission).where(
            MilestoneSubmission.milestone_id == milestone.id
        )
    )

    assert returned.status_code == 201
    assert returned.json()["decision"] == "returned"
    assert returned.json()["feedback"] == "Revise the evaluation section."
    assert returned.json()["reviewer_id"] == str(supervisor.id)
    assert returned.json()["reviewed_at"].endswith("Z")
    assert history.status_code == 200
    assert history.json()[0]["review_status"] == "returned"
    assert review.status_code == 200
    assert review.json()["feedback"] == "Revise the evaluation section."
    assert parent is not None and parent.review_status == "returned"


def test_approval_is_final_and_optional_blank_feedback_is_null(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, version = _create_pending_submission(
        api_client, db_session, supervisor
    )

    approved = _review(
        api_client, team, milestone, version["id"], supervisor, "approved", "  "
    )
    duplicate = _review(
        api_client, team, milestone, version["id"], supervisor, "approved", "Again"
    )
    revision = _submit_link(api_client, team, milestone, student, revision=True)
    history = api_client.get(
        _submissions_path(team, milestone), headers=_headers(student)
    )

    assert approved.status_code == 201
    assert approved.json()["feedback"] is None
    assert duplicate.status_code == 409
    assert revision.status_code == 409
    assert [row["review_status"] for row in history.json()] == ["approved"]


def test_returned_version_can_be_revised_and_statuses_remain_version_specific(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, first = _create_pending_submission(
        api_client, db_session, supervisor
    )
    returned = _review(
        api_client,
        team,
        milestone,
        first["id"],
        supervisor,
        "returned",
        "Fix section 2.",
    )
    feedback = api_client.get(
        _review_path(team, milestone, first["id"]), headers=_headers(student)
    )
    revision = _submit_link(
        api_client,
        team,
        milestone,
        student,
        revision=True,
        url="https://example.org/synthetic-srs-v2",
    )
    after_revision = api_client.get(
        _submissions_path(team, milestone), headers=_headers(student)
    )
    approved = _review(
        api_client,
        team,
        milestone,
        revision.json()["id"],
        supervisor,
        "approved",
        "Accepted.",
    )
    after_approval = api_client.get(
        _submissions_path(team, milestone), headers=_headers(student)
    )
    first_review = api_client.get(
        _review_path(team, milestone, first["id"]), headers=_headers(student)
    )
    second_review = api_client.get(
        _review_path(team, milestone, revision.json()["id"]),
        headers=_headers(student),
    )

    assert returned.status_code == 201
    assert feedback.status_code == 200
    assert feedback.json()["feedback"] == "Fix section 2."
    assert revision.status_code == 201
    assert revision.json()["version_number"] == 2
    assert after_revision.status_code == 200
    assert [row["review_status"] for row in after_revision.json()] == [
        "returned",
        "pending_review",
    ]
    assert after_revision.json()[0]["url"] == first["url"]
    assert after_revision.json()[1]["url"] == "https://example.org/synthetic-srs-v2"
    assert approved.status_code == 201
    assert [row["review_status"] for row in after_approval.json()] == [
        "returned",
        "approved",
    ]
    assert first_review.json()["decision"] == "returned"
    assert second_review.json()["decision"] == "approved"


def test_pending_version_cannot_be_replaced_and_stale_version_cannot_be_reviewed(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, first = _create_pending_submission(
        api_client, db_session, supervisor
    )
    while_pending = _submit_link(api_client, team, milestone, student, revision=True)
    returned = _review(
        api_client, team, milestone, first["id"], supervisor, "returned", "Revise."
    )
    second = _submit_link(api_client, team, milestone, student, revision=True)
    stale_review = _review(
        api_client,
        team,
        milestone,
        first["id"],
        supervisor,
        "approved",
        None,
    )
    current_review = _review(
        api_client,
        team,
        milestone,
        second.json()["id"],
        supervisor,
        "approved",
        None,
    )

    assert while_pending.status_code == 409
    assert returned.status_code == 201
    assert second.status_code == 201
    assert stale_review.status_code == 409
    assert current_review.status_code == 201


@pytest.mark.parametrize(
    "actor_kind", ["member", "leader", "coordinator", "other_supervisor"]
)
def test_only_current_supervisor_can_decide_a_review(
    actor_kind: str,
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    coordinator = _new_user(db_session, "coordinator")
    supervisor = _new_user(db_session, "supervisor")
    other_supervisor = _new_user(db_session, "supervisor")
    leader = _new_user(db_session)
    team = _new_team(db_session, leader)
    member = _new_user(db_session)
    db_session.add(TeamMembership(team_id=team.id, user_id=member.id, role="member"))
    milestone = _new_milestone(db_session, team)
    assign_supervisor(db_session, team.id, supervisor.id)
    version = _submit_link(api_client, team, milestone, leader).json()
    actor = {
        "member": member,
        "leader": leader,
        "coordinator": coordinator,
        "other_supervisor": other_supervisor,
    }[actor_kind]

    rejected = _review(
        api_client, team, milestone, version["id"], actor, "returned", "Revise."
    )

    assert rejected.status_code in {403, 404}
    parent = db_session.scalar(
        select(MilestoneSubmission).where(
            MilestoneSubmission.milestone_id == milestone.id
        )
    )
    assert parent is not None and parent.review_status == "pending_review"
    assert db_session.scalar(select(func.count()).select_from(SupervisorReview)) == 0


def test_reassignment_removes_former_supervisor_inbox_and_review_access(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    coordinator = _new_user(db_session, "coordinator")
    former = _new_user(db_session, "supervisor")
    current = _new_user(db_session, "supervisor")
    student, team, milestone, version = _create_pending_submission(
        api_client, db_session, former
    )
    former_inbox = api_client.get(
        "/supervisor/submissions/pending", headers=_headers(former)
    )
    reassigned = api_client.put(
        f"/teams/{team.id}/supervisor",
        json={"supervisor_id": str(current.id)},
        headers=_headers(coordinator),
    )
    old_inbox = api_client.get(
        "/supervisor/submissions/pending", headers=_headers(former)
    )
    current_inbox = api_client.get(
        "/supervisor/submissions/pending", headers=_headers(current)
    )
    old_review = _review(api_client, team, milestone, version["id"], former, "approved")
    new_review = _review(
        api_client, team, milestone, version["id"], current, "returned", "Revise."
    )

    assert former_inbox.status_code == 200 and len(former_inbox.json()) == 1
    assert reassigned.status_code == 200
    assert old_inbox.json() == []
    assert [row["id"] for row in current_inbox.json()] == [version["id"]]
    assert old_review.status_code == 404
    assert new_review.status_code == 201


def test_disabled_supervisor_cannot_review(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    _student, team, milestone, version = _create_pending_submission(
        api_client, db_session, supervisor
    )
    supervisor.is_active = False
    db_session.flush()

    rejected = _review(
        api_client, team, milestone, version["id"], supervisor, "approved"
    )

    assert rejected.status_code == 401


def test_review_is_team_scoped_and_absent_review_is_not_disclosed(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, version = _create_pending_submission(
        api_client, db_session, supervisor
    )
    wrong_team = _new_team(db_session, student, "Different Team")
    wrong_milestone = _new_milestone(db_session, wrong_team, name="Different Milestone")
    absent = api_client.get(
        _review_path(team, milestone, version["id"]), headers=_headers(student)
    )
    mismatched = api_client.get(
        _review_path(wrong_team, wrong_milestone, version["id"]),
        headers=_headers(student),
    )

    assert absent.status_code == 404
    assert mismatched.status_code == 404


def test_review_read_cannot_mix_an_authorized_team_with_another_teams_milestone(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student_a = _new_user(db_session)
    team_a = _new_team(db_session, student_a, "Authorized Team")
    _student_b, team_b, milestone_b, version_b = _create_pending_submission(
        api_client, db_session, supervisor, "Other Team"
    )
    assert (
        _review(
            api_client,
            team_b,
            milestone_b,
            version_b["id"],
            supervisor,
            "returned",
            "Update.",
        ).status_code
        == 201
    )

    mismatched = api_client.get(
        _review_path(team_a, milestone_b, version_b["id"]),
        headers=_headers(student_a),
    )

    assert mismatched.status_code == 404


def test_returned_file_revision_is_private_and_downloadable(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, first = _create_pending_submission(
        api_client, db_session, supervisor
    )
    assert (
        _review(
            api_client, team, milestone, first["id"], supervisor, "returned", "Update."
        ).status_code
        == 201
    )
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(tmp_path))

    revision = api_client.post(
        f"{_submissions_path(team, milestone)}/revisions/file",
        files={"file": ("Synthetic-Revision.txt", b"Updated report", "text/plain")},
        headers=_headers(student),
    )
    download = api_client.get(
        f"{_submissions_path(team, milestone)}/{revision.json()['id']}/download",
        headers=_headers(student),
    )
    versions = api_client.get(
        _submissions_path(team, milestone), headers=_headers(student)
    )

    assert revision.status_code == 201
    assert revision.json()["version_number"] == 2
    assert download.status_code == 200
    assert download.content == b"Updated report"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["cache-control"] == "no-store"
    assert [row["review_status"] for row in versions.json()] == [
        "returned",
        "pending_review",
    ]


def test_invalid_revision_file_keeps_returned_history_unchanged(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, first = _create_pending_submission(
        api_client, db_session, supervisor
    )
    _review(api_client, team, milestone, first["id"], supervisor, "returned", "Update.")
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(tmp_path))

    invalid = api_client.post(
        f"{_submissions_path(team, milestone)}/revisions/file",
        files={"file": ("Synthetic-Revision.pdf", b"not a PDF", "application/pdf")},
        headers=_headers(student),
    )
    history = api_client.get(
        _submissions_path(team, milestone), headers=_headers(student)
    )
    parent = db_session.scalar(
        select(MilestoneSubmission).where(
            MilestoneSubmission.milestone_id == milestone.id
        )
    )

    assert invalid.status_code == 422
    assert [row["version_number"] for row in history.json()] == [1]
    assert history.json()[0]["review_status"] == "returned"
    assert parent is not None and parent.review_status == "returned"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "failure,expected_status",
    [
        ("oversize", 413),
        ("extension", 422),
        ("signature", 422),
        ("multipart", 422),
    ],
)
def test_revision_validation_failures_leave_returned_history_unchanged(
    failure: str,
    expected_status: int,
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.submission_storage import MAX_FILE_SIZE_BYTES

    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, first = _create_pending_submission(
        api_client, db_session, supervisor
    )
    _review(api_client, team, milestone, first["id"], supervisor, "returned", "Update.")
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(tmp_path))
    path = f"{_submissions_path(team, milestone)}/revisions/file"

    if failure == "oversize":
        response = api_client.post(
            path,
            files={
                "file": (
                    "Synthetic-Revision.txt",
                    b"x" * (MAX_FILE_SIZE_BYTES + 1),
                    "text/plain",
                )
            },
            headers=_headers(student),
        )
    elif failure == "extension":
        response = api_client.post(
            path,
            files={"file": ("Synthetic-Revision.exe", b"unsafe", "text/plain")},
            headers=_headers(student),
        )
    elif failure == "signature":
        response = api_client.post(
            path,
            files={"file": ("Synthetic-Revision.pdf", b"not a PDF", "application/pdf")},
            headers=_headers(student),
        )
    else:
        response = api_client.post(
            path,
            data={"unexpected": "field"},
            files={"file": ("Synthetic-Revision.txt", b"Updated", "text/plain")},
            headers=_headers(student),
        )

    history = api_client.get(
        _submissions_path(team, milestone), headers=_headers(student)
    )
    parent = db_session.scalar(
        select(MilestoneSubmission).where(
            MilestoneSubmission.milestone_id == milestone.id
        )
    )

    assert response.status_code == expected_status
    assert [row["version_number"] for row in history.json()] == [1]
    assert history.json()[0]["review_status"] == "returned"
    assert parent is not None and parent.review_status == "returned"
    assert list(tmp_path.iterdir()) == []


def test_revision_database_failure_removes_promoted_file_and_preserves_returned_state(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, first = _create_pending_submission(
        api_client, db_session, supervisor
    )
    _review(api_client, team, milestone, first["id"], supervisor, "returned", "Update.")
    monkeypatch.setenv("GRADTRACK_PRIVATE_UPLOAD_DIR", str(tmp_path))

    def fail_commit(_session: OrmSession) -> None:
        raise SQLAlchemyError("synthetic database failure")

    monkeypatch.setattr(OrmSession, "commit", fail_commit)
    response = api_client.post(
        f"{_submissions_path(team, milestone)}/revisions/file",
        files={"file": ("Synthetic-Revision.txt", b"Updated report", "text/plain")},
        headers=_headers(student),
    )
    history = api_client.get(
        _submissions_path(team, milestone), headers=_headers(student)
    )
    parent = db_session.scalar(
        select(MilestoneSubmission).where(
            MilestoneSubmission.milestone_id == milestone.id
        )
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Submission could not be saved"}
    assert [row["version_number"] for row in history.json()] == [1]
    assert parent is not None and parent.review_status == "returned"
    assert list(tmp_path.iterdir()) == []


def test_invalid_revision_link_keeps_returned_state(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, first = _create_pending_submission(
        api_client, db_session, supervisor
    )
    _review(api_client, team, milestone, first["id"], supervisor, "returned", "Update.")

    invalid = api_client.post(
        f"{_submissions_path(team, milestone)}/revisions/link",
        json={"url": "http://localhost/private"},
        headers=_headers(student),
    )

    assert invalid.status_code == 422
    parent = db_session.scalar(
        select(MilestoneSubmission).where(
            MilestoneSubmission.milestone_id == milestone.id
        )
    )
    assert parent is not None and parent.review_status == "returned"


@pytest.mark.parametrize(
    "offset_microseconds,expected_late", [(-1, False), (0, False), (1, True)]
)
def test_revision_uses_new_deadline_snapshot_and_preserves_old_lateness(
    offset_microseconds: int,
    expected_late: bool,
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _new_user(db_session, "coordinator")
    supervisor = _new_user(db_session, "supervisor")
    student = _new_user(db_session)
    team = _new_team(db_session, student)
    old_deadline = datetime(2026, 12, 1, 15, tzinfo=UTC)
    new_deadline = datetime(2026, 12, 2, 15, tzinfo=UTC)
    milestone = _new_milestone(db_session, team, old_deadline)
    assign_supervisor(db_session, team.id, supervisor.id)
    submission_times = iter(
        [
            old_deadline + timedelta(microseconds=1),
            new_deadline + timedelta(microseconds=offset_microseconds),
        ]
    )
    monkeypatch.setattr(submissions, "_now_utc", lambda: next(submission_times))
    first = _submit_link(api_client, team, milestone, student)
    assert first.status_code == 201
    assert first.json()["is_late"] is True
    assert (
        _review(
            api_client,
            team,
            milestone,
            first.json()["id"],
            supervisor,
            "returned",
            "Update.",
        ).status_code
        == 201
    )
    changed = api_client.patch(
        f"/teams/{team.id}/milestones/{milestone.id}",
        json={"due_at": new_deadline.isoformat()},
        headers=_headers(coordinator),
    )
    revision = _submit_link(api_client, team, milestone, student, revision=True)
    history = api_client.get(
        _submissions_path(team, milestone), headers=_headers(student)
    )

    assert changed.status_code == 200
    assert revision.status_code == 201
    assert revision.json()["deadline_at_submission"] == "2026-12-02T15:00:00Z"
    assert revision.json()["is_late"] is expected_late
    assert history.json()[0]["deadline_at_submission"] == "2026-12-01T15:00:00Z"
    assert history.json()[0]["is_late"] is True


def test_inactive_student_cannot_resubmit(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, first = _create_pending_submission(
        api_client, db_session, supervisor
    )
    assert (
        _review(
            api_client, team, milestone, first["id"], supervisor, "returned", "Update."
        ).status_code
        == 201
    )
    student.is_active = False
    db_session.flush()

    rejected = _submit_link(api_client, team, milestone, student, revision=True)

    assert rejected.status_code == 401
    parent = db_session.scalar(
        select(MilestoneSubmission).where(
            MilestoneSubmission.milestone_id == milestone.id
        )
    )
    assert parent is not None and parent.review_status == "returned"


def test_unassigned_team_has_no_reviewer_and_cross_team_review_ids_are_hidden(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student_a = _new_user(db_session)
    student_b = _new_user(db_session)
    team_a = _new_team(db_session, student_a, "Unassigned Team")
    team_b = _new_team(db_session, student_b, "Other Team")
    milestone_a = _new_milestone(db_session, team_a)
    milestone_b = _new_milestone(db_session, team_b)
    version = _submit_link(api_client, team_a, milestone_a, student_a).json()

    inbox = api_client.get(
        "/supervisor/submissions/pending", headers=_headers(supervisor)
    )
    cross_team = _review(
        api_client, team_b, milestone_b, version["id"], supervisor, "approved"
    )
    wrong_team_history = api_client.get(
        _review_path(team_b, milestone_b, version["id"]),
        headers=_headers(student_b),
    )

    assert inbox.status_code == 200 and inbox.json() == []
    assert cross_team.status_code == 404
    assert wrong_team_history.status_code == 404


def test_database_enforces_review_constraints_and_immutability(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    student, team, milestone, version = _create_pending_submission(
        api_client, db_session, supervisor
    )
    approved = _review(
        api_client, team, milestone, version["id"], supervisor, "approved", "Accepted."
    )
    review_id = approved.json()["id"]

    with pytest.raises(DBAPIError):
        db_session.execute(
            text("UPDATE supervisor_reviews SET feedback = 'forged' WHERE id = :id"),
            {"id": review_id},
        )
    db_session.rollback()
    assert db_session.get(SupervisorReview, review_id).feedback == "Accepted."

    with pytest.raises(DBAPIError):
        db_session.execute(
            text("DELETE FROM supervisor_reviews WHERE id = :id"), {"id": review_id}
        )
    db_session.rollback()
    assert db_session.get(SupervisorReview, review_id) is not None

    second_version = SubmissionVersion(
        submission_id=version["submission_id"],
        version_number=2,
        submitted_by=student.id,
        submitted_at=datetime(2026, 12, 1, 17, tzinfo=UTC),
        deadline_at_submission=datetime(2026, 12, 1, 15, tzinfo=UTC),
        is_late=True,
        source_type="link",
        url="https://example.org/synthetic-srs-v2",
    )
    db_session.add(second_version)
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.add(
            SupervisorReview(
                version_id=second_version.id,
                reviewer_id=supervisor.id,
                decision="returned",
                feedback=None,
                reviewed_at=datetime(2026, 12, 1, 18, tzinfo=UTC),
            )
        )
        db_session.flush()
    db_session.rollback()

    with pytest.raises(IntegrityError):
        db_session.add(
            SupervisorReview(
                version_id=version["id"],
                reviewer_id=supervisor.id,
                decision="returned",
                feedback="Duplicate review",
                reviewed_at=datetime(2026, 12, 1, 16, tzinfo=UTC),
            )
        )
        db_session.flush()
    db_session.rollback()


def test_review_foreign_keys_are_enforced(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    supervisor = _new_user(db_session, "supervisor")
    _student, _team, _milestone, version = _create_pending_submission(
        api_client, db_session, supervisor
    )
    timestamp = datetime(2026, 12, 1, 16, tzinfo=UTC)

    db_session.add(
        SupervisorReview(
            version_id=uuid4(),
            reviewer_id=supervisor.id,
            decision="approved",
            feedback=None,
            reviewed_at=timestamp,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    db_session.add(
        SupervisorReview(
            version_id=version["id"],
            reviewer_id=uuid4(),
            decision="approved",
            feedback=None,
            reviewed_at=timestamp,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_full_team_submission_review_return_and_approval_flow(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    email = f"phase5b.student.{uuid4().hex}@example.com"
    password = "synthetic-phase5b-passphrase"
    registered = api_client.post(
        "/auth/register",
        json={
            "email": email,
            "display_name": "Synthetic Phase 5B Student",
            "password": password,
        },
    )
    login = api_client.post("/auth/login", json={"email": email, "password": password})
    assert registered.status_code == 201
    assert login.status_code == 200
    student = db_session.scalar(select(User).where(User.email == email))
    coordinator = _new_user(db_session, "coordinator")
    supervisor = _new_user(db_session, "supervisor")
    student_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created_team = api_client.post(
        "/teams", json={"name": "E2E Synthetic Team"}, headers=student_headers
    )
    team_id = created_team.json()["id"]
    assigned = api_client.put(
        f"/teams/{team_id}/supervisor",
        json={"supervisor_id": str(supervisor.id)},
        headers=_headers(coordinator),
    )
    milestone_response = api_client.post(
        f"/teams/{team_id}/milestones",
        json={"name": "E2E SRS", "due_at": "2026-12-15T12:00:00Z"},
        headers=_headers(coordinator),
    )
    team = db_session.get(Team, team_id)
    milestone = db_session.get(Milestone, milestone_response.json()["id"])
    assert team is not None and milestone is not None
    first = api_client.post(
        f"{_submissions_path(team, milestone)}/link",
        json={"url": "https://example.org/e2e-synthetic-srs"},
        headers=student_headers,
    )
    inbox = api_client.get(
        "/supervisor/submissions/pending", headers=_headers(supervisor)
    )
    returned = _review(
        api_client,
        team,
        milestone,
        first.json()["id"],
        supervisor,
        "returned",
        "Add the requested test cases.",
    )
    feedback = api_client.get(
        _review_path(team, milestone, first.json()["id"]), headers=student_headers
    )
    second = api_client.post(
        f"{_submissions_path(team, milestone)}/revisions/link",
        json={"url": "https://example.org/e2e-synthetic-srs-v2"},
        headers=student_headers,
    )
    approved = _review(
        api_client,
        team,
        milestone,
        second.json()["id"],
        supervisor,
        "approved",
        "Accepted.",
    )
    history = api_client.get(
        _submissions_path(team, milestone), headers=student_headers
    )
    forbidden = _review(
        api_client, team, milestone, second.json()["id"], student, "approved"
    )

    assert created_team.status_code == 201
    assert registered.status_code == 201
    assert login.status_code == 200
    assert student is not None and student.system_role == "student"
    assert assigned.status_code == 200
    assert milestone_response.status_code == 201
    assert first.status_code == 201
    assert [item["id"] for item in inbox.json()] == [first.json()["id"]]
    assert returned.status_code == 201
    assert feedback.json()["feedback"] == "Add the requested test cases."
    assert second.status_code == 201
    assert second.json()["version_number"] == 2
    assert approved.status_code == 201
    assert [item["review_status"] for item in history.json()] == [
        "returned",
        "approved",
    ]
    assert forbidden.status_code == 403


@pytest.fixture
def committed_review_scenario(postgres_engine: Engine):
    with SessionLocal() as session:
        student = _new_user(session)
        coordinator = _new_user(session, "coordinator")
        supervisor = _new_user(session, "supervisor")
        team = _new_team(session, student, "Concurrent Review Team")
        milestone = _new_milestone(session, team)
        assign_supervisor(session, team.id, supervisor.id)
        session.commit()
        student_id = student.id
        coordinator_id = coordinator.id
        supervisor_id = supervisor.id
        team_id, milestone_id = team.id, milestone.id
        scenario = (student, coordinator, supervisor, team, milestone)

    try:
        yield scenario
    finally:
        with postgres_engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE supervisor_reviews DISABLE TRIGGER "
                "trg_supervisor_reviews_immutable"
            )
            connection.exec_driver_sql(
                "ALTER TABLE submission_versions DISABLE TRIGGER "
                "trg_submission_versions_immutable"
            )
            try:
                connection.execute(
                    text(
                        "DELETE FROM supervisor_reviews WHERE version_id IN ("
                        "SELECT id FROM submission_versions WHERE submission_id IN ("
                        "SELECT id FROM milestone_submissions "
                        "WHERE milestone_id = :id))"
                    ),
                    {"id": milestone_id},
                )
                connection.execute(
                    text(
                        "DELETE FROM submission_versions WHERE submission_id IN ("
                        "SELECT id FROM milestone_submissions WHERE milestone_id = :id)"
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
                    text("DELETE FROM supervisor_assignments WHERE team_id = :id"),
                    {"id": team_id},
                )
                connection.execute(
                    text("DELETE FROM team_memberships WHERE team_id = :id"),
                    {"id": team_id},
                )
                connection.execute(
                    text("DELETE FROM teams WHERE id = :id"), {"id": team_id}
                )
                connection.execute(
                    text(
                        "DELETE FROM users WHERE id IN "
                        "(:student, :coordinator, :supervisor)"
                    ),
                    {
                        "student": student_id,
                        "coordinator": coordinator_id,
                        "supervisor": supervisor_id,
                    },
                )
            finally:
                connection.exec_driver_sql(
                    "ALTER TABLE submission_versions ENABLE TRIGGER "
                    "trg_submission_versions_immutable"
                )
                connection.exec_driver_sql(
                    "ALTER TABLE supervisor_reviews ENABLE TRIGGER "
                    "trg_supervisor_reviews_immutable"
                )


@pytest.mark.parametrize("action", ["review", "revision"])
def test_concurrent_duplicate_review_or_revision_has_one_winner(
    action: str,
    independent_api_sessions: None,
    committed_review_scenario: tuple[User, User, User, Team, Milestone],
    postgres_engine: Engine,
) -> None:
    student, _coordinator, supervisor, team, milestone = committed_review_scenario
    path = _submissions_path(team, milestone)
    with TestClient(app) as client:
        first = client.post(
            f"{path}/link",
            json={"url": "https://example.org/concurrency-test"},
            headers=_headers(student),
        )
    assert first.status_code == 201
    if action == "revision":
        with TestClient(app) as client:
            returned = _review(
                client,
                team,
                milestone,
                first.json()["id"],
                supervisor,
                "returned",
                "Revise.",
            )
        assert returned.status_code == 201

    def run_action(_index: int) -> int:
        with TestClient(app) as client:
            if action == "review":
                response = _review(
                    client,
                    team,
                    milestone,
                    first.json()["id"],
                    supervisor,
                    "approved",
                )
            else:
                response = _submit_link(client, team, milestone, student, revision=True)
            return response.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run_action, range(2)))

    assert sorted(results) == [201, 409]
    with SessionLocal() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(SupervisorReview)
                .where(SupervisorReview.version_id == first.json()["id"])
            )
            == 1
        )
        assert session.scalar(
            select(func.count())
            .select_from(SubmissionVersion)
            .where(SubmissionVersion.submission_id == first.json()["submission_id"])
        ) == (1 if action == "review" else 2)
