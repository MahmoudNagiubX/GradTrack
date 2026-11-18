"""Add team-owned milestones and deadline fields."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "gt18_19_0002"
down_revision: Union[str, None] = "gt52_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the Phase 4 milestone table without modifying prior tables."""
    op.create_table(
        "milestones",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("team_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
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
            "length(btrim(name)) > 0", name="ck_milestones_name_nonempty"
        ),
        sa.CheckConstraint("name = btrim(name)", name="ck_milestones_name_trimmed"),
        sa.CheckConstraint("length(name) <= 200", name="ck_milestones_name_length"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_milestones_team"),
        sa.PrimaryKeyConstraint("id", name="pk_milestones"),
    )
    op.create_index(
        "ix_milestones_team_due_at",
        "milestones",
        ["team_id", "due_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove only the Phase 4 milestone table and its index."""
    op.drop_index("ix_milestones_team_due_at", table_name="milestones")
    op.drop_table("milestones")
