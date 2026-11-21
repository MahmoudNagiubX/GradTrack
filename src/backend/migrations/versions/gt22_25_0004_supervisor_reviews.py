"""Add immutable, version-scoped supervisor reviews."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "gt22_25_0004"
down_revision: Union[str, None] = "gt20_21_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Store exactly one append-only review action per submission version."""
    op.create_table(
        "supervisor_reviews",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "decision IN ('approved', 'returned')",
            name="ck_supervisor_reviews_decision",
        ),
        sa.CheckConstraint(
            "(decision = 'returned' AND feedback IS NOT NULL "
            "AND feedback = btrim(feedback) AND length(feedback) BETWEEN 1 AND 2000) "
            "OR (decision = 'approved' AND (feedback IS NULL OR "
            "(feedback = btrim(feedback) AND length(feedback) <= 2000)))",
            name="ck_supervisor_reviews_feedback",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["submission_versions.id"],
            name="fk_supervisor_reviews_version",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"], ["users.id"], name="fk_supervisor_reviews_reviewer"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_supervisor_reviews"),
        sa.UniqueConstraint("version_id", name="uq_supervisor_reviews_version"),
    )
    op.execute(
        """
        CREATE FUNCTION reject_supervisor_review_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'supervisor reviews are immutable'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_supervisor_reviews_immutable
        BEFORE UPDATE OR DELETE ON supervisor_reviews
        FOR EACH ROW EXECUTE FUNCTION reject_supervisor_review_mutation()
        """
    )


def downgrade() -> None:
    """Remove only the Phase 5B supervisor review objects."""
    op.execute("DROP TRIGGER trg_supervisor_reviews_immutable ON supervisor_reviews")
    op.execute("DROP FUNCTION reject_supervisor_review_mutation()")
    op.drop_table("supervisor_reviews")
