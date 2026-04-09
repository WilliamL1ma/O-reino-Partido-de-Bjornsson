"""add race state fields to characters

Revision ID: 20260408_0003
Revises: 20260408_0002
Create Date: 2026-04-08 03:35:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260408_0003"
down_revision = "20260408_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("characters")}

    if "race_slug" not in existing_columns:
        op.add_column("characters", sa.Column("race_slug", sa.String(length=80), nullable=True))

    if "race_status" not in existing_columns:
        op.add_column("characters", sa.Column("race_status", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("characters", "race_status")
    op.drop_column("characters", "race_slug")
