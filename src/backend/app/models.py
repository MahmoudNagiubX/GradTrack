"""Core SQLAlchemy models for users, teams, memberships, and assignments."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
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
