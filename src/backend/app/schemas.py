"""Request and response schemas for authentication and team APIs."""

from datetime import datetime, timezone
from typing import Annotated, Literal
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


def _normalize_aware_utc(value: datetime) -> datetime:
    """Require an explicit timezone offset and normalize the instant to UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("due_at must be timezone-aware and include an offset")
    return value.astimezone(timezone.utc)
