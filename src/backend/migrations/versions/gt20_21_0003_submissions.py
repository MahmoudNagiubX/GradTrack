"""Add immutable milestone submission versions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "gt20_21_0003"
down_revision: Union[str, None] = "gt18_19_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create submission threads and their append-only version records."""
    op.create_table(
        "milestone_submissions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("milestone_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "review_status",
            sa.String(length=32),
            server_default="pending_review",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "review_status IN ('pending_review', 'returned', 'approved')",
            name="ck_milestone_submissions_review_status",
        ),
        sa.ForeignKeyConstraint(
            ["milestone_id"],
            ["milestones.id"],
            name="fk_milestone_submissions_milestone",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_milestone_submissions"),
        sa.UniqueConstraint("milestone_id", name="uq_milestone_submissions_milestone"),
    )
    op.create_table(
        "submission_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("submission_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("submitted_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at_submission", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_late", sa.Boolean(), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("media_type", sa.String(length=127), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.CheckConstraint(
            "version_number >= 1", name="ck_submission_versions_number_positive"
        ),
        sa.CheckConstraint(
            "source_type IN ('file', 'link')",
            name="ck_submission_versions_source_type",
        ),
        sa.CheckConstraint(
            "(source_type = 'file' AND storage_key IS NOT NULL AND url IS NULL "
            "AND original_filename IS NOT NULL AND file_size_bytes > 0 "
            "AND file_size_bytes <= 20971520 AND media_type IS NOT NULL) OR "
            "(source_type = 'link' AND url IS NOT NULL AND storage_key IS NULL "
            "AND original_filename IS NULL AND file_size_bytes IS NULL "
            "AND media_type IS NULL)",
            name="ck_submission_versions_exactly_one_source",
        ),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["milestone_submissions.id"],
            name="fk_submission_versions_submission",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"], ["users.id"], name="fk_submission_versions_submitted_by"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_submission_versions"),
        sa.UniqueConstraint(
            "submission_id", "version_number", name="uq_submission_versions_number"
        ),
    )
    op.create_index(
        "ix_submission_versions_submission_submitted",
        "submission_versions",
        ["submission_id", "submitted_at", "id"],
        unique=False,
    )
    op.execute(
        """
        CREATE FUNCTION reject_submission_version_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'submission versions are immutable'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_submission_versions_immutable
        BEFORE UPDATE OR DELETE ON submission_versions
        FOR EACH ROW EXECUTE FUNCTION reject_submission_version_mutation()
        """
    )


def downgrade() -> None:
    """Remove only the Phase 5A submission objects."""
    op.execute("DROP TRIGGER trg_submission_versions_immutable ON submission_versions")
    op.execute("DROP FUNCTION reject_submission_version_mutation()")
    op.drop_index(
        "ix_submission_versions_submission_submitted",
        table_name="submission_versions",
    )
    op.drop_table("submission_versions")
    op.drop_table("milestone_submissions")
