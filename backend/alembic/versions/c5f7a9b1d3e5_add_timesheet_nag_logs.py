import logging
"""add timesheet_nag_logs (EPIC-16 Timesheet Nag Cascade)

Revision ID: c5f7a9b1d3e5
Revises: b3e5f7a9c1d3
Create Date: 2026-08-06 00:00:00.000000

New table only.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5f7a9b1d3e5'
down_revision: Union[str, Sequence[str], None] = 'b3e5f7a9c1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'timesheet_nag_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('week_starting_date', sa.Date(), nullable=False),
        sa.Column('escalation_level', sa.Integer(), nullable=False),
        sa.Column('last_nagged_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('employee_id', 'week_starting_date', name='uq_timesheet_nag_employee_week'),
    )
    op.create_index(op.f('ix_timesheet_nag_logs_tenant_id'), 'timesheet_nag_logs', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_timesheet_nag_logs_employee_id'), 'timesheet_nag_logs', ['employee_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('timesheet_nag_logs')
