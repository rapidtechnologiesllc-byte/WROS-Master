import logging
"""add candidate_desire_profiles.talking_points (S-350 HR Intelligence Briefing)

Revision ID: 5e9f3a7c1d64
Revises: 7c1a9e4d6b28
Create Date: 2026-08-05 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e9f3a7c1d64'
down_revision: Union[str, Sequence[str], None] = '7c1a9e4d6b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('candidate_desire_profiles', sa.Column('talking_points', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('candidate_desire_profiles', 'talking_points')
