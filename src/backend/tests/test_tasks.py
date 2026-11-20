"""PostgreSQL-backed integration and authorization tests for Phase 6A team tasks."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from app import security
from app.auth import get_db_session
from app.main import app
from app.models import (
    Milestone,
    Task,
    TaskActivity,
    Team,
    TeamMembership,
    User,
)
from app.supervisor_assignments import assign_supervisor
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
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
    due_at: datetime | None = None,
    name: str = "Synthetic Milestone",
) -> Milestone:
    milestone = Milestone(
        team_id=team.id,
        name=name,
        due_at=due_at or datetime(2026, 12, 1, 15, tzinfo=timezone.utc),
    )
    session.add(milestone)
    session.flush()
    return milestone


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {security.create_access_token(user.id)}"}


def test_leader_creates_task_and_views_in_list_and_detail(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Team Leader")
    member = _new_user(db_session, "student", "Assignee Student")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)
    milestone = _new_milestone(db_session, team)

    due = datetime(2026, 12, 15, 12, 0, tzinfo=timezone.utc)
    create_payload = {
        "title": "Build authentication API",
        "description": "Support Argon2id password hashing",
        "assignee_id": str(member.id),
        "priority": "high",
        "due_at": due.isoformat(),
        "estimated_minutes": 180,
        "milestone_id": str(milestone.id),
    }

    # Leader creates task
    res = api_client.post(
        f"/teams/{team.id}/tasks",
        json=create_payload,
        headers=_headers(leader),
    )
    assert res.status_code == 201
    task_data = res.json()
    task_id = task_data["id"]

    assert task_data["title"] == "Build authentication API"
    assert task_data["description"] == "Support Argon2id password hashing"
    assert task_data["status"] == "todo"
    assert task_data["priority"] == "high"
    assert task_data["created_by"] == str(leader.id)
    assert task_data["assignee_id"] == str(member.id)
    assert task_data["updated_by"] == str(leader.id)
    assert task_data["completed_by"] is None
    assert task_data["completed_at"] is None
    assert task_data["estimated_minutes"] == 180
    assert task_data["milestone_id"] == str(milestone.id)
    assert task_data["parent_task_id"] is None

    # List endpoint
    list_res = api_client.get(
        f"/teams/{team.id}/tasks",
        headers=_headers(member),
    )
    assert list_res.status_code == 200
    tasks = list_res.json()
    assert len(tasks) == 1
    assert tasks[0]["id"] == task_id

    # Detail endpoint
    detail_res = api_client.get(
        f"/teams/{team.id}/tasks/{task_id}",
        headers=_headers(member),
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == task_id
    assert detail["checklist_items"] == []
    assert detail["subtasks"] == []

    # Activity history
    activity_res = api_client.get(
        f"/teams/{team.id}/tasks/{task_id}/activity",
        headers=_headers(leader),
    )
    assert activity_res.status_code == 200
    activities = activity_res.json()
    assert len(activities) == 1
    assert activities[0]["event_type"] == "created"
    assert activities[0]["actor_id"] == str(leader.id)
    assert activities[0]["actor_name"] == "Team Leader"
    assert "Assignee Student" in activities[0]["details"]


def test_task_creation_validation_rules(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Leader")
    member = _new_user(db_session, "student", "Member")
    other_student = _new_user(db_session, "student", "Other Student")
    supervisor = _new_user(db_session, "supervisor", "Supervisor")
    inactive_student = _new_user(db_session, "student", "Inactive", is_active=False)
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)
    _add_team_member(db_session, team, inactive_student)

    other_team = _new_team(db_session, other_student, "Other Team")
    other_milestone = _new_milestone(db_session, other_team)

    # 1. Other-team student assignee rejected
    res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={"title": "Test", "assignee_id": str(other_student.id)},
        headers=_headers(leader),
    )
    assert res.status_code == 400
    assert "member of this team" in res.json()["detail"]

    # 2. Supervisor assignee rejected
    res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={"title": "Test", "assignee_id": str(supervisor.id)},
        headers=_headers(leader),
    )
    assert res.status_code == 400
    assert "student account" in res.json()["detail"]

    # 3. Inactive student assignee rejected
    res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={"title": "Test", "assignee_id": str(inactive_student.id)},
        headers=_headers(leader),
    )
    assert res.status_code == 400
    assert "active student account" in res.json()["detail"]

    # 4. Unknown assignee ID rejected
    res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={"title": "Test", "assignee_id": str(uuid4())},
        headers=_headers(leader),
    )
    assert res.status_code == 400

    # 5. Mismatched milestone rejected
    res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={
            "title": "Test",
            "assignee_id": str(member.id),
            "milestone_id": str(other_milestone.id),
        },
        headers=_headers(leader),
    )
    assert res.status_code == 400
    assert "Milestone does not belong to this team" in res.json()["detail"]


def test_task_creation_permissions(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Leader")
    member = _new_user(db_session, "student", "Member")
    supervisor = _new_user(db_session, "supervisor", "Supervisor")
    coordinator = _new_user(db_session, "coordinator", "Coordinator")
    unrelated_student = _new_user(db_session, "student", "Unrelated")

    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)
    assign_supervisor(
        session=db_session,
        team_id=team.id,
        supervisor_id=supervisor.id,
    )

    payload = {"title": "Task A", "assignee_id": str(member.id)}

    # Regular member cannot create task
    res = api_client.post(
        f"/teams/{team.id}/tasks",
        json=payload,
        headers=_headers(member),
    )
    assert res.status_code == 403

    # Assigned supervisor cannot create task
    res = api_client.post(
        f"/teams/{team.id}/tasks",
        json=payload,
        headers=_headers(supervisor),
    )
    assert res.status_code == 403

    # Coordinator cannot create task
    res = api_client.post(
        f"/teams/{team.id}/tasks",
        json=payload,
        headers=_headers(coordinator),
    )
    assert res.status_code == 403

    # Unrelated student cannot access team
    res = api_client.post(
        f"/teams/{team.id}/tasks",
        json=payload,
        headers=_headers(unrelated_student),
    )
    assert res.status_code == 404


def test_task_metadata_update_and_reassignment(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Leader")
    member1 = _new_user(db_session, "student", "Member 1")
    member2 = _new_user(db_session, "student", "Member 2")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member1)
    _add_team_member(db_session, team, member2)
    milestone = _new_milestone(db_session, team)

    create_res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={"title": "Initial Title", "assignee_id": str(member1.id)},
        headers=_headers(leader),
    )
    task_id = create_res.json()["id"]

    # Member cannot edit task metadata
    res = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}",
        json={"title": "Hacked Title"},
        headers=_headers(member1),
    )
    assert res.status_code == 403

    # Leader updates title, priority, due date, estimated minutes, milestone
    new_due = datetime(2026, 12, 20, 10, 0, tzinfo=timezone.utc)
    res = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}",
        json={
            "title": "Updated Title",
            "priority": "low",
            "due_at": new_due.isoformat(),
            "estimated_minutes": 90,
            "milestone_id": str(milestone.id),
        },
        headers=_headers(leader),
    )
    assert res.status_code == 200
    updated = res.json()
    assert updated["title"] == "Updated Title"
    assert updated["priority"] == "low"
    assert updated["estimated_minutes"] == 90
    assert updated["milestone_id"] == str(milestone.id)

    # Leader reassigns to member2
    reassign_res = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}",
        json={"assignee_id": str(member2.id)},
        headers=_headers(leader),
    )
    assert reassign_res.status_code == 200
    assert reassign_res.json()["assignee_id"] == str(member2.id)

    # Check activity events
    activities = api_client.get(
        f"/teams/{team.id}/tasks/{task_id}/activity",
        headers=_headers(leader),
    ).json()
    event_types = [a["event_type"] for a in activities]
    assert event_types == ["created", "updated", "reassigned"]
    reassign_act = activities[2]
    assert reassign_act["old_value"] == str(member1.id)
    assert reassign_act["new_value"] == str(member2.id)
    assert "Member 2" in reassign_act["details"]


def test_task_status_lifecycle_completion_and_reopening(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Leader")
    member = _new_user(db_session, "student", "Member")
    other_member = _new_user(db_session, "student", "Other Member")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)
    _add_team_member(db_session, team, other_member)

    task_res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={"title": "Task Life", "assignee_id": str(member.id)},
        headers=_headers(leader),
    )
    task_id = task_res.json()["id"]

    # Other member cannot change status
    res = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/status",
        json={"status": "in_progress"},
        headers=_headers(other_member),
    )
    assert res.status_code == 403

    # Assignee moves to in_progress
    res = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/status",
        json={"status": "in_progress"},
        headers=_headers(member),
    )
    assert res.status_code == 200
    assert res.json()["status"] == "in_progress"
    assert res.json()["completed_by"] is None
    assert res.json()["completed_at"] is None

    # Idempotent status update produces no new event
    res_noop = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/status",
        json={"status": "in_progress"},
        headers=_headers(member),
    )
    assert res_noop.status_code == 200

    # Assignee marks done
    res_done = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/status",
        json={"status": "done"},
        headers=_headers(member),
    )
    assert res_done.status_code == 200
    done_data = res_done.json()
    assert done_data["status"] == "done"
    assert done_data["completed_by"] == str(member.id)
    assert done_data["completed_at"] is not None

    # Leader can reopen task
    res_reopen = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/status",
        json={"status": "in_progress"},
        headers=_headers(leader),
    )
    assert res_reopen.status_code == 200
    reopen_data = res_reopen.json()
    assert reopen_data["status"] == "in_progress"
    assert reopen_data["completed_by"] is None
    assert reopen_data["completed_at"] is None

    # Check activity sequence: created -> status_changed -> completed -> reopened
    acts = api_client.get(
        f"/teams/{team.id}/tasks/{task_id}/activity",
        headers=_headers(leader),
    ).json()
    event_types = [a["event_type"] for a in acts]
    assert event_types == ["created", "status_changed", "completed", "reopened"]
    assert acts[2]["event_type"] == "completed"
    assert acts[2]["actor_id"] == str(member.id)
    assert acts[3]["event_type"] == "reopened"
    assert acts[3]["actor_id"] == str(leader.id)


def test_removed_or_inactive_assignee_cannot_update_status(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Leader")
    member = _new_user(db_session, "student", "Member")
    team = _new_team(db_session, leader)
    membership = _add_team_member(db_session, team, member)

    task_res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={"title": "Task Removal", "assignee_id": str(member.id)},
        headers=_headers(leader),
    )
    task_id = task_res.json()["id"]

    # Remove membership from team
    db_session.delete(membership)
    db_session.flush()

    # Assignee can no longer mutate task status
    res = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/status",
        json={"status": "in_progress"},
        headers=_headers(member),
    )
    assert res.status_code in (403, 404)

    # Leader can still update status
    leader_res = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/status",
        json={"status": "in_progress"},
        headers=_headers(leader),
    )
    assert leader_res.status_code == 200


def test_one_level_subtasks(api_client: TestClient, db_session: OrmSession) -> None:
    leader = _new_user(db_session, "student", "Leader")
    member = _new_user(db_session, "student", "Member")
    other_leader = _new_user(db_session, "student", "Other Leader")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)
    other_team = _new_team(db_session, other_leader, "Other Team")

    # Create parent task
    parent_res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={"title": "Parent Task", "assignee_id": str(member.id)},
        headers=_headers(leader),
    )
    parent_id = parent_res.json()["id"]

    # Create child task
    child_res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={
            "title": "Child Task 1",
            "assignee_id": str(member.id),
            "parent_task_id": parent_id,
        },
        headers=_headers(leader),
    )
    assert child_res.status_code == 201
    child_id = child_res.json()["id"]
    assert child_res.json()["parent_task_id"] == parent_id

    # Verify detail of parent task lists subtask
    detail = api_client.get(
        f"/teams/{team.id}/tasks/{parent_id}",
        headers=_headers(member),
    ).json()
    assert len(detail["subtasks"]) == 1
    assert detail["subtasks"][0]["id"] == child_id

    # Grandchild creation (child as parent) rejected
    grandchild_res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={
            "title": "Grandchild Task",
            "assignee_id": str(member.id),
            "parent_task_id": child_id,
        },
        headers=_headers(leader),
    )
    assert grandchild_res.status_code == 400
    assert "one level" in grandchild_res.json()["detail"]

    # Self-parenting on update rejected
    self_res = api_client.patch(
        f"/teams/{team.id}/tasks/{parent_id}",
        json={"parent_task_id": parent_id},
        headers=_headers(leader),
    )
    assert self_res.status_code == 400
    assert "own parent" in self_res.json()["detail"]

    # Cross-team parent task rejected
    other_parent = api_client.post(
        f"/teams/{other_team.id}/tasks",
        json={"title": "Other Parent", "assignee_id": str(other_leader.id)},
        headers=_headers(other_leader),
    ).json()
    cross_res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={
            "title": "Cross Child",
            "assignee_id": str(member.id),
            "parent_task_id": other_parent["id"],
        },
        headers=_headers(leader),
    )
    assert cross_res.status_code == 400


def test_checklist_items_lifecycle(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Leader")
    member = _new_user(db_session, "student", "Member")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)

    task_res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={"title": "Checklist Task", "assignee_id": str(member.id)},
        headers=_headers(leader),
    )
    task_id = task_res.json()["id"]

    # Member cannot add checklist item
    add_fail = api_client.post(
        f"/teams/{team.id}/tasks/{task_id}/checklist",
        json={"item_text": "Write tests"},
        headers=_headers(member),
    )
    assert add_fail.status_code == 403

    # Leader adds checklist item
    add_res = api_client.post(
        f"/teams/{team.id}/tasks/{task_id}/checklist",
        json={"item_text": "Write tests"},
        headers=_headers(leader),
    )
    assert add_res.status_code == 201
    item = add_res.json()
    item_id = item["id"]
    assert item["item_text"] == "Write tests"
    assert item["is_done"] is False
    assert item["created_by"] == str(leader.id)

    # Assignee marks item done
    done_res = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/checklist/{item_id}",
        json={"is_done": True},
        headers=_headers(member),
    )
    assert done_res.status_code == 200
    assert done_res.json()["is_done"] is True
    assert done_res.json()["completed_by"] == str(member.id)
    assert done_res.json()["completed_at"] is not None

    # Assignee attempts to edit text -> 403
    text_fail = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/checklist/{item_id}",
        json={"item_text": "Edited by member"},
        headers=_headers(member),
    )
    assert text_fail.status_code == 403

    # Leader can edit text
    text_res = api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/checklist/{item_id}",
        json={"item_text": "Write tests thoroughly"},
        headers=_headers(leader),
    )
    assert text_res.status_code == 200
    assert text_res.json()["item_text"] == "Write tests thoroughly"

    # Detail shows item
    detail = api_client.get(
        f"/teams/{team.id}/tasks/{task_id}",
        headers=_headers(member),
    ).json()
    assert len(detail["checklist_items"]) == 1
    assert detail["checklist_items"][0]["item_text"] == "Write tests thoroughly"
    assert detail["checklist_items"][0]["is_done"] is True


def test_task_filtering_and_timezone_handling(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader = _new_user(db_session, "student", "Leader")
    member1 = _new_user(db_session, "student", "Member 1")
    member2 = _new_user(db_session, "student", "Member 2")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member1)
    _add_team_member(db_session, team, member2)
    milestone = _new_milestone(db_session, team)

    # Cairo offset +02:00
    cairo_due1 = datetime(2026, 12, 10, 14, 0, tzinfo=ZoneInfo("Africa/Cairo"))
    cairo_due2 = datetime(2026, 12, 20, 14, 0, tzinfo=ZoneInfo("Africa/Cairo"))

    # Create task 1: member1, high priority, due 2026-12-10 12:00 UTC
    t1 = api_client.post(
        f"/teams/{team.id}/tasks",
        json={
            "title": "Task 1",
            "assignee_id": str(member1.id),
            "priority": "high",
            "due_at": cairo_due1.isoformat(),
            "milestone_id": str(milestone.id),
        },
        headers=_headers(leader),
    ).json()

    # Create task 2: member2, low priority, due 2026-12-20 12:00 UTC
    t2 = api_client.post(
        f"/teams/{team.id}/tasks",
        json={
            "title": "Task 2",
            "assignee_id": str(member2.id),
            "priority": "low",
            "due_at": cairo_due2.isoformat(),
        },
        headers=_headers(leader),
    ).json()

    # Mark t1 as in_progress
    api_client.patch(
        f"/teams/{team.id}/tasks/{t1['id']}/status",
        json={"status": "in_progress"},
        headers=_headers(member1),
    )

    # Filter by status
    res = api_client.get(
        f"/teams/{team.id}/tasks?status=in_progress",
        headers=_headers(leader),
    )
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == t1["id"]

    # Filter by assignee
    res = api_client.get(
        f"/teams/{team.id}/tasks?assignee_id={member2.id}",
        headers=_headers(leader),
    )
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == t2["id"]

    # Filter by priority
    res = api_client.get(
        f"/teams/{team.id}/tasks?priority=high",
        headers=_headers(leader),
    )
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == t1["id"]

    # Filter by milestone
    res = api_client.get(
        f"/teams/{team.id}/tasks?milestone_id={milestone.id}",
        headers=_headers(leader),
    )
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == t1["id"]

    # Filter by due_before (before 2026-12-15 UTC)
    cutoff = datetime(2026, 12, 15, 0, 0, tzinfo=timezone.utc).isoformat()
    res = api_client.get(
        f"/teams/{team.id}/tasks",
        params={"due_before": cutoff},
        headers=_headers(leader),
    )
    assert res.status_code == 200
    tasks_before = res.json()
    assert len(tasks_before) == 1
    assert tasks_before[0]["id"] == t1["id"]

    # Filter with no matches returns empty list
    res = api_client.get(
        f"/teams/{team.id}/tasks?status=done",
        headers=_headers(leader),
    )
    assert res.status_code == 200
    assert res.json() == []


def test_cross_team_isolation_and_supervisor_read_only(
    api_client: TestClient, db_session: OrmSession
) -> None:
    leader1 = _new_user(db_session, "student", "Leader 1")
    member1 = _new_user(db_session, "student", "Member 1")
    supervisor = _new_user(db_session, "supervisor", "Supervisor")
    coordinator = _new_user(db_session, "coordinator", "Coordinator")
    other_student = _new_user(db_session, "student", "Other Student")

    team1 = _new_team(db_session, leader1, "Team 1")
    _add_team_member(db_session, team1, member1)
    assign_supervisor(
        session=db_session,
        team_id=team1.id,
        supervisor_id=supervisor.id,
    )

    t1 = api_client.post(
        f"/teams/{team1.id}/tasks",
        json={"title": "Team 1 Task", "assignee_id": str(member1.id)},
        headers=_headers(leader1),
    ).json()

    # Other student cannot read team1 tasks (non-enumerating 404)
    res = api_client.get(
        f"/teams/{team1.id}/tasks",
        headers=_headers(other_student),
    )
    assert res.status_code == 404

    res = api_client.get(
        f"/teams/{team1.id}/tasks/{t1['id']}",
        headers=_headers(other_student),
    )
    assert res.status_code == 404

    # Assigned supervisor can read team tasks
    sup_res = api_client.get(
        f"/teams/{team1.id}/tasks",
        headers=_headers(supervisor),
    )
    assert sup_res.status_code == 200
    assert len(sup_res.json()) == 1

    # Coordinator can read team tasks
    coord_res = api_client.get(
        f"/teams/{team1.id}/tasks",
        headers=_headers(coordinator),
    )
    assert coord_res.status_code == 200
    assert len(coord_res.json()) == 1

    # Supervisor cannot modify task
    patch_res = api_client.patch(
        f"/teams/{team1.id}/tasks/{t1['id']}/status",
        json={"status": "done"},
        headers=_headers(supervisor),
    )
    assert patch_res.status_code == 403


def test_database_constraints_and_activity_immutability(
    db_session: OrmSession,
) -> None:
    leader = _new_user(db_session, "student")
    member = _new_user(db_session, "student")
    team = _new_team(db_session, leader)
    _add_team_member(db_session, team, member)

    # 1. Direct insert violating title trimmed raises IntegrityError
    untrimmed_task = Task(
        team_id=team.id,
        title="  Untrimmed  ",
        status="todo",
        priority="medium",
        created_by=leader.id,
        assignee_id=member.id,
        updated_by=leader.id,
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(untrimmed_task)
            db_session.flush()

    # 2. Direct insert violating completion consistency
    inconsistent_task = Task(
        team_id=team.id,
        title="Inconsistent done",
        status="done",
        priority="medium",
        created_by=leader.id,
        assignee_id=member.id,
        updated_by=leader.id,
        completed_by=None,  # Invalid: done requires completed_by
        completed_at=None,
    )
    with pytest.raises(IntegrityError):
        with db_session.begin_nested():
            db_session.add(inconsistent_task)
            db_session.flush()

    # 3. TaskActivity immutability trigger
    valid_task = Task(
        team_id=team.id,
        title="Valid task",
        status="todo",
        priority="medium",
        created_by=leader.id,
        assignee_id=member.id,
        updated_by=leader.id,
    )
    db_session.add(valid_task)
    db_session.flush()

    activity = TaskActivity(
        task_id=valid_task.id,
        actor_id=leader.id,
        event_type="created",
        old_value=None,
        new_value="todo",
        details="Created",
    )
    db_session.add(activity)
    db_session.flush()

    # Attempt to update activity triggers rejection
    with pytest.raises(DBAPIError):
        with db_session.begin_nested():
            db_session.execute(
                text("UPDATE task_activities SET details = 'Tampered' WHERE id = :id"),
                {"id": activity.id},
            )


def test_cross_phase_end_to_end_workflow(
    api_client: TestClient, db_session: OrmSession
) -> None:
    # 1. Register student leader and member
    leader = _new_user(db_session, "student", "E2E Leader")
    member = _new_user(db_session, "student", "E2E Member")
    supervisor = _new_user(db_session, "supervisor", "E2E Supervisor")
    coordinator = _new_user(db_session, "coordinator", "E2E Coordinator")
    unrelated = _new_user(db_session, "student", "Unrelated Student")

    # 2. Leader creates team and adds member
    team = _new_team(db_session, leader, "GradTrack Alpha")
    _add_team_member(db_session, team, member)

    # 3. Coordinator assigns supervisor
    assign_supervisor(
        session=db_session,
        team_id=team.id,
        supervisor_id=supervisor.id,
    )

    # 4. Supervisor creates milestone
    milestone = _new_milestone(
        db_session,
        team,
        due_at=datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc),
        name="Phase 6 Verification Milestone",
    )

    # 5. Leader creates task linked to milestone, assigned to member
    t_res = api_client.post(
        f"/teams/{team.id}/tasks",
        json={
            "title": "Complete System Integration",
            "description": "Verify task flow and milestone linkage",
            "assignee_id": str(member.id),
            "priority": "high",
            "milestone_id": str(milestone.id),
            "estimated_minutes": 240,
        },
        headers=_headers(leader),
    )
    assert t_res.status_code == 201
    task_id = t_res.json()["id"]

    # 6. Leader adds checklist item
    chk_res = api_client.post(
        f"/teams/{team.id}/tasks/{task_id}/checklist",
        json={"item_text": "Write comprehensive test suite"},
        headers=_headers(leader),
    )
    assert chk_res.status_code == 201
    item_id = chk_res.json()["id"]

    # 7. Member updates task status, completes checklist item, then marks task done
    api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/status",
        json={"status": "in_progress"},
        headers=_headers(member),
    )
    api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/checklist/{item_id}",
        json={"is_done": True},
        headers=_headers(member),
    )
    api_client.patch(
        f"/teams/{team.id}/tasks/{task_id}/status",
        json={"status": "done"},
        headers=_headers(member),
    )

    # 8. Leader, supervisor, and coordinator inspect task details and activity
    detail_res = api_client.get(
        f"/teams/{team.id}/tasks/{task_id}",
        headers=_headers(supervisor),
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["status"] == "done"
    assert detail["completed_by"] == str(member.id)
    assert detail["checklist_items"][0]["is_done"] is True

    coord_res = api_client.get(
        f"/teams/{team.id}/tasks/{task_id}",
        headers=_headers(coordinator),
    )
    assert coord_res.status_code == 200

    activities_res = api_client.get(
        f"/teams/{team.id}/tasks/{task_id}/activity",
        headers=_headers(supervisor),
    )
    assert activities_res.status_code == 200
    acts = activities_res.json()
    act_types = [a["event_type"] for a in acts]
    assert act_types == [
        "created",
        "checklist_item_added",
        "status_changed",
        "checklist_item_updated",
        "completed",
    ]

    # 9. Unrelated student is denied access
    assert (
        api_client.get(
            f"/teams/{team.id}/tasks/{task_id}",
            headers=_headers(unrelated),
        ).status_code
        == 404
    )
