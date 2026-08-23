"""add timesheet_disputes (HRMS-0904)

Revision ID: a7b8c9d0e1f3
Revises: f6a7b8c9d0e2
Create Date: 2026-07-21 00:00:00.000007

HRMS-0904 -- Timesheet Dispute Resolution. Extends the existing
Timesheet/TimesheetEntry tables (HRMS-0901/0902); see app.models.
timesheet_dispute's module docstring for what's deliberately not built
(revenue_records/revenue_adjustments propagation -- those tables don't
exist yet).

VERIFICATION NOTE: op.create_table() (all inline FK/CHECK constraints)
verified end-to-end against a throwaway SQLite database and applies
cleanly -- a brand-new table, no ALTER-on-existing-table operations, so
none of the earlier SQLite batch-mode caveats apply here. Run against a
staging SQL Server copy first, not production directly, same as every
migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f3'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'timesheet_disputes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('timesheet_id', sa.String(length=36), nullable=False),
        sa.Column('raised_by', sa.String(length=10), nullable=False),
        sa.Column('raised_by_user_id', sa.String(length=50), nullable=True),
        sa.Column('disputed_date', sa.DateTime(), nullable=True),
        sa.Column('disputed_hours', sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column('original_hours', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('resolved_by', sa.String(length=50), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('adjusted_hours', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['timesheet_id'], ['timesheets.id']),
        sa.ForeignKeyConstraint(['raised_by_user_id'], ['users.UserID']),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.UserID']),
        sa.CheckConstraint("raised_by IN ('RM','EMPLOYEE','CLIENT')", name='ck_timesheet_disputes_raised_by'),
        sa.CheckConstraint(
            "status IN ('OPEN','UNDER_REVIEW','RESOLVED_ADJUSTED','RESOLVED_CONFIRMED','CANCELLED')",
            name='ck_timesheet_disputes_status',
        ),
    )
    op.create_index(op.f('ix_timesheet_disputes_tenant_id'), 'timesheet_disputes', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_timesheet_disputes_timesheet_id'), 'timesheet_disputes', ['timesheet_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('timesheet_disputes')
