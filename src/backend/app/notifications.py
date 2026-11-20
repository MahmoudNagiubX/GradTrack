"""In-app deadline reminders and read receipts for student team members."""

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.database import get_db_session
from app.models import (
    Milestone,
    MilestoneSubmission,
    NotificationReadReceipt,
    Task,
    TeamMembership,
    User,
)
from app.schemas import (
    MarkReminderReadResponse,
    ReminderItemResponse,
    ReminderKind,
)

router = APIRouter(tags=["notifications"])
DbSession = Annotated[Session, Depends(get_db_session)]

NAMESPACE_REMINDER = UUID("4a781b0f-23c4-4a27-a442-45ab1d2fa33b")


def _now_utc() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(timezone.utc)


def compute_reminder_id(
    source_kind: str,
    source_id: UUID,
    due_at: datetime,
    reminder_kind: str,
) -> UUID:
    """Derive a deterministic reminder UUID from source and deadline attributes."""
    due_utc = due_at.astimezone(timezone.utc)
    key = f"{source_kind}:{source_id}:{due_utc.isoformat()}:{reminder_kind}"
    return uuid5(NAMESPACE_REMINDER, key)


def _derive_student_reminders(
    student: User,
    session: Session,
    *,
    as_of: datetime | None = None,
) -> list[ReminderItemResponse]:
    """Derive active due-soon and overdue reminders for an active student member."""
    if student.system_role != "student" or not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active student members can access reminders",
        )

    now_utc = (as_of or _now_utc()).astimezone(timezone.utc)
    max_due_utc = now_utc + timedelta(days=7)

    # 1. Active team memberships
    memberships = session.scalars(
        select(TeamMembership.team_id).where(TeamMembership.user_id == student.id)
    ).all()
    if not memberships:
        return []

    team_ids = list(memberships)

    # raw_items: tuple(due_at, sort_prio, source_id, partial_response)
    raw_items: list[tuple[datetime, int, UUID, ReminderItemResponse]] = []

    # 2. Tasks currently assigned to student in active teams
    tasks = session.scalars(
        select(Task).where(
            Task.team_id.in_(team_ids),
            Task.assignee_id == student.id,
            Task.status != "done",
            Task.due_at.is_not(None),
        )
    ).all()

    for task in tasks:
        assert task.due_at is not None
        task_due = task.due_at.astimezone(timezone.utc)
        r_kind: ReminderKind
        if task_due < now_utc:
            r_kind = "task_overdue"
        elif now_utc <= task_due <= max_due_utc:
            r_kind = "task_due_soon"
        else:
            continue

        rem_id = compute_reminder_id("task", task.id, task_due, r_kind)
        item = ReminderItemResponse(
            id=rem_id,
            kind=r_kind,
            source_id=task.id,
            team_id=task.team_id,
            title=task.title,
            due_at=task_due,
            is_read=False,
            read_at=None,
        )
        raw_items.append((task_due, 1, task.id, item))

    # 3. Actionable team milestones (not_submitted or returned)
    milestones = session.scalars(
        select(Milestone).where(Milestone.team_id.in_(team_ids))
    ).all()

    for ms in milestones:
        ms_due = ms.due_at.astimezone(timezone.utc)
        ms_kind: ReminderKind
        if ms_due < now_utc:
            ms_kind = "milestone_overdue"
        elif now_utc <= ms_due <= max_due_utc:
            ms_kind = "milestone_due_soon"
        else:
            continue

        sub = session.scalar(
            select(MilestoneSubmission).where(MilestoneSubmission.milestone_id == ms.id)
        )
        if sub is None or sub.review_status == "returned":
            # Actionable: not submitted yet or returned by supervisor
            pass
        else:
            # Pending review or approved: no student action needed
            continue

        rem_id = compute_reminder_id("milestone", ms.id, ms_due, ms_kind)
        item = ReminderItemResponse(
            id=rem_id,
            kind=ms_kind,
            source_id=ms.id,
            team_id=ms.team_id,
            title=ms.name,
            due_at=ms_due,
            is_read=False,
            read_at=None,
        )
        raw_items.append((ms_due, 0, ms.id, item))

    if not raw_items:
        return []

    # 4. Fetch persistent read receipts for this student
    all_rem_ids = [item.id for _, _, _, item in raw_items]
    receipts = session.scalars(
        select(NotificationReadReceipt).where(
            NotificationReadReceipt.user_id == student.id,
            NotificationReadReceipt.reminder_id.in_(all_rem_ids),
        )
    ).all()
    receipt_map = {r.reminder_id: r.read_at for r in receipts}

    # 5. Deterministic sorting: due_at ascending, milestone before task, source_id, id
    raw_items.sort(key=lambda x: (x[0], x[1], x[2], x[3].id))

    result: list[ReminderItemResponse] = []
    for _, _, _, item in raw_items:
        read_at = receipt_map.get(item.id)
        is_read = read_at is not None
        result.append(
            ReminderItemResponse(
                id=item.id,
                kind=item.kind,
                source_id=item.source_id,
                team_id=item.team_id,
                title=item.title,
                due_at=item.due_at,
                is_read=is_read,
                read_at=read_at,
            )
        )

    return result


@router.get(
    "/notifications",
    response_model=list[ReminderItemResponse],
)
def get_notifications(
    current_user: CurrentUser,
    session: DbSession,
    unread_only: bool = Query(
        default=False,
        description="Filter to return only unread reminders",
    ),
) -> list[ReminderItemResponse]:
    """Return active deadline reminders for the authenticated student."""
    reminders = _derive_student_reminders(current_user, session)
    if unread_only:
        return [r for r in reminders if not r.is_read]
    return reminders


@router.post(
    "/notifications/{reminder_id}/read",
    response_model=MarkReminderReadResponse,
)
def mark_notification_read(
    reminder_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> MarkReminderReadResponse:
    """Mark a currently active reminder as read for the calling student."""
    reminders = _derive_student_reminders(current_user, session)
    matching = next((r for r in reminders if r.id == reminder_id), None)
    if matching is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found or no longer active",
        )

    existing = session.scalar(
        select(NotificationReadReceipt).where(
            NotificationReadReceipt.user_id == current_user.id,
            NotificationReadReceipt.reminder_id == reminder_id,
        )
    )
    if existing is not None:
        return MarkReminderReadResponse(
            reminder_id=reminder_id,
            read_at=existing.read_at,
        )

    now_utc = _now_utc()
    receipt = NotificationReadReceipt(
        user_id=current_user.id,
        reminder_id=reminder_id,
        read_at=now_utc,
    )
    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    return MarkReminderReadResponse(
        reminder_id=reminder_id,
        read_at=receipt.read_at,
    )
