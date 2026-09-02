import logging
"""add cost_rate_configs (EPIC-16 Fully Loaded Cost / Blended Delivery Rate)

Revision ID: b7d9f1a3c5e7
Revises: a5c8e2f4b6d9
Create Date: 2026-08-06 00:00:00.000000

New table only -- no ALTER on any existing table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d9f1a3c5e7'
down_revision: Union[str, Sequence[str], None] = 'a5c8e2f4b6d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'cost_rate_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('business_unit_id', sa.Integer(), nullable=True),
        sa.Column('statutory_pct', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('overhead_pct', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('effective_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['business_unit_id'], ['business_units.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.UserID']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_cost_rate_configs_tenant_id'), 'cost_rate_configs', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_cost_rate_configs_business_unit_id'), 'cost_rate_configs', ['business_unit_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('cost_rate_configs')
