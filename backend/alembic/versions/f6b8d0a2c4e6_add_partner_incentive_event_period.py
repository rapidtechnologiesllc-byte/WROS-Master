import logging
"""add partner_incentive_events.period_year/period_month (EPIC-16 Partner Incentive Calculator)

Revision ID: f6b8d0a2c4e6
Revises: e4a6c8f0d2b4
Create Date: 2026-08-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6b8d0a2c4e6'
down_revision: Union[str, Sequence[str], None] = 'e4a6c8f0d2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('partner_incentive_events', sa.Column('period_year', sa.Integer(), nullable=True))
    op.add_column('partner_incentive_events', sa.Column('period_month', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('partner_incentive_events', 'period_month')
    op.drop_column('partner_incentive_events', 'period_year')
