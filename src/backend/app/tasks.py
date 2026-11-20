"""Team-scoped task assignment, progress, checklists, and activity history."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_team_membership
from app.database import get_db_session
from app.models import (
    Milestone,
    Task,
    TaskActivity,
    TaskChecklistItem,
    TeamMembership,
    User,
)
from app.schemas import (
    TaskActivityResponse,
    TaskChecklistItemCreateRequest,
    TaskChecklistItemResponse,
    TaskChecklistItemUpdateRequest,
    TaskCreateRequest,
    TaskDetailResponse,
    TaskResponse,
    TaskStatusUpdateRequest,
    TaskUpdateRequest,
    _normalize_aware_utc,
)
from app.teams import get_visible_team

router = APIRouter(prefix="/teams/{team_id}/tasks", tags=["tasks"])

DbSession = Annotated[Session, Depends(get_db_session)]


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _serialize_task(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        team_id=task.team_id,
        title=task.title,
        description=task.description,
        status=task.status,  # type: ignore[arg-type]
        priority=task.priority,  # type: ignore[arg-type]
        created_by=task.created_by,
        assignee_id=task.assignee_id,
        updated_by=task.updated_by,
        completed_by=task.completed_by,
        due_at=_as_utc(task.due_at),
        estimated_minutes=task.estimated_minutes,
        milestone_id=task.milestone_id,
        parent_task_id=task.parent_task_id,
        completed_at=_as_utc(task.completed_at),
        created_at=_as_utc(task.created_at),  # type: ignore[arg-type]
        updated_at=_as_utc(task.updated_at),  # type: ignore[arg-type]
    )


def _serialize_checklist_item(item: TaskChecklistItem) -> TaskChecklistItemResponse:
    return TaskChecklistItemResponse(
        id=item.id,
        task_id=item.task_id,
        item_text=item.item_text,
        is_done=item.is_done,
        created_by=item.created_by,
        completed_by=item.completed_by,
        completed_at=_as_utc(item.completed_at),
        created_at=_as_utc(item.created_at),  # type: ignore[arg-type]
        updated_at=_as_utc(item.updated_at),  # type: ignore[arg-type]
    )


def _require_team_leader_role(
    team_id: UUID, current_user: User, session: Session
) -> TeamMembership:
    membership = get_current_team_membership(team_id, current_user, session)
    if membership.role != "leader":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team leaders can perform this action",
        )
    return membership


def _validate_assignee_in_team(
    team_id: UUID, assignee_id: UUID, session: Session
) -> User:
    assignee = session.get(User, assignee_id)
    if assignee is None or not assignee.is_active or assignee.system_role != "student":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee must be an active student account",
        )
    membership = session.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == assignee_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignee must be a member of this team",
        )
    return assignee


def _validate_milestone_in_team(
    team_id: UUID, milestone_id: UUID | None, session: Session
) -> Milestone | None:
    if milestone_id is None:
        return None
    milestone = session.get(Milestone, milestone_id)
    if milestone is None or milestone.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Milestone does not belong to this team or does not exist",
        )
    return milestone


def _validate_parent_task_in_team(
    team_id: UUID,
    parent_task_id: UUID | None,
    current_task_id: UUID | None,
    session: Session,
) -> Task | None:
    if parent_task_id is None:
        return None
    if current_task_id is not None and parent_task_id == current_task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A task cannot be its own parent",
        )
    parent = session.get(Task, parent_task_id)
    if parent is None or parent.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent task does not belong to this team or does not exist",
        )
    if parent.parent_task_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subtasks cannot be nested more than one level",
        )
    return parent


def _task_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Task not found",
    )


@router.get("", response_model=list[TaskResponse])
def list_team_tasks(
    team_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
    status_filter: Annotated[
        Literal["todo", "in_progress", "done"] | None, Query(alias="status")
    ] = None,
    assignee_id: UUID | None = None,
    priority: Literal["low", "medium", "high"] | None = None,
    milestone_id: UUID | None = None,
    due_before: datetime | None = None,
    due_after: datetime | None = None,
    parent_task_id: UUID | None = None,
) -> list[TaskResponse]:
    """List tasks belonging to this team with optional filters."""
    get_visible_team(team_id, current_user, session)

    query = select(Task).where(Task.team_id == team_id)

    if status_filter is not None:
        query = query.where(Task.status == status_filter)
    if assignee_id is not None:
        query = query.where(Task.assignee_id == assignee_id)
    if priority is not None:
        query = query.where(Task.priority == priority)
    if milestone_id is not None:
        query = query.where(Task.milestone_id == milestone_id)
    if due_before is not None:
        due_before_utc = _normalize_aware_utc(due_before)
        query = query.where(Task.due_at <= due_before_utc)
    if due_after is not None:
        due_after_utc = _normalize_aware_utc(due_after)
        query = query.where(Task.due_at >= due_after_utc)
    if parent_task_id is not None:
        query = query.where(Task.parent_task_id == parent_task_id)

    query = query.order_by(Task.created_at.asc(), Task.id.asc())
    tasks = session.scalars(query).all()
    return [_serialize_task(task) for task in tasks]


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    team_id: UUID,
    payload: TaskCreateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskResponse:
    """Create a task and assign it to an active student member of the team."""
    get_visible_team(team_id, current_user, session)
    _require_team_leader_role(team_id, current_user, session)

    assignee = _validate_assignee_in_team(team_id, payload.assignee_id, session)
    _validate_milestone_in_team(team_id, payload.milestone_id, session)
    _validate_parent_task_in_team(team_id, payload.parent_task_id, None, session)

    task = Task(
        team_id=team_id,
        title=payload.title,
        description=payload.description,
        status="todo",
        priority=payload.priority,
        created_by=current_user.id,
        assignee_id=payload.assignee_id,
        updated_by=current_user.id,
        completed_by=None,
        due_at=payload.due_at,
        estimated_minutes=payload.estimated_minutes,
        milestone_id=payload.milestone_id,
        parent_task_id=payload.parent_task_id,
        completed_at=None,
    )
    session.add(task)
    session.flush()

    activity = TaskActivity(
        task_id=task.id,
        actor_id=current_user.id,
        event_type="created",
        old_value=None,
        new_value="todo",
        details=f"Task created and assigned to {assignee.display_name}",
    )
    session.add(activity)
    session.commit()
    session.refresh(task)

    return _serialize_task(task)


@router.get("/{task_id}", response_model=TaskDetailResponse)
def get_task_detail(
    team_id: UUID,
    task_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskDetailResponse:
    """Get full task details including checklist items and direct subtasks."""
    get_visible_team(team_id, current_user, session)

    task = session.scalar(
        select(Task).where(Task.id == task_id, Task.team_id == team_id)
    )
    if task is None:
        raise _task_not_found()

    checklist_items = session.scalars(
        select(TaskChecklistItem)
        .where(TaskChecklistItem.task_id == task_id)
        .order_by(TaskChecklistItem.created_at.asc(), TaskChecklistItem.id.asc())
    ).all()

    subtasks = session.scalars(
        select(Task)
        .where(Task.parent_task_id == task_id, Task.team_id == team_id)
        .order_by(Task.created_at.asc(), Task.id.asc())
    ).all()

    serialized_task = _serialize_task(task)
    return TaskDetailResponse(
        **serialized_task.model_dump(),
        checklist_items=[_serialize_checklist_item(item) for item in checklist_items],
        subtasks=[_serialize_task(subtask) for subtask in subtasks],
    )


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task_metadata(
    team_id: UUID,
    task_id: UUID,
    payload: TaskUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskResponse:
    """Update task metadata, priority, due date, milestone, parent, or assignment."""
    get_visible_team(team_id, current_user, session)
    _require_team_leader_role(team_id, current_user, session)

    task = session.scalar(
        select(Task)
        .where(Task.id == task_id, Task.team_id == team_id)
        .with_for_update()
    )
    if task is None:
        raise _task_not_found()

    fields_set = payload.model_fields_set
    if not fields_set:
        return _serialize_task(task)

    updated_field_names: list[str] = []

    # Assignee check
    if "assignee_id" in fields_set and payload.assignee_id is not None:
        if payload.assignee_id != task.assignee_id:
            new_assignee = _validate_assignee_in_team(
                team_id, payload.assignee_id, session
            )
            old_assignee_id = task.assignee_id
            task.assignee_id = payload.assignee_id
            session.add(
                TaskActivity(
                    task_id=task.id,
                    actor_id=current_user.id,
                    event_type="reassigned",
                    old_value=str(old_assignee_id),
                    new_value=str(payload.assignee_id),
                    details=f"Reassigned to {new_assignee.display_name}",
                )
            )
            updated_field_names.append("assignee")

    # Milestone check
    if "milestone_id" in fields_set:
        if payload.milestone_id != task.milestone_id:
            _validate_milestone_in_team(team_id, payload.milestone_id, session)
            task.milestone_id = payload.milestone_id
            updated_field_names.append("milestone")

    # Parent task check
    if "parent_task_id" in fields_set:
        if payload.parent_task_id != task.parent_task_id:
            if payload.parent_task_id is not None:
                _validate_parent_task_in_team(
                    team_id, payload.parent_task_id, task.id, session
                )
                has_children = session.scalar(
                    select(Task.id).where(Task.parent_task_id == task.id).limit(1)
                )
                if has_children is not None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="A parent task with subtasks cannot become a subtask",
                    )
            task.parent_task_id = payload.parent_task_id
            updated_field_names.append("parent_task")

    # Title check
    if "title" in fields_set and payload.title is not None:
        if payload.title != task.title:
            task.title = payload.title
            updated_field_names.append("title")

    # Description check
    if "description" in fields_set:
        if payload.description != task.description:
            task.description = payload.description
            updated_field_names.append("description")

    # Priority check
    if "priority" in fields_set and payload.priority is not None:
        if payload.priority != task.priority:
            task.priority = payload.priority
            updated_field_names.append("priority")

    # Due at check
    if "due_at" in fields_set:
        if payload.due_at != task.due_at:
            task.due_at = payload.due_at
            updated_field_names.append("due_at")

    # Estimated minutes check
    if "estimated_minutes" in fields_set:
        if payload.estimated_minutes != task.estimated_minutes:
            task.estimated_minutes = payload.estimated_minutes
            updated_field_names.append("estimated_minutes")

    if updated_field_names:
        task.updated_by = current_user.id
        non_reassign_changes = [f for f in updated_field_names if f != "assignee"]
        if non_reassign_changes:
            session.add(
                TaskActivity(
                    task_id=task.id,
                    actor_id=current_user.id,
                    event_type="updated",
                    old_value=None,
                    new_value=None,
                    details=f"Updated: {', '.join(non_reassign_changes)}",
                )
            )
        session.commit()
        session.refresh(task)

    return _serialize_task(task)


@router.patch("/{task_id}/status", response_model=TaskResponse)
def update_task_status(
    team_id: UUID,
    task_id: UUID,
    payload: TaskStatusUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskResponse:
    """Update task progress (todo <-> in_progress <-> done) by assignee or leader."""
    get_visible_team(team_id, current_user, session)

    task = session.scalar(
        select(Task)
        .where(Task.id == task_id, Task.team_id == team_id)
        .with_for_update()
    )
    if task is None:
        raise _task_not_found()

    # Authorization check
    is_leader = False
    membership = session.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
        )
    )
    if membership is not None and membership.role == "leader":
        is_leader = True

    is_assignee = task.assignee_id == current_user.id
    if not (is_leader or is_assignee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned member or team leader can update task status",
        )

    # Recheck assignee membership eligibility at mutation time
    if is_assignee and not is_leader:
        assignee_membership = session.scalar(
            select(TeamMembership).where(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == current_user.id,
            )
        )
        if assignee_membership is None or not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Assignee is no longer an active member of this team",
            )

    old_status = task.status
    new_status = payload.status

    # Idempotent no-op check: do not record duplicate event
    if old_status == new_status:
        return _serialize_task(task)

    now = datetime.now(timezone.utc)
    if new_status == "done":
        task.status = "done"
        task.completed_by = current_user.id
        task.completed_at = now
        event_type = "completed"
    elif old_status == "done":
        # Reopening clears completion metadata
        task.status = new_status
        task.completed_by = None
        task.completed_at = None
        event_type = "reopened"
    else:
        task.status = new_status
        event_type = "status_changed"

    task.updated_by = current_user.id

    session.add(
        TaskActivity(
            task_id=task.id,
            actor_id=current_user.id,
            event_type=event_type,
            old_value=old_status,
            new_value=new_status,
            details=f"Status changed from {old_status} to {new_status}",
        )
    )
    session.commit()
    session.refresh(task)

    return _serialize_task(task)


@router.get("/{task_id}/activity", response_model=list[TaskActivityResponse])
def get_task_activity(
    team_id: UUID,
    task_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> list[TaskActivityResponse]:
    """Get the chronological audit activity for a team task."""
    get_visible_team(team_id, current_user, session)

    task = session.scalar(
        select(Task.id).where(Task.id == task_id, Task.team_id == team_id)
    )
    if task is None:
        raise _task_not_found()

    rows = session.execute(
        select(
            TaskActivity.id,
            TaskActivity.task_id,
            TaskActivity.actor_id,
            User.display_name,
            TaskActivity.event_type,
            TaskActivity.old_value,
            TaskActivity.new_value,
            TaskActivity.details,
            TaskActivity.created_at,
        )
        .join(User, User.id == TaskActivity.actor_id)
        .where(TaskActivity.task_id == task_id)
        .order_by(TaskActivity.sequence_id.asc())
    ).all()

    return [
        TaskActivityResponse(
            id=row[0],
            task_id=row[1],
            actor_id=row[2],
            actor_name=row[3],
            event_type=row[4],
            old_value=row[5],
            new_value=row[6],
            details=row[7],
            created_at=_as_utc(row[8]),  # type: ignore[arg-type]
        )
        for row in rows
    ]


@router.post(
    "/{task_id}/checklist",
    response_model=TaskChecklistItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_checklist_item(
    team_id: UUID,
    task_id: UUID,
    payload: TaskChecklistItemCreateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskChecklistItemResponse:
    """Active team leader adds a checklist item to a task."""
    get_visible_team(team_id, current_user, session)
    _require_team_leader_role(team_id, current_user, session)

    task = session.scalar(
        select(Task)
        .where(Task.id == task_id, Task.team_id == team_id)
        .with_for_update()
    )
    if task is None:
        raise _task_not_found()

    item = TaskChecklistItem(
        task_id=task.id,
        item_text=payload.item_text,
        is_done=False,
        created_by=current_user.id,
        completed_by=None,
        completed_at=None,
    )
    session.add(item)
    session.flush()

    session.add(
        TaskActivity(
            task_id=task.id,
            actor_id=current_user.id,
            event_type="checklist_item_added",
            old_value=None,
            new_value=None,
            details=f"Added checklist item: '{payload.item_text}'",
        )
    )
    task.updated_by = current_user.id
    session.commit()
    session.refresh(item)

    return _serialize_checklist_item(item)


@router.patch(
    "/{task_id}/checklist/{item_id}",
    response_model=TaskChecklistItemResponse,
)
def update_checklist_item(
    team_id: UUID,
    task_id: UUID,
    item_id: UUID,
    payload: TaskChecklistItemUpdateRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> TaskChecklistItemResponse:
    """Update checklist completion (assignee or leader) or item text (leader only)."""
    get_visible_team(team_id, current_user, session)

    task = session.scalar(
        select(Task)
        .where(Task.id == task_id, Task.team_id == team_id)
        .with_for_update()
    )
    if task is None:
        raise _task_not_found()

    item = session.scalar(
        select(TaskChecklistItem)
        .where(
            TaskChecklistItem.id == item_id,
            TaskChecklistItem.task_id == task_id,
        )
        .with_for_update()
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checklist item not found",
        )

    # Permission check
    is_leader = False
    membership = session.scalar(
        select(TeamMembership).where(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == current_user.id,
        )
    )
    if membership is not None and membership.role == "leader":
        is_leader = True

    is_assignee = task.assignee_id == current_user.id
    if not (is_leader or is_assignee):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned member or team leader can update checklist items",
        )

    fields_set = payload.model_fields_set
    if not fields_set:
        return _serialize_checklist_item(item)

    # Editing text requires team leader
    if "item_text" in fields_set and payload.item_text is not None:
        if not is_leader:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the team leader can edit checklist item text",
            )
        if payload.item_text != item.item_text:
            item.item_text = payload.item_text

    # Updating done status
    if "is_done" in fields_set and payload.is_done is not None:
        if payload.is_done != item.is_done:
            now = datetime.now(timezone.utc)
            if payload.is_done:
                item.is_done = True
                item.completed_by = current_user.id
                item.completed_at = now
            else:
                item.is_done = False
                item.completed_by = None
                item.completed_at = None

            state_label = "done" if payload.is_done else "incomplete"
            session.add(
                TaskActivity(
                    task_id=task.id,
                    actor_id=current_user.id,
                    event_type="checklist_item_updated",
                    old_value=str(not payload.is_done).lower(),
                    new_value=str(payload.is_done).lower(),
                    details=f"Checklist item '{item.item_text}' marked {state_label}",
                )
            )

    task.updated_by = current_user.id
    session.commit()
    session.refresh(item)

    return _serialize_checklist_item(item)
