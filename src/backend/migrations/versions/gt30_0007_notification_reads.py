"""Add notification_read_receipts table for in-app deadline reminders."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "gt30_0007"
down_revision: Union[str, None] = "gt28_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create notification_read_receipts table."""
    op.create_table(
        "notification_read_receipts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("reminder_id", sa.Uuid(), nullable=False),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_notification_read_receipts_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "reminder_id", name="pk_notification_read_receipts"
        ),
    )
    op.create_index(
        "ix_notification_read_receipts_user_id",
        "notification_read_receipts",
        ["user_id"],
    )


def downgrade() -> None:
    """Drop notification_read_receipts table."""
    op.drop_index(
        "ix_notification_read_receipts_user_id",
        table_name="notification_read_receipts",
    )
    op.drop_table("notification_read_receipts")
