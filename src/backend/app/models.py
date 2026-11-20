"""Core SQLAlchemy models for users, teams, memberships, and assignments."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Metadata registry for the GradTrack SQLAlchemy models."""


class User(Base):
    """An account with one system role."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint(
            "email = lower(btrim(email))", name="ck_users_email_normalized"
        ),
        CheckConstraint(
            "length(btrim(display_name)) > 0", name="ck_users_display_name_nonempty"
        ),
        CheckConstraint(
            "length(password_hash) > 0", name="ck_users_password_hash_nonempty"
        ),
        CheckConstraint(
            "system_role IN ('student', 'supervisor', 'coordinator')",
            name="ck_users_system_role",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    system_role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="student", server_default="student"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Team(Base):
    """A team that may have no current supervisor assignment."""

    __tablename__ = "teams"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_teams_name_nonempty"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TeamMembership(Base):
    """A user's role within one team; leadership is not a system role."""

    __tablename__ = "team_memberships"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_memberships_team_user"),
        CheckConstraint(
            "role IN ('member', 'leader')", name="ck_team_memberships_role"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.id", name="fk_team_memberships_team"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_team_memberships_user"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default="member", server_default="member"
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SupervisorAssignment(Base):
    """A team's single current supervisor assignment, if one exists."""

    __tablename__ = "supervisor_assignments"

    # One row per assigned team; no row means the team is unassigned.
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.id", name="fk_supervisor_assignments_team"),
        primary_key=True,
    )
    supervisor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_supervisor_assignments_user"),
        nullable=False,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Milestone(Base):
    """A team-owned milestone with one currently editable deadline."""

    __tablename__ = "milestones"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_milestones_name_nonempty"),
        CheckConstraint("name = btrim(name)", name="ck_milestones_name_trimmed"),
        CheckConstraint("length(name) <= 200", name="ck_milestones_name_length"),
        Index("ix_milestones_team_due_at", "team_id", "due_at"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.id", name="fk_milestones_team"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MilestoneSubmission(Base):
    """The single submission thread currently accepted for one milestone."""

    __tablename__ = "milestone_submissions"
    __table_args__ = (
        UniqueConstraint("milestone_id", name="uq_milestone_submissions_milestone"),
        CheckConstraint(
            "review_status IN ('pending_review', 'returned', 'approved')",
            name="ck_milestone_submissions_review_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    milestone_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("milestones.id", name="fk_milestone_submissions_milestone"),
        nullable=False,
    )
    review_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending_review",
        server_default="pending_review",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SubmissionVersion(Base):
    """An immutable accepted submission version and its deadline snapshot."""

    __tablename__ = "submission_versions"
    __table_args__ = (
        UniqueConstraint(
            "submission_id", "version_number", name="uq_submission_versions_number"
        ),
        CheckConstraint(
            "version_number >= 1", name="ck_submission_versions_number_positive"
        ),
        CheckConstraint(
            "source_type IN ('file', 'link')", name="ck_submission_versions_source_type"
        ),
        CheckConstraint(
            "(source_type = 'file' AND storage_key IS NOT NULL AND url IS NULL "
            "AND original_filename IS NOT NULL AND file_size_bytes > 0 "
            "AND file_size_bytes <= 20971520 AND media_type IS NOT NULL) OR "
            "(source_type = 'link' AND url IS NOT NULL AND storage_key IS NULL "
            "AND original_filename IS NULL AND file_size_bytes IS NULL "
            "AND media_type IS NULL)",
            name="ck_submission_versions_exactly_one_source",
        ),
        Index(
            "ix_submission_versions_submission_submitted",
            "submission_id",
            "submitted_at",
            "id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    submission_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "milestone_submissions.id", name="fk_submission_versions_submission"
        ),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_submission_versions_submitted_by"),
        nullable=False,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    deadline_at_submission: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(127), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)


class SupervisorReview(Base):
    """One immutable review decision for a single submission version."""

    __tablename__ = "supervisor_reviews"
    __table_args__ = (
        UniqueConstraint("version_id", name="uq_supervisor_reviews_version"),
        CheckConstraint(
            "decision IN ('approved', 'returned')",
            name="ck_supervisor_reviews_decision",
        ),
        CheckConstraint(
            "(decision = 'returned' AND feedback IS NOT NULL "
            "AND feedback = btrim(feedback) AND length(feedback) BETWEEN 1 AND 2000) "
            "OR (decision = 'approved' AND (feedback IS NULL OR "
            "(feedback = btrim(feedback) AND length(feedback) <= 2000)))",
            name="ck_supervisor_reviews_feedback",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("submission_versions.id", name="fk_supervisor_reviews_version"),
        nullable=False,
    )
    reviewer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_supervisor_reviews_reviewer"),
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Task(Base):
    """A team-owned task with assignment, status, and milestone association."""

    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("length(btrim(title)) > 0", name="ck_tasks_title_nonempty"),
        CheckConstraint("title = btrim(title)", name="ck_tasks_title_trimmed"),
        CheckConstraint("length(title) <= 200", name="ck_tasks_title_length"),
        CheckConstraint(
            "status IN ('todo', 'in_progress', 'done')", name="ck_tasks_status"
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high')", name="ck_tasks_priority"
        ),
        CheckConstraint(
            "estimated_minutes IS NULL OR "
            "(estimated_minutes > 0 AND estimated_minutes <= 525600)",
            name="ck_tasks_estimated_minutes_range",
        ),
        CheckConstraint(
            "parent_task_id IS NULL OR parent_task_id != id",
            name="ck_tasks_no_self_parent",
        ),
        CheckConstraint(
            "(status = 'done' AND completed_at IS NOT NULL "
            "AND completed_by IS NOT NULL) OR "
            "(status != 'done' AND completed_at IS NULL AND completed_by IS NULL)",
            name="ck_tasks_completion_consistency",
        ),
        Index("ix_tasks_team_status", "team_id", "status"),
        Index("ix_tasks_team_assignee", "team_id", "assignee_id"),
        Index("ix_tasks_team_due_at", "team_id", "due_at"),
        Index("ix_tasks_team_milestone", "team_id", "milestone_id"),
        Index("ix_tasks_team_parent", "team_id", "parent_task_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    team_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("teams.id", name="fk_tasks_team"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="todo", server_default="todo"
    )
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="medium", server_default="medium"
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_tasks_created_by"),
        nullable=False,
    )
    assignee_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_tasks_assignee"),
        nullable=False,
    )
    updated_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_tasks_updated_by"),
        nullable=False,
    )
    completed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_tasks_completed_by"),
        nullable=True,
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    milestone_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("milestones.id", name="fk_tasks_milestone"),
        nullable=True,
    )
    parent_task_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", name="fk_tasks_parent"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TaskChecklistItem(Base):
    """A single checklist item belonging to a task."""

    __tablename__ = "task_checklist_items"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(item_text)) > 0",
            name="ck_task_checklist_items_text_nonempty",
        ),
        CheckConstraint(
            "item_text = btrim(item_text)",
            name="ck_task_checklist_items_text_trimmed",
        ),
        CheckConstraint(
            "length(item_text) <= 200",
            name="ck_task_checklist_items_text_length",
        ),
        CheckConstraint(
            "(is_done = true AND completed_at IS NOT NULL "
            "AND completed_by IS NOT NULL) OR "
            "(is_done = false AND completed_at IS NULL AND completed_by IS NULL)",
            name="ck_task_checklist_items_done_consistency",
        ),
        Index("ix_task_checklist_items_task_id", "task_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", name="fk_task_checklist_items_task", ondelete="CASCADE"),
        nullable=False,
    )
    item_text: Mapped[str] = mapped_column(String(200), nullable=False)
    is_done: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_task_checklist_items_created_by"),
        nullable=False,
    )
    completed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_task_checklist_items_completed_by"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TaskActivity(Base):
    """An append-only audit event for one task mutation."""

    __tablename__ = "task_activities"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'created', 'assigned', 'reassigned', 'status_changed', "
            "'reopened', 'completed', 'updated', 'checklist_item_added', "
            "'checklist_item_updated', 'comment_added', 'attachment_uploaded'"
            ")",
            name="ck_task_activities_event_type",
        ),
        Index("ix_task_activities_task_seq", "task_id", "sequence_id"),
        Index("ix_task_activities_task_created", "task_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    sequence_id: Mapped[int] = mapped_column(
        BigInteger, Identity(start=1), nullable=False, unique=True
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", name="fk_task_activities_task", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_task_activities_actor"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    old_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TaskComment(Base):
    """An append-only comment posted by an active team student member."""

    __tablename__ = "task_comments"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(content)) > 0", name="ck_task_comments_content_nonempty"
        ),
        CheckConstraint(
            "content = btrim(content)", name="ck_task_comments_content_trimmed"
        ),
        CheckConstraint(
            "length(content) <= 2000", name="ck_task_comments_content_length"
        ),
        Index("ix_task_comments_task_created", "task_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", name="fk_task_comments_task", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_task_comments_author"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TaskAttachment(Base):
    """A private validated file or image attached to a team task."""

    __tablename__ = "task_attachments"
    __table_args__ = (
        CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 20971520",
            name="ck_task_attachments_file_size",
        ),
        CheckConstraint(
            "length(btrim(original_filename)) > 0",
            name="ck_task_attachments_filename_nonempty",
        ),
        CheckConstraint(
            "length(storage_key) = 64",
            name="ck_task_attachments_storage_key_length",
        ),
        Index("ix_task_attachments_task_created", "task_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tasks.id", name="fk_task_attachments_task", ondelete="CASCADE"),
        nullable=False,
    )
    uploader_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_task_attachments_uploader"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    media_type: Mapped[str] = mapped_column(String(127), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
