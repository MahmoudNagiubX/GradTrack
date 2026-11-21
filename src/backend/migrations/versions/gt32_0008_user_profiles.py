"""Add user profile and avatar fields to users table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "gt32_0008"
down_revision: Union[str, None] = "gt30_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add profile and avatar columns and constraints to users."""
    op.add_column(
        "users",
        sa.Column("student_number", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("faculty", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("department", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("academic_level", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("bio", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("avatar_storage_key", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_users_student_number_nonempty",
        "users",
        "student_number IS NULL OR length(btrim(student_number)) > 0",
    )
    op.create_check_constraint(
        "ck_users_avatar_storage_key_len",
        "users",
        "avatar_storage_key IS NULL OR length(avatar_storage_key) = 32",
    )


def downgrade() -> None:
    """Drop profile and avatar columns and constraints from users."""
    op.drop_constraint("ck_users_avatar_storage_key_len", "users", type_="check")
    op.drop_constraint("ck_users_student_number_nonempty", "users", type_="check")
    op.drop_column("users", "avatar_storage_key")
    op.drop_column("users", "bio")
    op.drop_column("users", "academic_level")
    op.drop_column("users", "department")
    op.drop_column("users", "faculty")
    op.drop_column("users", "student_number")
