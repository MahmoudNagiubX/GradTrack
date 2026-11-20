"""Team-scoped calendar/timeline data and progress dashboard summaries."""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser
from app.database import get_db_session
from app.milestones import deadline_status
from app.models import (
    Milestone,
    MilestoneSubmission,
    SubmissionVersion,
    SupervisorAssignment,
    Task,
    Team,
    TeamMembership,
    User,
)
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
from app.teams import get_visible_team

router = APIRouter(tags=["progress", "timeline"])
DbSession = Annotated[Session, Depends(get_db_session)]


def _now_utc() -> datetime:
    """Return the current instant normalized to UTC; monkeypatchable in tests."""
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Validate timezone awareness and normalize to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Datetime must include an explicit timezone offset",
        )
    return value.astimezone(timezone.utc)


@router.get(
    "/teams/{team_id}/calendar",
    response_model=list[CalendarItemResponse],
)
def get_team_calendar(
    team_id: UUID,
    start_at: Annotated[
        datetime,
        Query(description="Start boundary (inclusive, UTC offset-aware)"),
    ],
    end_at: Annotated[
        datetime,
        Query(description="End boundary (exclusive, UTC offset-aware)"),
    ],
    current_user: CurrentUser,
    session: DbSession,
) -> list[CalendarItemResponse]:
    """Return tasks and milestones in the half-open range [start_at, end_at)."""
    get_visible_team(team_id, current_user, session)

    start_utc = _as_utc(start_at)
    end_utc = _as_utc(end_at)

    if start_utc >= end_utc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_at must be before end_at",
        )

    if (end_utc - start_utc) > timedelta(days=93):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Calendar query range cannot exceed 93 days",
        )

    now = _now_utc()

    # 1. Tasks in range with a due date
    tasks = session.scalars(
        select(Task).where(
            Task.team_id == team_id,
            Task.due_at.is_not(None),
            Task.due_at >= start_utc,
            Task.due_at < end_utc,
        )
    ).all()

    items: list[CalendarItemResponse] = [
        CalendarTaskItem(
            kind="task",
            id=task.id,
            team_id=task.team_id,
            title=task.title,
            due_at=task.due_at.astimezone(timezone.utc),  # type: ignore[union-attr]
            status=task.status,  # type: ignore[arg-type]
            priority=task.priority,  # type: ignore[arg-type]
            assignee_id=task.assignee_id,
            milestone_id=task.milestone_id,
            parent_task_id=task.parent_task_id,
        )
        for task in tasks
    ]

    # 2. Milestones in range
    milestones = session.scalars(
        select(Milestone).where(
            Milestone.team_id == team_id,
            Milestone.due_at >= start_utc,
            Milestone.due_at < end_utc,
        )
    ).all()

    for milestone in milestones:
        d_status = deadline_status(milestone.due_at, now=now)
        sub = session.scalar(
            select(MilestoneSubmission).where(
                MilestoneSubmission.milestone_id == milestone.id
            )
        )
        r_status = sub.review_status if sub is not None else "not_submitted"

        items.append(
            CalendarMilestoneItem(
                kind="milestone",
                id=milestone.id,
                team_id=milestone.team_id,
                title=milestone.name,
                due_at=milestone.due_at.astimezone(timezone.utc),
                deadline_status=d_status,
                review_status=r_status,  # type: ignore[arg-type]
            )
        )

    # Sort deterministically: due_at ASC, kind tie-break (milestone then task), id ASC
    items.sort(
        key=lambda item: (
            item.due_at,
            0 if item.kind == "milestone" else 1,
            item.id,
        )
    )
    return items


def _compute_team_progress(
    team: Team,
    session: Session,
    *,
    as_of: datetime | None = None,
) -> TeamProgressSummaryResponse:
    """Derive progress counts, assignee metrics, and upcoming deadlines for a team."""
    now_utc = _as_utc(as_of or _now_utc())

    # 1. Tasks
    tasks: Sequence[Task] = session.scalars(
        select(Task).where(Task.team_id == team.id)
    ).all()

    total_tasks = len(tasks)
    todo_tasks = 0
    in_progress_tasks = 0
    done_tasks = 0
    overdue_tasks = 0

    task_counts_by_assignee: dict[UUID, dict[str, int]] = {}
    for task in tasks:
        if task.status == "todo":
            todo_tasks += 1
        elif task.status == "in_progress":
            in_progress_tasks += 1
        elif task.status == "done":
            done_tasks += 1

        is_overdue = (
            task.status != "done"
            and task.due_at is not None
            and task.due_at.astimezone(timezone.utc) < now_utc
        )
        if is_overdue:
            overdue_tasks += 1

        assignee_dict = task_counts_by_assignee.setdefault(
            task.assignee_id,
            {"total": 0, "todo": 0, "in_progress": 0, "done": 0, "overdue": 0},
        )
        assignee_dict["total"] += 1
        if task.status in ("todo", "in_progress", "done"):
            assignee_dict[task.status] += 1
        if is_overdue:
            assignee_dict["overdue"] += 1

    # Team members query for display names and zero-task members
    members = session.execute(
        select(User.id, User.display_name)
        .join(TeamMembership, TeamMembership.user_id == User.id)
        .where(TeamMembership.team_id == team.id)
        .order_by(User.display_name.asc(), User.id.asc())
    ).all()

    tasks_by_assignee: list[AssigneeTaskProgress] = []
    for member_id, display_name in members:
        counts = task_counts_by_assignee.get(
            member_id,
            {"total": 0, "todo": 0, "in_progress": 0, "done": 0, "overdue": 0},
        )
        tasks_by_assignee.append(
            AssigneeTaskProgress(
                assignee_id=member_id,
                assignee_name=display_name,
                total=counts["total"],
                todo=counts["todo"],
                in_progress=counts["in_progress"],
                done=counts["done"],
                overdue=counts["overdue"],
            )
        )

    # In case there are tasks assigned to an assignee no longer in active team members
    for assignee_id, counts in task_counts_by_assignee.items():
        if not any(m.assignee_id == assignee_id for m in tasks_by_assignee):
            user = session.get(User, assignee_id)
            name = user.display_name if user else "Former Member"
            tasks_by_assignee.append(
                AssigneeTaskProgress(
                    assignee_id=assignee_id,
                    assignee_name=name,
                    total=counts["total"],
                    todo=counts["todo"],
                    in_progress=counts["in_progress"],
                    done=counts["done"],
                    overdue=counts["overdue"],
                )
            )
    tasks_by_assignee.sort(key=lambda a: (a.assignee_name.lower(), a.assignee_id))

    # 2. Milestones
    milestones: Sequence[Milestone] = session.scalars(
        select(Milestone).where(Milestone.team_id == team.id)
    ).all()

    total_milestones = len(milestones)
    ms_scheduled = 0
    ms_due_soon = 0
    ms_overdue = 0

    rev_not_submitted = 0
    rev_pending_review = 0
    rev_returned = 0
    rev_approved = 0
    late_submissions_count = 0

    for milestone in milestones:
        ds = deadline_status(milestone.due_at, now=now_utc)
        if ds == "scheduled":
            ms_scheduled += 1
        elif ds == "due_soon":
            ms_due_soon += 1
        elif ds == "overdue":
            ms_overdue += 1

        sub = session.scalar(
            select(MilestoneSubmission).where(
                MilestoneSubmission.milestone_id == milestone.id
            )
        )
        if sub is None:
            rev_not_submitted += 1
        else:
            if sub.review_status == "pending_review":
                rev_pending_review += 1
            elif sub.review_status == "returned":
                rev_returned += 1
            elif sub.review_status == "approved":
                rev_approved += 1

            # Count lateness on the latest submitted version of the milestone
            latest_version = session.scalar(
                select(SubmissionVersion)
                .where(SubmissionVersion.submission_id == sub.id)
                .order_by(SubmissionVersion.version_number.desc())
                .limit(1)
            )
            if latest_version is not None and latest_version.is_late:
                late_submissions_count += 1

    # 3. Upcoming deadlines (due_at >= now_utc)
    upcoming_candidates: list[UpcomingDeadlineItem] = []

    for task in tasks:
        if task.due_at is not None:
            task_due = task.due_at.astimezone(timezone.utc)
            if task_due >= now_utc:
                upcoming_candidates.append(
                    UpcomingDeadlineItem(
                        kind="task",
                        id=task.id,
                        title=task.title,
                        due_at=task_due,
                        status=task.status,  # type: ignore[arg-type]
                        priority=task.priority,  # type: ignore[arg-type]
                        assignee_id=task.assignee_id,
                    )
                )

    for milestone in milestones:
        ms_due = milestone.due_at.astimezone(timezone.utc)
        if ms_due >= now_utc:
            sub = session.scalar(
                select(MilestoneSubmission).where(
                    MilestoneSubmission.milestone_id == milestone.id
                )
            )
            r_status = sub.review_status if sub is not None else "not_submitted"
            upcoming_candidates.append(
                UpcomingDeadlineItem(
                    kind="milestone",
                    id=milestone.id,
                    title=milestone.name,
                    due_at=ms_due,
                    deadline_status=deadline_status(milestone.due_at, now=now_utc),
                    review_status=r_status,  # type: ignore[arg-type]
                )
            )

    upcoming_candidates.sort(
        key=lambda u: (u.due_at, 0 if u.kind == "milestone" else 1, u.id)
    )
    upcoming = upcoming_candidates[:10]

    return TeamProgressSummaryResponse(
        team_id=team.id,
        team_name=team.name,
        as_of=now_utc,
        tasks=TaskProgressCounts(
            total=total_tasks,
            todo=todo_tasks,
            in_progress=in_progress_tasks,
            done=done_tasks,
            overdue=overdue_tasks,
        ),
        tasks_by_assignee=tasks_by_assignee,
        milestones=MilestoneProgressCounts(
            total=total_milestones,
            scheduled=ms_scheduled,
            due_soon=ms_due_soon,
            overdue=ms_overdue,
            not_submitted=rev_not_submitted,
            pending_review=rev_pending_review,
            returned=rev_returned,
            approved=rev_approved,
        ),
        late_submissions=late_submissions_count,
        upcoming=upcoming,
    )


@router.get(
    "/teams/{team_id}/progress",
    response_model=TeamProgressSummaryResponse,
)
def get_team_progress(
    team_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> TeamProgressSummaryResponse:
    """Return derived task, milestone, and upcoming progress for a visible team."""
    team = get_visible_team(team_id, current_user, session)
    return _compute_team_progress(team, session)


@router.get(
    "/supervisor/teams/progress",
    response_model=list[TeamProgressSummaryResponse],
)
def get_supervisor_teams_progress(
    current_user: CurrentUser,
    session: DbSession,
) -> list[TeamProgressSummaryResponse]:
    """Return progress summaries for teams assigned to the calling supervisor."""
    if current_user.system_role != "supervisor" or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active supervisors can view supervisor team progress",
        )

    assigned_teams = session.scalars(
        select(Team)
        .join(SupervisorAssignment, SupervisorAssignment.team_id == Team.id)
        .where(SupervisorAssignment.supervisor_id == current_user.id)
        .order_by(Team.name.asc(), Team.id.asc())
    ).all()

    now = _now_utc()
    return [_compute_team_progress(team, session, as_of=now) for team in assigned_teams]
