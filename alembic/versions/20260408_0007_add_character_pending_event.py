"""adiciona evento pendente ao personagem

ID da revisão: 20260408_0007
Revisa: 20260408_0006
Data de criação: 2026-04-08 00:07:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260408_0007"
down_revision = "20260408_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("characters", sa.Column("pending_event", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("characters", "pending_event")
