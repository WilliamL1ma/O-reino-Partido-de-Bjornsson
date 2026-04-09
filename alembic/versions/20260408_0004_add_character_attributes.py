"""adiciona atributos ao personagem

ID da revisão: 20260408_0004
Revisa: 20260408_0003
Data de criação: 2026-04-08 00:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260408_0004"
down_revision = "20260408_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("characters", sa.Column("strength", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("characters", sa.Column("dexterity", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("characters", sa.Column("constitution", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("characters", sa.Column("intelligence", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("characters", sa.Column("wisdom", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("characters", sa.Column("charisma", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("characters", sa.Column("perception", sa.Integer(), nullable=False, server_default="10"))


def downgrade() -> None:
    op.drop_column("characters", "perception")
    op.drop_column("characters", "charisma")
    op.drop_column("characters", "wisdom")
    op.drop_column("characters", "intelligence")
    op.drop_column("characters", "constitution")
    op.drop_column("characters", "dexterity")
    op.drop_column("characters", "strength")
