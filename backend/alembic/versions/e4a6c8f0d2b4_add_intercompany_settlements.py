import logging
"""add intercompany_settlements (EPIC-16)

Revision ID: e4a6c8f0d2b4
Revises: d2f4a6c8e0b2
Create Date: 2026-08-06 00:00:00.000000

New table only.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e4a6c8f0d2b4'
down_revision: Union[str, Sequence[str], None] = 'd2f4a6c8e0b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'intercompany_settlements',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('from_entity', sa.String(length=50), nullable=False),
        sa.Column('to_entity', sa.String(length=50), nullable=False),
        sa.Column('amount_usd_cents', sa.Integer(), nullable=False),
        sa.Column('settlement_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.UserID']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_intercompany_settlements_tenant_id'), 'intercompany_settlements', ['tenant_id'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('intercompany_settlements')
