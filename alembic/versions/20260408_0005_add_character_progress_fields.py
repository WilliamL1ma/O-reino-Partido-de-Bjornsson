"""adiciona campos de progresso do personagem

ID da revisão: 20260408_0005
Revisa: 20260408_0004
Data de criação: 2026-04-08 00:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260408_0005"
down_revision = "20260408_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("characters", sa.Column("experience", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("characters", sa.Column("gold", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("characters", sa.Column("story_act", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("characters", sa.Column("story_scene", sa.String(length=80), nullable=True))
    op.add_column("characters", sa.Column("story_flags", sa.Text(), nullable=True))
    op.add_column("characters", sa.Column("story_inventory", sa.Text(), nullable=True))

    op.alter_column("characters", "experience", server_default=None)
    op.alter_column("characters", "gold", server_default=None)
    op.alter_column("characters", "story_act", server_default=None)


def downgrade() -> None:
    op.drop_column("characters", "story_inventory")
    op.drop_column("characters", "story_flags")
    op.drop_column("characters", "story_scene")
    op.drop_column("characters", "story_act")
    op.drop_column("characters", "gold")
    op.drop_column("characters", "experience")
