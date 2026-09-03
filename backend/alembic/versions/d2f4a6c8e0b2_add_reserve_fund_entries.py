import logging
"""add reserve_fund_entries (EPIC-16)

Revision ID: d2f4a6c8e0b2
Revises: b7d9f1a3c5e7
Create Date: 2026-08-06 00:00:00.000000

New table only.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd2f4a6c8e0b2'
down_revision: Union[str, Sequence[str], None] = 'b7d9f1a3c5e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'reserve_fund_entries',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('business_unit_id', sa.Integer(), nullable=True),
        sa.Column('entry_type', sa.String(length=20), nullable=False),
        sa.Column('amount_usd_cents', sa.Integer(), nullable=False),
        sa.Column('period_year', sa.Integer(), nullable=False),
        sa.Column('period_month', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.CheckConstraint("entry_type IN ('CONTRIBUTION','WITHDRAWAL')", name='ck_reserve_fund_entries_entry_type'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['business_unit_id'], ['business_units.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.UserID']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reserve_fund_entries_tenant_id'), 'reserve_fund_entries', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_reserve_fund_entries_business_unit_id'), 'reserve_fund_entries', ['business_unit_id'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('reserve_fund_entries')
