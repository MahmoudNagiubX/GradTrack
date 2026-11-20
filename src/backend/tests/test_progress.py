"""PostgreSQL integration and authorization tests for Phase 7A."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

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
    milestone: Milestone | None = None,
    parent_task: Task | None = None,
) -> Task:
    task = Task(
        team_id=team.id,
        title=title,
        status=status,
        priority=priority,
        created_by=creator.id,
        assignee_id=assignee.id,
        updated_by=creator.id,
        due_at=due_at,
        milestone_id=milestone.id if milestone else None,
        parent_task_id=parent_task.id if parent_task else None,
    )
    if status == "done":
        task.completed_by = assignee.id
        task.completed_at = datetime.now(timezone.utc)
    session.add(task)
    session.flush()
    return task


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {security.create_access_token(user.id)}"}


# ===========================================================================
# GT-29: Calendar / Timeline Integration Tests
# ===========================================================================


def test_calendar_mixed_tasks_and_milestones(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    leader = _new_user(db_session, display_name="Leader Layla")
    member = _new_user(db_session, display_name="Member Ziad")
    supervisor = _new_user(db_session, "supervisor")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)
    assign_supervisor(db_session, team.id, supervisor.id)

    window_start = datetime(2026, 12, 1, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2026, 12, 31, 0, 0, tzinfo=timezone.utc)

    # 1. Tasks: in-range, out-of-range, undated, and subtask
    t1 = _new_task(
        db_session,
        team,
        leader,
        member,
        title="Task In Range 1",
        due_at=datetime(2026, 12, 10, 12, 0, tzinfo=timezone.utc),
    )
    t2 = _new_task(
        db_session,
        team,
        leader,
        member,
        title="Task In Range 2",
        due_at=datetime(2026, 12, 20, 15, 0, tzinfo=timezone.utc),
    )
    _new_task(
        db_session,
        team,
        leader,
        member,
        title="Task Past Out",
        due_at=datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc),
    )
    _new_task(
        db_session,
        team,
        leader,
        member,
        title="Task Future Out",
        due_at=datetime(2027, 1, 15, 10, 0, tzinfo=timezone.utc),
    )
    _new_task(
        db_session,
        team,
        leader,
        member,
        title="Task No Due Date",
        due_at=None,
    )
    # Subtask of t1, in range
    subtask = _new_task(
        db_session,
        team,
        leader,
        member,
        title="Subtask In Range",
        due_at=datetime(2026, 12, 8, 9, 0, tzinfo=timezone.utc),
        parent_task=t1,
    )

    # 2. Milestones: in-range, out-of-range
    m1 = _new_milestone(
        db_session,
        team,
        due_at=datetime(2026, 12, 15, 18, 0, tzinfo=timezone.utc),
        name="Milestone In Range",
    )
    _new_milestone(
        db_session,
        team,
        due_at=datetime(2027, 1, 10, 18, 0, tzinfo=timezone.utc),
        name="Milestone Out of Range",
    )

    db_session.commit()

    # Query calendar
    res = api_client.get(
        f"/teams/{team.id}/calendar",
        params={
            "start_at": window_start.isoformat(),
            "end_at": window_end.isoformat(),
        },
        headers=_headers(leader),
    )
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 4

    # Ordering check: subtask (Dec 8), t1 (Dec 10), m1 (Dec 15), t2 (Dec 20)
    assert items[0]["id"] == str(subtask.id)
    assert items[0]["kind"] == "task"
    assert items[0]["parent_task_id"] == str(t1.id)

    assert items[1]["id"] == str(t1.id)
    assert items[1]["kind"] == "task"

    assert items[2]["id"] == str(m1.id)
    assert items[2]["kind"] == "milestone"
    assert items[2]["title"] == "Milestone In Range"
    assert items[2]["review_status"] == "not_submitted"

    assert items[3]["id"] == str(t2.id)
    assert items[3]["kind"] == "task"


def test_calendar_exact_half_open_boundaries_and_timezones(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    leader = _new_user(db_session)
    member = _new_user(db_session)
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)

    start_instant = datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)
    end_instant = datetime(2026, 12, 10, 12, 0, tzinfo=timezone.utc)

    # Item exactly at start_at -> MUST be included
    at_start = _new_task(
        db_session,
        team,
        leader,
        member,
        title="At Start Task",
        due_at=start_instant,
    )
    # Item exactly at end_at -> MUST be excluded (half-open [start, end))
    at_end = _new_task(
        db_session,
        team,
        leader,
        member,
        title="At End Task",
        due_at=end_instant,
    )
    db_session.commit()

    # Query using Cairo (+02:00) timezone query params
    cairo_tz = ZoneInfo("Africa/Cairo")
    cairo_start = start_instant.astimezone(cairo_tz)  # 2026-12-01 14:00+02:00
    cairo_end = end_instant.astimezone(cairo_tz)  # 2026-12-10 14:00+02:00

    res = api_client.get(
        f"/teams/{team.id}/calendar",
        params={
            "start_at": cairo_start.isoformat(),
            "end_at": cairo_end.isoformat(),
        },
        headers=_headers(member),
    )
    assert res.status_code == 200
    items = res.json()
    item_ids = [i["id"] for i in items]
    assert str(at_start.id) in item_ids
    assert str(at_end.id) not in item_ids


def test_calendar_validation_and_range_limits(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    leader = _new_user(db_session)
    team = _new_team(db_session, leader)
    db_session.commit()

    base_time = datetime(2026, 12, 1, 10, 0, tzinfo=timezone.utc)

    # 1. start_at == end_at rejected
    r1 = api_client.get(
        f"/teams/{team.id}/calendar",
        params={
            "start_at": base_time.isoformat(),
            "end_at": base_time.isoformat(),
        },
        headers=_headers(leader),
    )
    assert r1.status_code == 422
    assert "start_at must be before end_at" in r1.text

    # 2. start_at > end_at rejected
    r2 = api_client.get(
        f"/teams/{team.id}/calendar",
        params={
            "start_at": (base_time + timedelta(days=5)).isoformat(),
            "end_at": base_time.isoformat(),
        },
        headers=_headers(leader),
    )
    assert r2.status_code == 422

    # 3. range > 93 days rejected
    r3 = api_client.get(
        f"/teams/{team.id}/calendar",
        params={
            "start_at": base_time.isoformat(),
            "end_at": (base_time + timedelta(days=94)).isoformat(),
        },
        headers=_headers(leader),
    )
    assert r3.status_code == 422
    assert "93 days" in r3.text

    # 4. Naive datetime rejected
    r4 = api_client.get(
        f"/teams/{team.id}/calendar",
        params={
            "start_at": "2026-12-01T10:00:00",
            "end_at": "2026-12-10T10:00:00",
        },
        headers=_headers(leader),
    )
    assert r4.status_code == 422


def test_calendar_authorization_and_isolation(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    leader = _new_user(db_session)
    member = _new_user(db_session)
    supervisor = _new_user(db_session, "supervisor")
    other_supervisor = _new_user(db_session, "supervisor")
    coordinator = _new_user(db_session, "coordinator")
    outsider = _new_user(db_session)

    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)
    assign_supervisor(db_session, team.id, supervisor.id)
    db_session.commit()

    params = {
        "start_at": "2026-12-01T00:00:00Z",
        "end_at": "2026-12-15T00:00:00Z",
    }

    # Member, leader, supervisor, coordinator allowed
    for viewer in [member, leader, supervisor, coordinator]:
        res = api_client.get(
            f"/teams/{team.id}/calendar",
            params=params,
            headers=_headers(viewer),
        )
        assert res.status_code == 200

    # Outside student denied with 404
    assert (
        api_client.get(
            f"/teams/{team.id}/calendar",
            params=params,
            headers=_headers(outsider),
        ).status_code
        == 404
    )

    # Unassigned supervisor denied with 404
    assert (
        api_client.get(
            f"/teams/{team.id}/calendar",
            params=params,
            headers=_headers(other_supervisor),
        ).status_code
        == 404
    )


# ===========================================================================
# GT-31: Student / Team Progress Summary Integration Tests
# ===========================================================================


def test_team_progress_empty_team(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    leader = _new_user(db_session, display_name="Leader Empty")
    member = _new_user(db_session, display_name="Member Empty")
    team = _new_team(db_session, leader, name="Empty Team")
    _add_team_member(db_session, team, member)
    db_session.commit()

    res = api_client.get(f"/teams/{team.id}/progress", headers=_headers(leader))
    assert res.status_code == 200
    data = res.json()
    assert data["team_id"] == str(team.id)
    assert data["team_name"] == "Empty Team"
    assert data["tasks"]["total"] == 0
    assert data["tasks"]["overdue"] == 0
    assert data["milestones"]["total"] == 0
    assert data["milestones"]["not_submitted"] == 0
    assert data["late_submissions"] == 0
    assert data["upcoming"] == []

    # Assignee breakdown includes all team members with 0 counts
    assignees = data["tasks_by_assignee"]
    assert len(assignees) == 2
    assert {a["assignee_name"] for a in assignees} == {
        "Leader Empty",
        "Member Empty",
    }
    assert all(a["total"] == 0 for a in assignees)


def test_team_progress_tasks_lifecycle_and_overdue_boundaries(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 12, 10, 12, 0, tzinfo=timezone.utc)
    from app import progress

    monkeypatch.setattr(progress, "_now_utc", lambda: fixed_now)

    leader = _new_user(db_session, display_name="Leader Tamer")
    m1 = _new_user(db_session, display_name="Member Adel")
    m2 = _new_user(db_session, display_name="Member Bassem")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, m1)
    _add_team_member(db_session, team, m2)

    # 1. m1 has 1 todo (future), 1 in_progress (past -> overdue)
    _new_task(
        db_session,
        team,
        leader,
        m1,
        title="Future Todo",
        status="todo",
        due_at=fixed_now + timedelta(days=2),
    )
    _new_task(
        db_session,
        team,
        leader,
        m1,
        title="Overdue In Progress",
        status="in_progress",
        due_at=fixed_now - timedelta(days=1),
    )

    # 2. m2 has 1 done (past due -> NOT overdue), 1 done (future)
    _new_task(
        db_session,
        team,
        leader,
        m2,
        title="Done Past",
        status="done",
        due_at=fixed_now - timedelta(days=3),
    )
    _new_task(
        db_session,
        team,
        leader,
        m2,
        title="Done Future",
        status="done",
        due_at=fixed_now + timedelta(days=5),
    )

    # 3. Leader has 1 task exactly at deadline -> NOT overdue (due_at < now required)
    _new_task(
        db_session,
        team,
        leader,
        leader,
        title="Exact Deadline Todo",
        status="todo",
        due_at=fixed_now,
    )

    db_session.commit()

    res = api_client.get(f"/teams/{team.id}/progress", headers=_headers(m1))
    assert res.status_code == 200
    data = res.json()

    tasks = data["tasks"]
    assert tasks["total"] == 5
    assert tasks["todo"] == 2
    assert tasks["in_progress"] == 1
    assert tasks["done"] == 2
    assert tasks["overdue"] == 1  # only Overdue In Progress

    # Check per-assignee counts
    by_assignee = {a["assignee_name"]: a for a in data["tasks_by_assignee"]}
    assert by_assignee["Member Adel"]["total"] == 2
    assert by_assignee["Member Adel"]["overdue"] == 1
    assert by_assignee["Member Bassem"]["total"] == 2
    assert by_assignee["Member Bassem"]["done"] == 2
    assert by_assignee["Member Bassem"]["overdue"] == 0
    assert by_assignee["Leader Tamer"]["total"] == 1
    assert by_assignee["Leader Tamer"]["overdue"] == 0


def test_team_progress_milestones_and_late_submissions(
    api_client: TestClient,
    db_session: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 12, 10, 12, 0, tzinfo=timezone.utc)
    from app import progress

    monkeypatch.setattr(progress, "_now_utc", lambda: fixed_now)

    leader = _new_user(db_session)
    member = _new_user(db_session)
    supervisor = _new_user(db_session, "supervisor")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)
    assign_supervisor(db_session, team.id, supervisor.id)

    # Milestone 1: scheduled (> 7 days future), not submitted
    _new_milestone(
        db_session,
        team,
        due_at=fixed_now + timedelta(days=10),
        name="Scheduled Milestone",
    )

    # Milestone 2: due_soon (<= 7 days future), submitted on time, pending_review
    m2 = _new_milestone(
        db_session,
        team,
        due_at=fixed_now + timedelta(days=3),
        name="Due Soon Milestone",
    )
    sub2 = MilestoneSubmission(milestone_id=m2.id, review_status="pending_review")
    db_session.add(sub2)
    db_session.flush()
    v1_m2 = SubmissionVersion(
        submission_id=sub2.id,
        version_number=1,
        submitted_by=member.id,
        submitted_at=fixed_now - timedelta(hours=2),
        deadline_at_submission=m2.due_at,
        is_late=False,
        source_type="link",
        url="https://example.test/spec",
    )
    db_session.add(v1_m2)

    # Milestone 3: overdue, v1 was late and returned, v2 was late and approved
    m3 = _new_milestone(
        db_session,
        team,
        due_at=fixed_now - timedelta(days=2),
        name="Overdue Milestone",
    )
    sub3 = MilestoneSubmission(milestone_id=m3.id, review_status="approved")
    db_session.add(sub3)
    db_session.flush()
    v1_m3 = SubmissionVersion(
        submission_id=sub3.id,
        version_number=1,
        submitted_by=member.id,
        submitted_at=fixed_now - timedelta(days=1),
        deadline_at_submission=m3.due_at,
        is_late=True,
        source_type="link",
        url="https://example.test/v1",
    )
    v2_m3 = SubmissionVersion(
        submission_id=sub3.id,
        version_number=2,
        submitted_by=member.id,
        submitted_at=fixed_now - timedelta(hours=5),
        deadline_at_submission=m3.due_at,
        is_late=True,
        source_type="link",
        url="https://example.test/v2",
    )
    db_session.add_all([v1_m3, v2_m3])
    db_session.flush()
    rev = SupervisorReview(
        version_id=v2_m3.id,
        reviewer_id=supervisor.id,
        decision="approved",
        feedback="Approved final version",
        reviewed_at=fixed_now - timedelta(hours=1),
    )
    db_session.add(rev)
    db_session.commit()

    res = api_client.get(f"/teams/{team.id}/progress", headers=_headers(leader))
    assert res.status_code == 200
    data = res.json()

    ms = data["milestones"]
    assert ms["total"] == 3
    assert ms["scheduled"] == 1
    assert ms["due_soon"] == 1
    assert ms["overdue"] == 1

    # Review status
    assert ms["not_submitted"] == 1
    assert ms["pending_review"] == 1
    assert ms["returned"] == 0
    assert ms["approved"] == 1

    # late_submissions counts latest version per milestone (m3 latest is late -> 1)
    assert data["late_submissions"] == 1


# ===========================================================================
# GT-37: Supervisor Assigned-Team Progress Integration Tests
# ===========================================================================


def test_supervisor_teams_progress_multiple_teams(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    sup1 = _new_user(db_session, "supervisor", display_name="Dr. Supervisor One")
    sup2 = _new_user(db_session, "supervisor", display_name="Dr. Supervisor Two")
    student1 = _new_user(db_session, display_name="Student Alpha")
    student2 = _new_user(db_session, display_name="Student Beta")
    student3 = _new_user(db_session, display_name="Student Gamma")

    # Team Alpha and Team Beta assigned to sup1
    team_a = _new_team(db_session, student1, name="Team Alpha")
    team_b = _new_team(db_session, student2, name="Team Beta")
    # Team Gamma assigned to sup2
    team_c = _new_team(db_session, student3, name="Team Gamma")

    assign_supervisor(db_session, team_a.id, sup1.id)
    assign_supervisor(db_session, team_b.id, sup1.id)
    assign_supervisor(db_session, team_c.id, sup2.id)

    _new_task(db_session, team_a, student1, student1, title="Task Alpha")
    _new_task(db_session, team_b, student2, student2, title="Task Beta")
    _new_task(db_session, team_c, student3, student3, title="Task Gamma")
    db_session.commit()

    # sup1 queries assigned teams progress
    res = api_client.get("/supervisor/teams/progress", headers=_headers(sup1))
    assert res.status_code == 200
    summaries = res.json()
    assert len(summaries) == 2
    team_names = [s["team_name"] for s in summaries]
    assert team_names == ["Team Alpha", "Team Beta"]
    assert "Team Gamma" not in team_names

    # sup2 queries assigned teams progress
    res2 = api_client.get("/supervisor/teams/progress", headers=_headers(sup2))
    assert res2.status_code == 200
    summaries2 = res2.json()
    assert len(summaries2) == 1
    assert summaries2[0]["team_name"] == "Team Gamma"


def test_supervisor_teams_progress_reassignment_and_empty(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    sup1 = _new_user(db_session, "supervisor")
    sup2 = _new_user(db_session, "supervisor")
    student = _new_user(db_session)
    team = _new_team(db_session, student, name="Moving Team")

    # Unassigned supervisor gets empty list
    empty_res = api_client.get("/supervisor/teams/progress", headers=_headers(sup1))
    assert empty_res.status_code == 200
    assert empty_res.json() == []

    # Assign to sup1
    assign_supervisor(db_session, team.id, sup1.id)
    db_session.commit()

    res1 = api_client.get("/supervisor/teams/progress", headers=_headers(sup1))
    assert res1.status_code == 200
    assert len(res1.json()) == 1
    assert res1.json()[0]["team_id"] == str(team.id)

    # Reassign team to sup2
    assign_supervisor(db_session, team.id, sup2.id)
    db_session.commit()

    # Former supervisor sup1 immediately gets empty list
    former_res = api_client.get("/supervisor/teams/progress", headers=_headers(sup1))
    assert former_res.status_code == 200
    assert former_res.json() == []

    # New supervisor sup2 sees the team
    new_res = api_client.get("/supervisor/teams/progress", headers=_headers(sup2))
    assert new_res.status_code == 200
    assert len(new_res.json()) == 1


def test_supervisor_teams_progress_authorization(
    api_client: TestClient,
    db_session: OrmSession,
) -> None:
    student = _new_user(db_session, "student")
    coordinator = _new_user(db_session, "coordinator")
    inactive_supervisor = _new_user(db_session, "supervisor", is_active=False)
    db_session.commit()

    # Students denied (403)
    r1 = api_client.get("/supervisor/teams/progress", headers=_headers(student))
    assert r1.status_code == 403

    # Coordinator denied (403, coordinator is not automatically a supervisor)
    r2 = api_client.get("/supervisor/teams/progress", headers=_headers(coordinator))
    assert r2.status_code == 403

    # Inactive supervisor denied (401 from token/active check)
    r3 = api_client.get(
        "/supervisor/teams/progress", headers=_headers(inactive_supervisor)
    )
    assert r3.status_code == 401
