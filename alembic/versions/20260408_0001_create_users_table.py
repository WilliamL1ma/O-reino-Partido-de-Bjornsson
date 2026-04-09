"""create users table with 2fa fields

Revision ID: 20260408_0001
Revises:
Create Date: 2026-04-08 02:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260408_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "users" not in inspector.get_table_names():
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(length=120), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("birth_date", sa.Date(), nullable=False),
            sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("two_factor_secret", sa.String(length=64), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        return

    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("users")}

    if "two_factor_enabled" not in existing_columns:
        op.add_column(
            "users",
            sa.Column(
                "two_factor_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    if "two_factor_secret" not in existing_columns:
        op.add_column(
            "users",
            sa.Column("two_factor_secret", sa.String(length=64), nullable=True),
        )

    if "ix_users_email" not in existing_indexes:
        op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
