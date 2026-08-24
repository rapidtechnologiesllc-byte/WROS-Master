"""Expand ai_agent_persona column from String(100) to Text for long personas

Revision ID: 20260815_expand_persona
Revises:
Create Date: 2026-08-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260815_expand_persona'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alter the column type from String(100) to Text
    # This allows storing 800-1000+ word personas
    op.alter_column(
        'candidate_ai_assignments',
        'ai_agent_persona',
        existing_type=sa.String(100),
        type_=sa.Text(),
        existing_nullable=True,
        nullable=True
    )


def downgrade() -> None:
    # Revert to String(100) if needed (will truncate personas >100 chars)
    op.alter_column(
        'candidate_ai_assignments',
        'ai_agent_persona',
        existing_type=sa.Text(),
        type_=sa.String(100),
        existing_nullable=True,
        nullable=True
    )
