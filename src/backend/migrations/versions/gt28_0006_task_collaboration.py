"""Add task comments and attachments for team collaboration."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "gt28_0006"
down_revision: Union[str, None] = "gt26_27_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create task_comments and task_attachments and extend task activity events."""
    op.drop_constraint(
        "ck_task_activities_event_type",
        "task_activities",
        type_="check",
    )
    op.create_check_constraint(
        "ck_task_activities_event_type",
        "task_activities",
        "event_type IN ("
        "'created', 'assigned', 'reassigned', 'status_changed', "
        "'reopened', 'completed', 'updated', 'checklist_item_added', "
        "'checklist_item_updated', 'comment_added', 'attachment_uploaded'"
        ")",
    )

    op.create_table(
        "task_comments",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("author_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(content)) > 0", name="ck_task_comments_content_nonempty"
        ),
        sa.CheckConstraint(
            "content = btrim(content)", name="ck_task_comments_content_trimmed"
        ),
        sa.CheckConstraint(
            "length(content) <= 2000", name="ck_task_comments_content_length"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name="fk_task_comments_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name="fk_task_comments_author"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_task_comments"),
    )
    op.create_index(
        "ix_task_comments_task_created",
        "task_comments",
        ["task_id", "created_at", "id"],
    )

    op.create_table(
        "task_attachments",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("uploader_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("media_type", sa.String(length=127), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 20971520",
            name="ck_task_attachments_file_size",
        ),
        sa.CheckConstraint(
            "length(btrim(original_filename)) > 0",
            name="ck_task_attachments_filename_nonempty",
        ),
        sa.CheckConstraint(
            "length(storage_key) = 32",
            name="ck_task_attachments_storage_key_length",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name="fk_task_attachments_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploader_id"], ["users.id"], name="fk_task_attachments_uploader"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_task_attachments"),
    )
    op.create_index(
        "ix_task_attachments_task_created",
        "task_attachments",
        ["task_id", "created_at", "id"],
    )


def downgrade() -> None:
    """Remove task_attachments, task_comments and restore activity constraints."""
    op.drop_index("ix_task_attachments_task_created", table_name="task_attachments")
    op.drop_table("task_attachments")
    op.drop_index("ix_task_comments_task_created", table_name="task_comments")
    op.drop_table("task_comments")

    op.drop_constraint(
        "ck_task_activities_event_type",
        "task_activities",
        type_="check",
    )
    op.create_check_constraint(
        "ck_task_activities_event_type",
        "task_activities",
        "event_type IN ("
        "'created', 'assigned', 'reassigned', 'status_changed', "
        "'reopened', 'completed', 'updated', 'checklist_item_added', "
        "'checklist_item_updated'"
        ")",
    )
