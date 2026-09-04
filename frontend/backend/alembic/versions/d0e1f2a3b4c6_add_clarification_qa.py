"""add clarification_qa (HRMS-P814)

Revision ID: d0e1f2a3b4c6
Revises: c9d0e1f2a3b5
Create Date: 2026-07-21 00:00:00.000009

HRMS-P814 -- Sub-Vendor Request for Clarification. The tracking/
scorecard pieces built alongside this (HRMS-P803/P810/P805/P812) needed
no schema changes at all -- pure read-only queries over existing tables.

VERIFICATION NOTE: op.create_table() (all inline FK constraints)
verified end-to-end against a throwaway SQLite database and applies
cleanly -- a brand-new table, no ALTER-on-existing-table operations.
Run against a staging SQL Server copy first, not production directly,
same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0e1f2a3b4c6'
down_revision: Union[str, Sequence[str], None] = 'c9d0e1f2a3b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'clarification_qa',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('request_id', sa.String(length=36), nullable=False),
        sa.Column('sub_vendor_id', sa.String(length=36), nullable=False),
        sa.Column('question', sa.String(length=2000), nullable=False),
        sa.Column('asked_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('answer', sa.String(length=2000), nullable=True),
        sa.Column('answered_by', sa.String(length=50), nullable=True),
        sa.Column('answered_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['request_id'], ['sub_vendor_requests.id']),
        sa.ForeignKeyConstraint(['sub_vendor_id'], ['sub_vendor_accounts.id']),
        sa.ForeignKeyConstraint(['answered_by'], ['users.UserID']),
    )
    op.create_index(op.f('ix_clarification_qa_tenant_id'), 'clarification_qa', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_clarification_qa_request_id'), 'clarification_qa', ['request_id'], unique=False)
    op.create_index(op.f('ix_clarification_qa_sub_vendor_id'), 'clarification_qa', ['sub_vendor_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('clarification_qa')
