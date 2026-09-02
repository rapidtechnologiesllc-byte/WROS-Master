import logging
"""add bank_transactions (EPIC-16 Bank Reconciliation)

Revision ID: b3e5f7a9c1d3
Revises: a1c3e5f7b9d1
Create Date: 2026-08-06 00:00:00.000000

New table only.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3e5f7a9c1d3'
down_revision: Union[str, Sequence[str], None] = 'a1c3e5f7b9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'bank_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('amount_usd_cents', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('matched_invoice_id', sa.String(length=36), nullable=True),
        sa.Column('reconciled', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['matched_invoice_id'], ['invoices.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.UserID']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bank_transactions_tenant_id'), 'bank_transactions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_bank_transactions_matched_invoice_id'), 'bank_transactions', ['matched_invoice_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('bank_transactions')
