"""Create core user, team, membership, and supervisor assignment tables."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "gt52_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the four Phase 1 persistence tables."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column(
            "system_role",
            sa.String(length=32),
            server_default="student",
            nullable=False,
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "email = lower(btrim(email))", name="ck_users_email_normalized"
        ),
        sa.CheckConstraint(
            "length(btrim(display_name)) > 0", name="ck_users_display_name_nonempty"
        ),
        sa.CheckConstraint(
            "length(password_hash) > 0", name="ck_users_password_hash_nonempty"
        ),
        sa.CheckConstraint(
            "system_role IN ('student', 'supervisor', 'coordinator')",
            name="ck_users_system_role",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_teams_name_nonempty"),
        sa.PrimaryKeyConstraint("id", name="pk_teams"),
    )
    op.create_table(
        "team_memberships",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("team_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "role", sa.String(length=16), server_default="member", nullable=False
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('member', 'leader')", name="ck_team_memberships_role"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name="fk_team_memberships_team"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_team_memberships_user"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_team_memberships"),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_memberships_team_user"),
    )
    op.create_table(
        "supervisor_assignments",
        sa.Column("team_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("supervisor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["supervisor_id"], ["users.id"], name="fk_supervisor_assignments_user"
        ),
        sa.ForeignKeyConstraint(
            ["team_id"], ["teams.id"], name="fk_supervisor_assignments_team"
        ),
        sa.PrimaryKeyConstraint("team_id", name="pk_supervisor_assignments"),
    )


def downgrade() -> None:
    """Remove the Phase 1 tables in foreign-key-safe order."""
    op.drop_table("supervisor_assignments")
    op.drop_table("team_memberships")
    op.drop_table("teams")
    op.drop_table("users")
