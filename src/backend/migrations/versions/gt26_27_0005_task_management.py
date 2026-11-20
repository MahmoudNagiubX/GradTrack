"""Add team tasks, checklist items, and immutable task activities."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "gt26_27_0005"
down_revision: Union[str, None] = "gt22_25_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create tasks, task_checklist_items, and task_activities with audit trigger."""
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("team_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="todo",
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.String(length=16),
            server_default="medium",
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("assignee_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("completed_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("milestone_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("parent_task_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(btrim(title)) > 0", name="ck_tasks_title_nonempty"),
        sa.CheckConstraint("title = btrim(title)", name="ck_tasks_title_trimmed"),
        sa.CheckConstraint("length(title) <= 200", name="ck_tasks_title_length"),
        sa.CheckConstraint(
            "status IN ('todo', 'in_progress', 'done')", name="ck_tasks_status"
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'medium', 'high')", name="ck_tasks_priority"
        ),
        sa.CheckConstraint(
            "estimated_minutes IS NULL OR "
            "(estimated_minutes > 0 AND estimated_minutes <= 525600)",
            name="ck_tasks_estimated_minutes_range",
        ),
        sa.CheckConstraint(
            "parent_task_id IS NULL OR parent_task_id != id",
            name="ck_tasks_no_self_parent",
        ),
        sa.CheckConstraint(
            "(status = 'done' AND completed_at IS NOT NULL "
            "AND completed_by IS NOT NULL) OR "
            "(status != 'done' AND completed_at IS NULL AND completed_by IS NULL)",
            name="ck_tasks_completion_consistency",
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name="fk_tasks_team"),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_tasks_created_by"
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"], ["users.id"], name="fk_tasks_assignee"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name="fk_tasks_updated_by"
        ),
        sa.ForeignKeyConstraint(
            ["completed_by"], ["users.id"], name="fk_tasks_completed_by"
        ),
        sa.ForeignKeyConstraint(
            ["milestone_id"], ["milestones.id"], name="fk_tasks_milestone"
        ),
        sa.ForeignKeyConstraint(
            ["parent_task_id"], ["tasks.id"], name="fk_tasks_parent"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tasks"),
    )
    op.create_index("ix_tasks_team_status", "tasks", ["team_id", "status"])
    op.create_index("ix_tasks_team_assignee", "tasks", ["team_id", "assignee_id"])
    op.create_index("ix_tasks_team_due_at", "tasks", ["team_id", "due_at"])
    op.create_index("ix_tasks_team_milestone", "tasks", ["team_id", "milestone_id"])
    op.create_index("ix_tasks_team_parent", "tasks", ["team_id", "parent_task_id"])

    op.create_table(
        "task_checklist_items",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("item_text", sa.String(length=200), nullable=False),
        sa.Column(
            "is_done",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("completed_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(item_text)) > 0",
            name="ck_task_checklist_items_text_nonempty",
        ),
        sa.CheckConstraint(
            "item_text = btrim(item_text)",
            name="ck_task_checklist_items_text_trimmed",
        ),
        sa.CheckConstraint(
            "length(item_text) <= 200",
            name="ck_task_checklist_items_text_length",
        ),
        sa.CheckConstraint(
            "(is_done = true AND completed_at IS NOT NULL "
            "AND completed_by IS NOT NULL) OR "
            "(is_done = false AND completed_at IS NULL AND completed_by IS NULL)",
            name="ck_task_checklist_items_done_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name="fk_task_checklist_items_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_task_checklist_items_created_by",
        ),
        sa.ForeignKeyConstraint(
            ["completed_by"],
            ["users.id"],
            name="fk_task_checklist_items_completed_by",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_task_checklist_items"),
    )
    op.create_index(
        "ix_task_checklist_items_task_id", "task_checklist_items", ["task_id"]
    )

    op.create_table(
        "task_activities",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("old_value", sa.String(length=255), nullable=True),
        sa.Column("new_value", sa.String(length=255), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ("
            "'created', 'assigned', 'reassigned', 'status_changed', "
            "'reopened', 'completed', 'updated', 'checklist_item_added', "
            "'checklist_item_updated'"
            ")",
            name="ck_task_activities_event_type",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name="fk_task_activities_task",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name="fk_task_activities_actor"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_task_activities"),
    )
    op.create_index(
        "ix_task_activities_task_created",
        "task_activities",
        ["task_id", "created_at", "id"],
    )

    op.execute(
        """
        CREATE FUNCTION reject_task_activity_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'task activity entries are immutable'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_task_activities_immutable
        BEFORE UPDATE OR DELETE ON task_activities
        FOR EACH ROW EXECUTE FUNCTION reject_task_activity_mutation()
        """
    )


def downgrade() -> None:
    """Remove tasks, checklist items, and task activities."""
    op.execute("DROP TRIGGER trg_task_activities_immutable ON task_activities")
    op.execute("DROP FUNCTION reject_task_activity_mutation()")
    op.drop_index("ix_task_activities_task_created", table_name="task_activities")
    op.drop_table("task_activities")
    op.drop_index("ix_task_checklist_items_task_id", table_name="task_checklist_items")
    op.drop_table("task_checklist_items")
    op.drop_index("ix_tasks_team_parent", table_name="tasks")
    op.drop_index("ix_tasks_team_milestone", table_name="tasks")
    op.drop_index("ix_tasks_team_due_at", table_name="tasks")
    op.drop_index("ix_tasks_team_assignee", table_name="tasks")
    op.drop_index("ix_tasks_team_status", table_name="tasks")
    op.drop_table("tasks")
