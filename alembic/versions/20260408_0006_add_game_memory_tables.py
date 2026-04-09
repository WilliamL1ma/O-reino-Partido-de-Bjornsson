"""adiciona tabelas de memória do jogo

ID da revisão: 20260408_0006
Revisa: 20260408_0005
Data de criação: 2026-04-08 00:06:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260408_0006"
down_revision = "20260408_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("scene", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_game_messages_character_id"), "game_messages", ["character_id"], unique=False)

    op.create_table(
        "memory_summaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_summaries_character_id"), "memory_summaries", ["character_id"], unique=False)
    op.alter_column("memory_summaries", "version", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_memory_summaries_character_id"), table_name="memory_summaries")
    op.drop_table("memory_summaries")
    op.drop_index(op.f("ix_game_messages_character_id"), table_name="game_messages")
    op.drop_table("game_messages")
