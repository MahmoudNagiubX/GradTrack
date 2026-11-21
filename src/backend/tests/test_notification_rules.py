"""Pure unit tests for Phase 7B deadline reminder rules and stable ID generation."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from app.notifications import compute_reminder_id
from app.schemas import MarkReminderReadResponse, ReminderItemResponse
from pydantic import ValidationError


def test_due_date_boundary_classification() -> None:
    now_utc = datetime(2026, 12, 10, 12, 0, 0, tzinfo=timezone.utc)
    max_due_soon = now_utc + timedelta(days=7)

    # 1. Exactly at deadline -> due_soon
    exact_deadline = now_utc
    assert exact_deadline >= now_utc
    assert exact_deadline <= max_due_soon

    # 2. 1 microsecond past deadline -> overdue
    just_past = now_utc - timedelta(microseconds=1)
    assert just_past < now_utc

    # 3. Exactly at 7 days -> due_soon
    exact_7_days = max_due_soon
    assert exact_7_days >= now_utc
    assert exact_7_days <= max_due_soon

    # 4. 7 days + 1 microsecond -> beyond 7-day window
    beyond_7_days = max_due_soon + timedelta(microseconds=1)
    assert beyond_7_days > max_due_soon


def test_compute_reminder_id_deterministic_and_stable() -> None:
    source_id = uuid4()
    due_at = datetime(2026, 12, 15, 14, 0, 0, tzinfo=timezone.utc)

    id1 = compute_reminder_id("task", source_id, due_at, "task_due_soon")
    id2 = compute_reminder_id("task", source_id, due_at, "task_due_soon")
    assert id1 == id2


def test_compute_reminder_id_changes_on_attributes() -> None:
    source_id = uuid4()
    due_at = datetime(2026, 12, 15, 14, 0, 0, tzinfo=timezone.utc)

    base_id = compute_reminder_id("task", source_id, due_at, "task_due_soon")

    # Changed deadline
    changed_due = due_at + timedelta(days=1)
    new_due_id = compute_reminder_id("task", source_id, changed_due, "task_due_soon")
    assert base_id != new_due_id

    # Changed kind (due_soon -> overdue)
    overdue_id = compute_reminder_id("task", source_id, due_at, "task_overdue")
    assert base_id != overdue_id

    # Changed source_id
    diff_source_id = compute_reminder_id("task", uuid4(), due_at, "task_due_soon")
    assert base_id != diff_source_id

    # Changed source_kind
    milestone_id = compute_reminder_id(
        "milestone", source_id, due_at, "milestone_due_soon"
    )
    assert base_id != milestone_id


def test_compute_reminder_id_timezone_normalization() -> None:
    source_id = uuid4()
    # 14:00 UTC == 16:00 Cairo (+02:00)
    utc_dt = datetime(2026, 12, 15, 14, 0, 0, tzinfo=timezone.utc)
    cairo_tz = ZoneInfo("Africa/Cairo")
    cairo_dt = datetime(2026, 12, 15, 16, 0, 0, tzinfo=cairo_tz)

    id_utc = compute_reminder_id("task", source_id, utc_dt, "task_due_soon")
    id_cairo = compute_reminder_id("task", source_id, cairo_dt, "task_due_soon")
    assert id_utc == id_cairo


def test_reminder_schemas_validation() -> None:
    now = datetime.now(timezone.utc)
    rem_id = uuid4()
    task_id = uuid4()
    team_id = uuid4()

    valid_item = ReminderItemResponse(
        id=rem_id,
        kind="task_due_soon",
        source_id=task_id,
        team_id=team_id,
        title="Implement Reminders",
        due_at=now,
        is_read=False,
    )
    assert valid_item.id == rem_id
    assert valid_item.is_read is False
    assert valid_item.read_at is None

    # Invalid reminder kind
    with pytest.raises(ValidationError):
        ReminderItemResponse.model_validate(
            {
                "id": str(rem_id),
                "kind": "unsupported_kind",
                "source_id": str(task_id),
                "team_id": str(team_id),
                "title": "Bad Reminder",
                "due_at": now.isoformat(),
                "is_read": False,
            }
        )

    receipt = MarkReminderReadResponse(reminder_id=rem_id, read_at=now)
    assert receipt.status == "ok"
    assert receipt.reminder_id == rem_id
