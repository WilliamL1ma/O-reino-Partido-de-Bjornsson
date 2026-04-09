"""create characters table

Revision ID: 20260408_0002
Revises: 20260408_0001
Create Date: 2026-04-08 03:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260408_0002"
down_revision = "20260408_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "characters" in inspector.get_table_names():
      return

    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("age", sa.Integer(), nullable=False),
        sa.Column("personality", sa.Text(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=True),
        sa.Column("fear", sa.Text(), nullable=True),
        sa.Column("race_name", sa.String(length=80), nullable=True),
        sa.Column("class_name", sa.String(length=80), nullable=True),
        sa.Column("onboarding_step", sa.String(length=40), nullable=False, server_default="race"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_characters_user_id", "characters", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_characters_user_id", table_name="characters")
    op.drop_table("characters")
