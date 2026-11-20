"""Unit tests for task, checklist, and activity schemas and validation."""

from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from app.schemas import (
    TaskActivityResponse,
    TaskChecklistItemCreateRequest,
    TaskChecklistItemUpdateRequest,
    TaskCreateRequest,
    TaskDetailResponse,
    TaskResponse,
    TaskStatusUpdateRequest,
    TaskUpdateRequest,
)
from pydantic import ValidationError


def test_task_create_request_valid_minimal() -> None:
    assignee_id = uuid4()
    req = TaskCreateRequest(title="  Implement login  ", assignee_id=assignee_id)
    assert req.title == "Implement login"
    assert req.assignee_id == assignee_id
    assert req.priority == "medium"
    assert req.description is None
    assert req.due_at is None
    assert req.estimated_minutes is None
    assert req.milestone_id is None
    assert req.parent_task_id is None


def test_task_create_request_valid_full() -> None:
    assignee_id = uuid4()
    milestone_id = uuid4()
    parent_id = uuid4()
    cairo_due = datetime(2026, 12, 1, 15, 0, tzinfo=ZoneInfo("Africa/Cairo"))
    req = TaskCreateRequest(
        title="Implement login",
        description="Full Argon2id integration",
        assignee_id=assignee_id,
        priority="high",
        due_at=cairo_due,
        estimated_minutes=120,
        milestone_id=milestone_id,
        parent_task_id=parent_id,
    )
    assert req.priority == "high"
    assert req.estimated_minutes == 120
    assert req.due_at == datetime(2026, 12, 1, 13, 0, tzinfo=timezone.utc)
    assert req.milestone_id == milestone_id
    assert req.parent_task_id == parent_id


def test_task_create_request_rejects_empty_or_whitespace_title() -> None:
    with pytest.raises(ValidationError):
        TaskCreateRequest(title="   ", assignee_id=uuid4())
    with pytest.raises(ValidationError):
        TaskCreateRequest(title="", assignee_id=uuid4())


def test_task_create_request_rejects_too_long_title() -> None:
    with pytest.raises(ValidationError):
        TaskCreateRequest(title="a" * 201, assignee_id=uuid4())


def test_task_create_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        TaskCreateRequest(
            title="Valid title",
            assignee_id=uuid4(),
            custom_extra_field="disallowed",  # type: ignore[call-arg]
        )


def test_task_create_request_rejects_invalid_priority() -> None:
    with pytest.raises(ValidationError):
        TaskCreateRequest(
            title="Valid title",
            assignee_id=uuid4(),
            priority="critical",  # type: ignore[arg-type]
        )


def test_task_create_request_rejects_naive_due_at() -> None:
    with pytest.raises(ValidationError):
        TaskCreateRequest(
            title="Valid title",
            assignee_id=uuid4(),
            due_at=datetime(2026, 12, 1, 12, 0),
        )


def test_task_create_request_rejects_invalid_estimated_minutes() -> None:
    with pytest.raises(ValidationError):
        TaskCreateRequest(
            title="Valid title",
            assignee_id=uuid4(),
            estimated_minutes=0,
        )
    with pytest.raises(ValidationError):
        TaskCreateRequest(
            title="Valid title",
            assignee_id=uuid4(),
            estimated_minutes=-10,
        )
    with pytest.raises(ValidationError):
        TaskCreateRequest(
            title="Valid title",
            assignee_id=uuid4(),
            estimated_minutes=600000,
        )


def test_task_status_update_request_accepts_only_approved_statuses() -> None:
    for valid_status in ("todo", "in_progress", "done"):
        req = TaskStatusUpdateRequest(status=valid_status)  # type: ignore[arg-type]
        assert req.status == valid_status

    for invalid_status in ("blocked", "completed", "pending", "in-progress", ""):
        with pytest.raises(ValidationError):
            TaskStatusUpdateRequest(status=invalid_status)  # type: ignore[arg-type]


def test_task_update_request_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        TaskUpdateRequest(unknown_field="value")  # type: ignore[call-arg]


def test_checklist_item_create_request_validation() -> None:
    req = TaskChecklistItemCreateRequest(item_text="  Design database schema  ")
    assert req.item_text == "Design database schema"

    with pytest.raises(ValidationError):
        TaskChecklistItemCreateRequest(item_text="   ")
    with pytest.raises(ValidationError):
        TaskChecklistItemCreateRequest(item_text="")
    with pytest.raises(ValidationError):
        TaskChecklistItemCreateRequest(item_text="x" * 201)
    with pytest.raises(ValidationError):
        TaskChecklistItemCreateRequest(
            item_text="Valid",
            unexpected="value",  # type: ignore[call-arg]
        )


def test_task_checklist_item_update_request_validation() -> None:
    req = TaskChecklistItemUpdateRequest(is_done=True, item_text="Updated text")
    assert req.is_done is True
    assert req.item_text == "Updated text"

    req_partial = TaskChecklistItemUpdateRequest(is_done=False)
    assert req_partial.is_done is False
    assert req_partial.item_text is None


def test_task_response_and_detail_response_schema() -> None:
    task_id = uuid4()
    team_id = uuid4()
    user_id = uuid4()
    now = datetime.now(timezone.utc)

    task_resp = TaskResponse(
        id=task_id,
        team_id=team_id,
        title="Build backend",
        description="FastAPI endpoints",
        status="todo",
        priority="high",
        created_by=user_id,
        assignee_id=user_id,
        updated_by=user_id,
        completed_by=None,
        due_at=now,
        estimated_minutes=60,
        milestone_id=None,
        parent_task_id=None,
        completed_at=None,
        created_at=now,
        updated_at=now,
    )
    assert task_resp.id == task_id

    detail = TaskDetailResponse(
        **task_resp.model_dump(),
        checklist_items=[],
        subtasks=[],
    )
    assert detail.checklist_items == []
    assert detail.subtasks == []


def test_task_activity_response_schema() -> None:
    now = datetime.now(timezone.utc)
    act = TaskActivityResponse(
        id=uuid4(),
        task_id=uuid4(),
        actor_id=uuid4(),
        actor_name="Test Student",
        event_type="created",
        old_value=None,
        new_value="todo",
        details="Task created",
        created_at=now,
    )
    assert act.event_type == "created"
    assert act.actor_name == "Test Student"
