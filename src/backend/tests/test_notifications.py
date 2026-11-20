"""PostgreSQL integration and authorization tests for Phase 7B in-app reminders."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from app import security
from app.auth import get_db_session
from app.main import app
from app.models import (
    Milestone,
    MilestoneSubmission,
    SubmissionVersion,
    SupervisorReview,
    Task,
    Team,
    TeamMembership,
    User,
)
from app.supervisor_assignments import assign_supervisor
from fastapi.testclient import TestClient
from sqlalchemy import text
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


def _new_user(
    session: OrmSession,
    role: str = "student",
    display_name: str | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        email=f"{role}.{uuid4().hex}@example.test",
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


def _new_milestone(
    session: OrmSession,
    team: Team,
    due_at: datetime,
    name: str = "Synthetic Milestone",
) -> Milestone:
    milestone = Milestone(team_id=team.id, name=name, due_at=due_at)
    session.add(milestone)
    session.flush()
    return milestone


def _new_task(
    session: OrmSession,
    team: Team,
    creator: User,
    assignee: User,
    title: str = "Synthetic Task",
    status: str = "todo",
    priority: str = "medium",
    due_at: datetime | None = None,
) -> Task:
    comp_by = assignee.id if status == "done" else None
    comp_at = datetime.now(timezone.utc) if status == "done" else None

    task = Task(
        team_id=team.id,
        title=title,
        status=status,
        priority=priority,
        created_by=creator.id,
        assignee_id=assignee.id,
        updated_by=creator.id,
        due_at=due_at,
        completed_by=comp_by,
        completed_at=comp_at,
    )
    session.add(task)
    session.flush()
    return task


def _headers(user: User) -> dict[str, str]:
    token = security.create_access_token(user.id)
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# GT-30: In-App Deadline Reminders Tests
# ===========================================================================


def test_notifications_active_student_assigned_task_and_team_milestone(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 12, 10, 12, 0, 0, tzinfo=timezone.utc)
    from app import notifications

    monkeypatch.setattr(notifications, "_now_utc", lambda: fixed_now)

    leader = _new_user(db_session, display_name="Leader Omar")
    member = _new_user(db_session, display_name="Member Layla")
    team = _new_team(db_session, leader, name="Alpha Team")
    _add_team_member(db_session, team, member)

    # Task 1 assigned to leader (due in 2 days)
    _new_task(
        db_session,
        team,
        creator=leader,
        assignee=leader,
        title="Leader Architecture Task",
        due_at=fixed_now + timedelta(days=2),
    )

    # Task 2 assigned to member (due in 3 days)
    _new_task(
        db_session,
        team,
        creator=leader,
        assignee=member,
        title="Member Frontend Task",
        due_at=fixed_now + timedelta(days=3),
    )

    # Team milestone (due in 4 days)
    _new_milestone(
        db_session,
        team,
        name="Team Sprint 1 Milestone",
        due_at=fixed_now + timedelta(days=4),
    )

    # 1. Leader inbox: sees own task and team milestone, NOT member's task
    res_leader = api_client.get("/notifications", headers=_headers(leader))
    assert res_leader.status_code == 200
    leader_items = res_leader.json()
    assert len(leader_items) == 2
    leader_titles = [i["title"] for i in leader_items]
    assert "Leader Architecture Task" in leader_titles
    assert "Team Sprint 1 Milestone" in leader_titles
    assert "Member Frontend Task" not in leader_titles

    # 2. Member inbox: sees own task and team milestone, NOT leader's task
    res_member = api_client.get("/notifications", headers=_headers(member))
    assert res_member.status_code == 200
    member_items = res_member.json()
    assert len(member_items) == 2
    member_titles = [i["title"] for i in member_items]
    assert "Member Frontend Task" in member_titles
    assert "Team Sprint 1 Milestone" in member_titles
    assert "Leader Architecture Task" not in member_titles


def test_notifications_milestone_review_states_and_done_tasks(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 12, 10, 12, 0, 0, tzinfo=timezone.utc)
    from app import notifications

    monkeypatch.setattr(notifications, "_now_utc", lambda: fixed_now)

    leader = _new_user(db_session, display_name="Leader Khaled")
    supervisor = _new_user(db_session, "supervisor", display_name="Dr. Supervisor")
    team = _new_team(db_session, leader)
    assign_supervisor(db_session, team.id, supervisor.id)

    # Milestone 1: not submitted -> actionable, shown
    _new_milestone(
        db_session, team, name="M1 Not Submitted", due_at=fixed_now + timedelta(days=2)
    )

    # Milestone 2: submitted and pending review -> not actionable for students
    m2 = _new_milestone(
        db_session, team, name="M2 Pending Review", due_at=fixed_now + timedelta(days=3)
    )
    sub2 = MilestoneSubmission(milestone_id=m2.id, review_status="pending_review")
    db_session.add(sub2)
    db_session.flush()

    # Milestone 3: returned by supervisor -> actionable, shown
    m3 = _new_milestone(
        db_session, team, name="M3 Returned", due_at=fixed_now + timedelta(days=4)
    )
    sub3 = MilestoneSubmission(milestone_id=m3.id, review_status="returned")
    db_session.add(sub3)
    db_session.flush()

    # Milestone 4: approved by supervisor -> not actionable, hidden
    m4 = _new_milestone(
        db_session, team, name="M4 Approved", due_at=fixed_now + timedelta(days=5)
    )
    sub4 = MilestoneSubmission(milestone_id=m4.id, review_status="approved")
    db_session.add(sub4)
    db_session.flush()

    # Task 1: done -> not actionable, hidden
    _new_task(
        db_session,
        team,
        creator=leader,
        assignee=leader,
        title="Completed Task",
        due_at=fixed_now + timedelta(days=1),
        status="done",
    )

    # Task 2: no due date -> hidden
    _new_task(
        db_session,
        team,
        creator=leader,
        assignee=leader,
        title="No Deadline Task",
        due_at=None,
    )

    # Task 3: distant deadline (> 7 days) -> hidden
    _new_task(
        db_session,
        team,
        creator=leader,
        assignee=leader,
        title="Distant Task",
        due_at=fixed_now + timedelta(days=8),
    )

    res = api_client.get("/notifications", headers=_headers(leader))
    assert res.status_code == 200
    items = res.json()
    titles = [i["title"] for i in items]

    assert "M1 Not Submitted" in titles
    assert "M3 Returned" in titles
    assert "M2 Pending Review" not in titles
    assert "M4 Approved" not in titles
    assert "Completed Task" not in titles
    assert "No Deadline Task" not in titles
    assert "Distant Task" not in titles


def test_notifications_overdue_and_due_soon_boundaries(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 12, 10, 12, 0, 0, tzinfo=timezone.utc)
    from app import notifications

    monkeypatch.setattr(notifications, "_now_utc", lambda: fixed_now)

    student = _new_user(db_session, display_name="Student Hana")
    team = _new_team(db_session, student)

    # 1. Exactly at deadline -> due_soon
    _new_task(
        db_session,
        team,
        student,
        student,
        title="Task Exact Deadline",
        due_at=fixed_now,
    )

    # 2. Overdue task (1 second ago) -> overdue
    _new_task(
        db_session,
        team,
        student,
        student,
        title="Task Overdue",
        due_at=fixed_now - timedelta(seconds=1),
    )

    # 3. Exactly at 7 days -> due_soon
    _new_task(
        db_session,
        team,
        student,
        student,
        title="Task Exact 7 Days",
        due_at=fixed_now + timedelta(days=7),
    )

    # 4. Beyond 7 days (7 days + 1 second) -> excluded
    _new_task(
        db_session,
        team,
        student,
        student,
        title="Task Beyond 7 Days",
        due_at=fixed_now + timedelta(days=7, seconds=1),
    )

    res = api_client.get("/notifications", headers=_headers(student))
    assert res.status_code == 200
    items = res.json()
    item_map = {i["title"]: i for i in items}

    assert "Task Exact Deadline" in item_map
    assert item_map["Task Exact Deadline"]["kind"] == "task_due_soon"

    assert "Task Overdue" in item_map
    assert item_map["Task Overdue"]["kind"] == "task_overdue"

    assert "Task Exact 7 Days" in item_map
    assert item_map["Task Exact 7 Days"]["kind"] == "task_due_soon"

    assert "Task Beyond 7 Days" not in item_map


def test_notifications_mark_read_and_unread_filter(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 12, 10, 12, 0, 0, tzinfo=timezone.utc)
    from app import notifications

    monkeypatch.setattr(notifications, "_now_utc", lambda: fixed_now)

    student = _new_user(db_session)
    team = _new_team(db_session, student)

    _new_task(
        db_session,
        team,
        student,
        student,
        "Task One",
        due_at=fixed_now + timedelta(days=1),
    )
    _new_task(
        db_session,
        team,
        student,
        student,
        "Task Two",
        due_at=fixed_now + timedelta(days=2),
    )

    # 1. Fetch initial: both unread
    res1 = api_client.get("/notifications", headers=_headers(student))
    assert res1.status_code == 200
    items1 = res1.json()
    assert len(items1) == 2
    assert all(not i["is_read"] for i in items1)

    t1_rem_id = next(i["id"] for i in items1 if i["title"] == "Task One")
    t2_rem_id = next(i["id"] for i in items1 if i["title"] == "Task Two")

    # 2. Mark t1 read
    post_res = api_client.post(
        f"/notifications/{t1_rem_id}/read", headers=_headers(student)
    )
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["status"] == "ok"
    assert post_data["reminder_id"] == t1_rem_id
    assert post_data["read_at"] is not None

    # Idempotent repeat call returns 200
    repeat_res = api_client.post(
        f"/notifications/{t1_rem_id}/read", headers=_headers(student)
    )
    assert repeat_res.status_code == 200
    assert repeat_res.json()["read_at"] == post_data["read_at"]

    # Database count check
    count = db_session.scalar(
        text(
            "SELECT count(*) FROM notification_read_receipts "
            "WHERE user_id = :u AND reminder_id = :r"
        ),
        {"u": student.id, "r": t1_rem_id},
    )
    assert count == 1

    # 3. Fetch with unread_only=true
    unread_res = api_client.get(
        "/notifications?unread_only=true", headers=_headers(student)
    )
    assert unread_res.status_code == 200
    unread_items = unread_res.json()
    assert len(unread_items) == 1
    assert unread_items[0]["id"] == t2_rem_id
    assert not unread_items[0]["is_read"]

    # 4. Fetch all: t1 is read, t2 is unread
    all_res = api_client.get("/notifications", headers=_headers(student))
    assert all_res.status_code == 200
    all_map = {i["id"]: i for i in all_res.json()}
    assert all_map[t1_rem_id]["is_read"] is True
    assert all_map[t1_rem_id]["read_at"] is not None
    assert all_map[t2_rem_id]["is_read"] is False


def test_notifications_deadline_change_invalidates_stale_reminder(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 12, 10, 12, 0, 0, tzinfo=timezone.utc)
    from app import notifications

    monkeypatch.setattr(notifications, "_now_utc", lambda: fixed_now)

    student = _new_user(db_session)
    team = _new_team(db_session, student)

    task = _new_task(
        db_session,
        team,
        student,
        student,
        "Dynamic Task",
        due_at=fixed_now + timedelta(days=2),
    )

    # 1. Fetch initial reminder & mark read
    res1 = api_client.get("/notifications", headers=_headers(student))
    assert res1.status_code == 200
    initial_rem_id = res1.json()[0]["id"]

    mark_res = api_client.post(
        f"/notifications/{initial_rem_id}/read", headers=_headers(student)
    )
    assert mark_res.status_code == 200

    # 2. Update task deadline to another date within window
    task.due_at = fixed_now + timedelta(days=5)
    db_session.commit()

    # 3. New fetch: new reminder ID generated, starts UNREAD
    res2 = api_client.get("/notifications", headers=_headers(student))
    assert res2.status_code == 200
    items2 = res2.json()
    assert len(items2) == 1
    new_rem_id = items2[0]["id"]
    assert new_rem_id != initial_rem_id
    assert items2[0]["is_read"] is False

    # 4. Marking the old stale reminder ID returns 404
    stale_res = api_client.post(
        f"/notifications/{initial_rem_id}/read", headers=_headers(student)
    )
    assert stale_res.status_code == 404

    # 5. Update task deadline beyond 7 days -> reminder disappears
    task.due_at = fixed_now + timedelta(days=12)
    db_session.commit()

    res3 = api_client.get("/notifications", headers=_headers(student))
    assert res3.status_code == 200
    assert res3.json() == []


def test_notifications_authorization_and_isolation(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 12, 10, 12, 0, 0, tzinfo=timezone.utc)
    from app import notifications

    monkeypatch.setattr(notifications, "_now_utc", lambda: fixed_now)

    student1 = _new_user(db_session, display_name="Student 1")
    student2 = _new_user(db_session, display_name="Student 2")
    inactive_student = _new_user(db_session, display_name="Inactive", is_active=False)
    supervisor = _new_user(db_session, "supervisor")
    coordinator = _new_user(db_session, "coordinator")

    team1 = _new_team(db_session, student1, name="Team 1")
    _new_task(
        db_session,
        team1,
        student1,
        student1,
        "Team 1 Task",
        due_at=fixed_now + timedelta(days=2),
    )

    # 1. Unauthenticated -> 401
    assert api_client.get("/notifications").status_code == 401
    assert api_client.post(f"/notifications/{uuid4()}/read").status_code == 401

    # 2. Inactive student -> 401 (rejected at auth layer)
    assert (
        api_client.get("/notifications", headers=_headers(inactive_student)).status_code
        == 401
    )

    # 3. Supervisor -> 403
    assert (
        api_client.get("/notifications", headers=_headers(supervisor)).status_code
        == 403
    )
    assert (
        api_client.post(
            f"/notifications/{uuid4()}/read", headers=_headers(supervisor)
        ).status_code
        == 403
    )

    # 4. Coordinator -> 403
    assert (
        api_client.get("/notifications", headers=_headers(coordinator)).status_code
        == 403
    )

    # 5. Student in no team -> returns []
    orphan_student = _new_user(db_session, display_name="Orphan Student")
    orphan_res = api_client.get("/notifications", headers=_headers(orphan_student))
    assert orphan_res.status_code == 200
    assert orphan_res.json() == []

    # 6. Student 2 cannot see Team 1's reminders or mark them read
    s1_rem_id = api_client.get("/notifications", headers=_headers(student1)).json()[0][
        "id"
    ]

    s2_res = api_client.get("/notifications", headers=_headers(student2))
    assert s2_res.status_code == 200
    assert s2_res.json() == []

    s2_mark = api_client.post(
        f"/notifications/{s1_rem_id}/read", headers=_headers(student2)
    )
    assert s2_mark.status_code == 404

    # 7. Nonexistent reminder ID -> 404
    assert (
        api_client.post(
            f"/notifications/{uuid4()}/read", headers=_headers(student1)
        ).status_code
        == 404
    )


def test_notifications_cross_phase_e2e(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full lifecycle: register, team, tasks, milestone review, revisions."""
    fixed_now = datetime(2026, 12, 10, 12, 0, 0, tzinfo=timezone.utc)
    from app import notifications

    monkeypatch.setattr(notifications, "_now_utc", lambda: fixed_now)

    # Register two students
    s1 = _new_user(db_session, display_name="Student One")
    s2 = _new_user(db_session, display_name="Student Two")
    sup = _new_user(db_session, "supervisor", display_name="Supervisor Dr")

    # Create team
    team = _new_team(db_session, s1, name="GradTrack Cohort")
    _add_team_member(db_session, team, s2)
    assign_supervisor(db_session, team.id, sup.id)

    # Assign task to s1
    task = _new_task(
        db_session,
        team,
        creator=s1,
        assignee=s1,
        title="Backend Auth Module",
        due_at=fixed_now + timedelta(days=2),
    )

    # Supervisor creates milestone
    ms = _new_milestone(
        db_session,
        team,
        name="Phase 7 Prototype",
        due_at=fixed_now + timedelta(days=3),
    )

    # 1. Fetch reminders for s1: has task and milestone
    r1 = api_client.get("/notifications", headers=_headers(s1)).json()
    assert len(r1) == 2
    task_rem = next(i for i in r1 if i["title"] == "Backend Auth Module")
    assert task_rem["is_read"] is False
    ms_rem = next(i for i in r1 if i["title"] == "Phase 7 Prototype")

    # Mark milestone read
    mark_res = api_client.post(
        f"/notifications/{ms_rem['id']}/read", headers=_headers(s1)
    )
    assert mark_res.status_code == 200

    # 2. Milestone deadline extended to 4 days
    ms.due_at = fixed_now + timedelta(days=4)
    db_session.commit()

    # Old reminder is stale, new reminder is unread
    r2 = api_client.get("/notifications", headers=_headers(s1)).json()
    new_ms_rem = next(i for i in r2 if i["title"] == "Phase 7 Prototype")
    assert new_ms_rem["id"] != ms_rem["id"]
    assert new_ms_rem["is_read"] is False

    # 3. Student submits milestone -> pending_review
    sub = MilestoneSubmission(milestone_id=ms.id, review_status="pending_review")
    db_session.add(sub)
    db_session.flush()
    v1 = SubmissionVersion(
        submission_id=sub.id,
        version_number=1,
        submitted_by=s1.id,
        submitted_at=fixed_now,
        deadline_at_submission=ms.due_at,
        is_late=False,
        source_type="link",
        url="https://example.test/submission-v1",
    )
    db_session.add(v1)
    db_session.commit()

    # Milestone disappears from student reminders while pending review
    r3 = api_client.get("/notifications", headers=_headers(s1)).json()
    assert len(r3) == 1
    assert r3[0]["title"] == "Backend Auth Module"

    # 4. Supervisor returns the submission -> actionable again
    sub.review_status = "returned"
    rev = SupervisorReview(
        version_id=v1.id,
        reviewer_id=sup.id,
        decision="returned",
        feedback="Please add diagram and revision log",
        reviewed_at=fixed_now,
    )
    db_session.add(rev)
    db_session.commit()

    # Milestone reappears in student reminders
    r4 = api_client.get("/notifications", headers=_headers(s1)).json()
    assert len(r4) == 2
    assert any(i["title"] == "Phase 7 Prototype" for i in r4)

    # 5. Supervisor approves submission -> removed from reminders permanently
    sub.review_status = "approved"
    db_session.commit()

    r5 = api_client.get("/notifications", headers=_headers(s1)).json()
    assert len(r5) == 1
    assert r5[0]["title"] == "Backend Auth Module"

    # 6. Close task (status='done') -> removed from reminders
    task.status = "done"
    db_session.commit()

    r6 = api_client.get("/notifications", headers=_headers(s1)).json()
    assert r6 == []
