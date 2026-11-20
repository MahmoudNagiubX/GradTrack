"""Request and response schemas for authentication and team APIs."""

from datetime import datetime, timezone
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


class RegistrationRequest(BaseModel):
    """Validated student registration fields; role is intentionally excluded."""

    email: EmailStr = Field(max_length=320)
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    password: Annotated[str, StringConstraints(min_length=16, max_length=128)]

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().casefold()
        return value

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_display_name(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class LoginRequest(BaseModel):
    """JSON credentials submitted to the manual login endpoint."""

    email: EmailStr = Field(max_length=320)
    password: Annotated[str, StringConstraints(min_length=16, max_length=128)]

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().casefold()
        return value


class PublicUser(BaseModel):
    """User fields safe to return from authentication endpoints."""

    model_config = {"from_attributes": True}

    id: UUID
    email: EmailStr
    display_name: str
    system_role: str


class AccessTokenResponse(BaseModel):
    """Short-lived bearer access token returned after successful login."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class TeamCreateRequest(BaseModel):
    """A student-provided team name; role fields are not accepted from clients."""

    model_config = {"extra": "forbid"}

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TeamMemberAddRequest(BaseModel):
    """The ID of an existing student to add as a regular team member."""

    model_config = {"extra": "forbid"}

    user_id: UUID


class SupervisorAssignmentRequest(BaseModel):
    """The account selected by an authorized coordinator."""

    model_config = {"extra": "forbid"}

    supervisor_id: UUID


class TeamMemberResponse(BaseModel):
    """Limited member fields visible within an authorized team."""

    user_id: UUID
    display_name: str
    role: Literal["member", "leader"]


class TeamResponse(BaseModel):
    """A team and its membership, returned only to authorized viewers."""

    id: UUID
    name: str
    created_at: datetime
    supervisor_id: UUID | None
    members: list[TeamMemberResponse]


class SupervisorAssignmentResponse(BaseModel):
    """The team's current supervisor assignment."""

    team_id: UUID
    supervisor_id: UUID
    assigned_at: datetime


class MilestoneCreateRequest(BaseModel):
    """Client fields accepted when an authorized writer creates a milestone."""

    model_config = {"extra": "forbid"}

    name: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    description: str | None = None
    due_at: datetime

    @field_validator("due_at")
    @classmethod
    def normalize_due_at(cls, value: datetime) -> datetime:
        return _normalize_aware_utc(value)


class MilestoneUpdateRequest(BaseModel):
    """Only the deadline can be changed during the milestone planning phase."""

    model_config = {"extra": "forbid"}

    due_at: datetime

    @field_validator("due_at")
    @classmethod
    def normalize_due_at(cls, value: datetime) -> datetime:
        return _normalize_aware_utc(value)


class MilestoneResponse(BaseModel):
    """A milestone with its non-persisted planning/deadline state."""

    id: UUID
    team_id: UUID
    name: str
    description: str | None
    due_at: datetime
    deadline_status: Literal["scheduled", "due_soon", "overdue"]
    created_at: datetime
    updated_at: datetime


class LinkSubmissionRequest(BaseModel):
    """A single externally hosted HTTPS submission link."""

    model_config = {"extra": "forbid"}

    url: Annotated[str, StringConstraints(min_length=8, max_length=2048)]

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        from app.submission_storage import validate_submission_url

        return validate_submission_url(value)


class SubmissionVersionResponse(BaseModel):
    """Public metadata for one immutable submission version."""

    id: UUID
    submission_id: UUID
    milestone_id: UUID
    team_id: UUID
    version_number: int
    submitted_by: UUID
    submitted_at: datetime
    deadline_at_submission: datetime
    is_late: bool
    source_type: Literal["file", "link"]
    original_filename: str | None
    file_size_bytes: int | None
    media_type: str | None
    url: str | None
    review_status: Literal["pending_review", "returned", "approved"]


class PendingSubmissionResponse(SubmissionVersionResponse):
    """A latest pending version with the team, milestone, and submitter labels."""

    team_name: str
    milestone_name: str
    submitter_name: str


class ReviewDecisionRequest(BaseModel):
    """A supervisor's immutable decision for one pending version."""

    model_config = {"extra": "forbid"}

    decision: Literal["approved", "returned"]
    feedback: Annotated[str | None, Field(max_length=2000)] = None

    @field_validator("feedback")
    @classmethod
    def trim_optional_feedback(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def require_return_feedback(self) -> "ReviewDecisionRequest":
        if self.decision == "returned" and self.feedback is None:
            raise ValueError("Written feedback is required to return a submission")
        return self


class SupervisorReviewResponse(BaseModel):
    """The immutable decision, reviewer attribution, and feedback for one version."""

    id: UUID
    version_id: UUID
    reviewer_id: UUID
    decision: Literal["approved", "returned"]
    feedback: str | None
    reviewed_at: datetime


class TaskCreateRequest(BaseModel):
    """Client fields accepted when creating a team task."""

    model_config = {"extra": "forbid"}

    title: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]
    description: str | None = None
    assignee_id: UUID
    priority: Literal["low", "medium", "high"] = "medium"
    due_at: datetime | None = None
    estimated_minutes: Annotated[int | None, Field(ge=1, le=525600)] = None
    milestone_id: UUID | None = None
    parent_task_id: UUID | None = None

    @field_validator("due_at")
    @classmethod
    def normalize_due_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _normalize_aware_utc(value)


class TaskUpdateRequest(BaseModel):
    """Client fields accepted when updating task metadata or assignment."""

    model_config = {"extra": "forbid"}

    title: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
        ]
        | None
    ) = None
    description: str | None = None
    assignee_id: UUID | None = None
    priority: Literal["low", "medium", "high"] | None = None
    due_at: datetime | None = None
    estimated_minutes: Annotated[int | None, Field(ge=1, le=525600)] = None
    milestone_id: UUID | None = None
    parent_task_id: UUID | None = None

    @field_validator("due_at")
    @classmethod
    def normalize_due_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _normalize_aware_utc(value)


class TaskStatusUpdateRequest(BaseModel):
    """Status change requested by the assignee or team leader."""

    model_config = {"extra": "forbid"}

    status: Literal["todo", "in_progress", "done"]


class TaskResponse(BaseModel):
    """Public representation of a team task."""

    id: UUID
    team_id: UUID
    title: str
    description: str | None
    status: Literal["todo", "in_progress", "done"]
    priority: Literal["low", "medium", "high"]
    created_by: UUID
    assignee_id: UUID
    updated_by: UUID
    completed_by: UUID | None
    due_at: datetime | None
    estimated_minutes: int | None
    milestone_id: UUID | None
    parent_task_id: UUID | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskChecklistItemCreateRequest(BaseModel):
    """Client fields accepted when adding a checklist item."""

    model_config = {"extra": "forbid"}

    item_text: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    ]


class TaskChecklistItemUpdateRequest(BaseModel):
    """Updates to checklist item text or completion status."""

    model_config = {"extra": "forbid"}

    is_done: bool | None = None
    item_text: (
        Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
        ]
        | None
    ) = None


class TaskChecklistItemResponse(BaseModel):
    """Representation of one checklist item."""

    id: UUID
    task_id: UUID
    item_text: str
    is_done: bool
    created_by: UUID
    completed_by: UUID | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskDetailResponse(TaskResponse):
    """Detailed task representation including checklist items and child subtasks."""

    checklist_items: list[TaskChecklistItemResponse]
    subtasks: list[TaskResponse]


class TaskActivityResponse(BaseModel):
    """One immutable activity entry for a task."""

    id: UUID
    task_id: UUID
    actor_id: UUID
    actor_name: str
    event_type: Literal[
        "created",
        "assigned",
        "reassigned",
        "status_changed",
        "reopened",
        "completed",
        "updated",
        "checklist_item_added",
        "checklist_item_updated",
        "comment_added",
        "attachment_uploaded",
    ]
    old_value: str | None
    new_value: str | None
    details: str | None
    created_at: datetime


class TaskCommentCreateRequest(BaseModel):
    """Client fields accepted when posting a task comment."""

    model_config = {"extra": "forbid"}

    content: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    ]


class TaskCommentResponse(BaseModel):
    """Public representation of one task comment."""

    id: UUID
    task_id: UUID
    author_id: UUID
    author_name: str
    content: str
    created_at: datetime


class TaskAttachmentResponse(BaseModel):
    """Public metadata for a private task attachment."""

    id: UUID
    task_id: UUID
    uploader_id: UUID
    uploader_name: str
    original_filename: str
    file_size_bytes: int
    media_type: str
    created_at: datetime


def _normalize_aware_utc(value: datetime) -> datetime:
    """Require an explicit timezone offset and normalize the instant to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("due_at must be timezone-aware and include an offset")
    return value.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Phase 7A: Timeline / Calendar Data & Progress Dashboards
# ---------------------------------------------------------------------------


class CalendarTaskItem(BaseModel):
    """Calendar projection for a team task with an offset-aware due date."""

    kind: Literal["task"] = "task"
    id: UUID
    team_id: UUID
    title: str
    due_at: datetime
    status: Literal["todo", "in_progress", "done"]
    priority: Literal["low", "medium", "high"]
    assignee_id: UUID
    milestone_id: UUID | None = None
    parent_task_id: UUID | None = None


class CalendarMilestoneItem(BaseModel):
    """Calendar projection for a team milestone planning deadline."""

    kind: Literal["milestone"] = "milestone"
    id: UUID
    team_id: UUID
    title: str
    due_at: datetime
    deadline_status: Literal["scheduled", "due_soon", "overdue"]
    review_status: Literal["not_submitted", "pending_review", "returned", "approved"]


CalendarItemResponse = Annotated[
    Union[CalendarTaskItem, CalendarMilestoneItem],
    Field(discriminator="kind"),
]


class TaskProgressCounts(BaseModel):
    """Derived progress metrics across a team's tasks."""

    total: int
    todo: int
    in_progress: int
    done: int
    overdue: int


class AssigneeTaskProgress(BaseModel):
    """Per-member task breakdown within a team."""

    assignee_id: UUID
    assignee_name: str
    total: int
    todo: int
    in_progress: int
    done: int
    overdue: int


class MilestoneProgressCounts(BaseModel):
    """Derived planning deadline and review states for team milestones."""

    total: int
    scheduled: int
    due_soon: int
    overdue: int
    not_submitted: int
    pending_review: int
    returned: int
    approved: int


class UpcomingDeadlineItem(BaseModel):
    """A nearest future task or milestone deadline."""

    kind: Literal["task", "milestone"]
    id: UUID
    title: str
    due_at: datetime
    # Task-specific (None for milestone)
    status: Literal["todo", "in_progress", "done"] | None = None
    priority: Literal["low", "medium", "high"] | None = None
    assignee_id: UUID | None = None
    # Milestone-specific (None for task)
    deadline_status: Literal["scheduled", "due_soon", "overdue"] | None = None
    review_status: (
        Literal["not_submitted", "pending_review", "returned", "approved"] | None
    ) = None


class TeamProgressSummaryResponse(BaseModel):
    """Derived progress summary for an authorized team."""

    team_id: UUID
    team_name: str
    as_of: datetime
    tasks: TaskProgressCounts
    tasks_by_assignee: list[AssigneeTaskProgress]
    milestones: MilestoneProgressCounts
    late_submissions: int
    upcoming: list[UpcomingDeadlineItem]


# ---------------------------------------------------------------------------
# Phase 7B: In-App Deadline Reminders Schemas (GT-30)
# ---------------------------------------------------------------------------

ReminderKind = Literal[
    "task_due_soon",
    "task_overdue",
    "milestone_due_soon",
    "milestone_overdue",
]


class ReminderItemResponse(BaseModel):
    """Derived in-app reminder for an actionable task or milestone deadline."""

    id: UUID
    kind: ReminderKind
    source_id: UUID
    team_id: UUID
    title: str
    due_at: datetime
    is_read: bool
    read_at: datetime | None = None


class MarkReminderReadResponse(BaseModel):
    """Receipt response when marking an active reminder as read."""

    status: str = "ok"
    reminder_id: UUID
    read_at: datetime
