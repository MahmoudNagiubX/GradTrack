"""Unit tests for Phase 7A timeline, calendar, and progress summary schemas."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from app.schemas import (
    AssigneeTaskProgress,
    CalendarItemResponse,
    CalendarMilestoneItem,
    CalendarTaskItem,
    MilestoneProgressCounts,
    TaskProgressCounts,
    TeamProgressSummaryResponse,
    UpcomingDeadlineItem,
)
from pydantic import ValidationError


def test_calendar_task_item_valid() -> None:
    task_id = uuid4()
    team_id = uuid4()
    assignee_id = uuid4()
    milestone_id = uuid4()
    due = datetime(2026, 12, 1, 15, 0, tzinfo=timezone.utc)

    item = CalendarTaskItem(
        id=task_id,
        team_id=team_id,
        title="Complete backend testing",
        due_at=due,
        status="in_progress",
        priority="high",
        assignee_id=assignee_id,
        milestone_id=milestone_id,
    )
    assert item.kind == "task"
    assert item.title == "Complete backend testing"
    assert item.due_at == due
    assert item.status == "in_progress"
    assert item.priority == "high"
    assert item.parent_task_id is None


def test_calendar_milestone_item_valid() -> None:
    m_id = uuid4()
    team_id = uuid4()
    due = datetime(2026, 12, 15, 12, 0, tzinfo=timezone.utc)

    item = CalendarMilestoneItem(
        id=m_id,
        team_id=team_id,
        title="System Architecture Submission",
        due_at=due,
        deadline_status="due_soon",
        review_status="pending_review",
    )
    assert item.kind == "milestone"
    assert item.title == "System Architecture Submission"
    assert item.deadline_status == "due_soon"
    assert item.review_status == "pending_review"


def test_calendar_item_discriminated_union() -> None:
    due = datetime(2026, 12, 10, 10, 0, tzinfo=timezone.utc)
    task_payload = {
        "kind": "task",
        "id": str(uuid4()),
        "team_id": str(uuid4()),
        "title": "Task A",
        "due_at": due.isoformat(),
        "status": "todo",
        "priority": "low",
        "assignee_id": str(uuid4()),
    }
    milestone_payload = {
        "kind": "milestone",
        "id": str(uuid4()),
        "team_id": str(uuid4()),
        "title": "Milestone B",
        "due_at": due.isoformat(),
        "deadline_status": "scheduled",
        "review_status": "not_submitted",
    }

    from pydantic import TypeAdapter

    adapter = TypeAdapter(CalendarItemResponse)
    parsed_task = adapter.validate_python(task_payload)
    parsed_milestone = adapter.validate_python(milestone_payload)

    assert isinstance(parsed_task, CalendarTaskItem)
    assert isinstance(parsed_milestone, CalendarMilestoneItem)


def test_progress_counts_schemas() -> None:
    tasks = TaskProgressCounts(
        total=5,
        todo=2,
        in_progress=2,
        done=1,
        overdue=1,
    )
    assert tasks.total == 5
    assert tasks.done == 1

    assignee = AssigneeTaskProgress(
        assignee_id=uuid4(),
        assignee_name="Mona Student",
        total=3,
        todo=1,
        in_progress=1,
        done=1,
        overdue=0,
    )
    assert assignee.assignee_name == "Mona Student"

    milestones = MilestoneProgressCounts(
        total=3,
        scheduled=1,
        due_soon=1,
        overdue=1,
        not_submitted=1,
        pending_review=1,
        returned=0,
        approved=1,
    )
    assert milestones.total == 3
    assert milestones.approved == 1


def test_upcoming_deadline_item_schemas() -> None:
    due = datetime(2026, 12, 20, 12, 0, tzinfo=timezone.utc)
    task_upcoming = UpcomingDeadlineItem(
        kind="task",
        id=uuid4(),
        title="Integration Tests",
        due_at=due,
        status="in_progress",
        priority="high",
        assignee_id=uuid4(),
    )
    assert task_upcoming.kind == "task"
    assert task_upcoming.deadline_status is None

    ms_upcoming = UpcomingDeadlineItem(
        kind="milestone",
        id=uuid4(),
        title="Final Prototype",
        due_at=due,
        deadline_status="scheduled",
        review_status="approved",
    )
    assert ms_upcoming.kind == "milestone"
    assert ms_upcoming.status is None


def test_team_progress_summary_response_valid() -> None:
    now = datetime.now(timezone.utc)
    team_id = uuid4()
    summary = TeamProgressSummaryResponse(
        team_id=team_id,
        team_name="Team Alpha",
        as_of=now,
        tasks=TaskProgressCounts(total=0, todo=0, in_progress=0, done=0, overdue=0),
        tasks_by_assignee=[],
        milestones=MilestoneProgressCounts(
            total=0,
            scheduled=0,
            due_soon=0,
            overdue=0,
            not_submitted=0,
            pending_review=0,
            returned=0,
            approved=0,
        ),
        late_submissions=0,
        upcoming=[],
    )
    assert summary.team_id == team_id
    assert summary.team_name == "Team Alpha"
    assert summary.late_submissions == 0
    assert summary.upcoming == []


def test_calendar_item_discriminator_invalid() -> None:
    with pytest.raises(ValidationError):
        CalendarTaskItem.model_validate(
            {
                "id": str(uuid4()),
                "team_id": str(uuid4()),
                "title": "Bad Task",
                "due_at": datetime.now(timezone.utc).isoformat(),
                "kind": "unknown_kind",
                "status": "todo",
                "priority": "low",
            }
        )
