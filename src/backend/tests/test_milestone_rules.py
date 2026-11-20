"""Unit tests for milestone input validation and derived deadline state."""

from datetime import datetime, timedelta, timezone

import pytest
from app.main import app
from app.milestones import deadline_status
from app.schemas import MilestoneCreateRequest, MilestoneUpdateRequest
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        (
            "2026-12-01T17:00:00+02:00",
            datetime(2026, 12, 1, 15, tzinfo=timezone.utc),
        ),
        (
            "2026-12-01T15:00:00Z",
            datetime(2026, 12, 1, 15, tzinfo=timezone.utc),
        ),
        (
            "2026-01-01T00:30:00+02:00",
            datetime(2025, 12, 31, 22, 30, tzinfo=timezone.utc),
        ),
        (
            "2026-12-31T23:30:00-02:00",
            datetime(2027, 1, 1, 1, 30, tzinfo=timezone.utc),
        ),
    ),
)
def test_create_schema_normalizes_offset_aware_due_time_to_utc(
    value: str, expected: datetime
) -> None:
    payload = MilestoneCreateRequest(name="Proposal", due_at=value)

    assert payload.due_at == expected
    assert payload.due_at.tzinfo is timezone.utc


@pytest.mark.parametrize("value", ("2026-12-01T17:00:00", "2026-12-01", "not-a-date"))
def test_create_schema_rejects_invalid_or_offsetless_deadlines(value: str) -> None:
    with pytest.raises(ValidationError):
        MilestoneCreateRequest(name="Proposal", due_at=value)


def test_update_schema_normalizes_deadline_and_rejects_extra_fields() -> None:
    payload = MilestoneUpdateRequest(due_at="2026-12-01T17:00:00+02:00")

    assert payload.due_at == datetime(2026, 12, 1, 15, tzinfo=timezone.utc)
    with pytest.raises(ValidationError):
        MilestoneUpdateRequest(
            due_at="2026-12-01T17:00:00Z",
            team_id="00000000-0000-0000-0000-000000000001",
        )


@pytest.mark.parametrize("value", ("2026-12-01T17:00:00", "not-a-date"))
def test_update_schema_rejects_invalid_or_offsetless_deadlines(value: str) -> None:
    with pytest.raises(ValidationError):
        MilestoneUpdateRequest(due_at=value)


@pytest.mark.parametrize("name", ("", "   ", "\t\n", "x" * 201))
def test_create_schema_rejects_blank_or_oversized_names(name: str) -> None:
    with pytest.raises(ValidationError):
        MilestoneCreateRequest(
            name=name,
            due_at="2026-12-01T17:00:00Z",
        )


def test_create_schema_trims_name_and_accepts_optional_description() -> None:
    payload = MilestoneCreateRequest(
        name="  Software Requirements  ",
        description="Draft and review the SRS.",
        due_at="2026-12-01T17:00:00Z",
    )

    assert payload.name == "Software Requirements"
    assert payload.description == "Draft and review the SRS."


def test_create_schema_rejects_client_controlled_team_and_role_fields() -> None:
    with pytest.raises(ValidationError):
        MilestoneCreateRequest(
            name="Proposal",
            due_at="2026-12-01T17:00:00Z",
            team_id="00000000-0000-0000-0000-000000000001",
            system_role="coordinator",
        )


@pytest.mark.parametrize(
    ("delta", "expected"),
    (
        (timedelta(days=7, microseconds=1), "scheduled"),
        (timedelta(days=7), "due_soon"),
        (timedelta(days=6, hours=23), "due_soon"),
        (timedelta(0), "due_soon"),
        (-timedelta(microseconds=1), "overdue"),
    ),
)
def test_deadline_status_uses_approved_seven_day_and_exact_time_boundaries(
    delta: timedelta, expected: str
) -> None:
    now = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)

    assert deadline_status(now + delta, now=now) == expected


def test_deadline_status_rejects_naive_datetimes() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        deadline_status(datetime(2026, 11, 18, 12), now=datetime(2026, 11, 18, 12))


def test_milestone_routes_are_present_in_openapi() -> None:
    paths = app.openapi()["paths"]

    assert set(paths["/teams/{team_id}/milestones"]) == {"get", "post"}
    assert set(paths["/teams/{team_id}/milestones/{milestone_id}"]) == {
        "get",
        "patch",
    }
