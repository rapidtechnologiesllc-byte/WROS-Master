import logging
"""add employee_allocations + timesheets + timesheet_entries

Revision ID: a1b2c3d4e5f7
Revises: f8a9b0c1d2e3
Create Date: 2026-07-21 00:00:00.000001

HRMS-0507 (minimal allocate/end-allocation slice, not Phase 4's full
Resource Management build) + HRMS-0901/0902 (Timesheet Submission +
Approval), Phase 2 Domain 4. Same translation conventions as every
prior migration in this package (UUID as String(36),
Enum(native_enum=False, create_constraint=True) rendered as
VARCHAR + CHECK).

VERIFICATION NOTE: all 3 op.create_table() calls, including inline
FKs/UNIQUE/CHECK constraints, were verified end-to-end against a
throwaway SQLite database and apply cleanly (all-new tables, no
ALTER-on-existing-table operations this time, so none of the earlier
SQLite batch-mode caveats apply here). Run against a staging SQL
Server copy first, not production directly, same as every migration
in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, Sequence[str], None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    # --- employee_allocations (HRMS-0507) ---
    op.create_table(
        'employee_allocations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('demand_id', sa.String(length=36), nullable=False),
        sa.Column('client_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('utilization_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('client_reporting_manager_contact_id', sa.String(length=36), nullable=True),
        sa.Column('timesheet_approver_email', sa.String(length=300), nullable=True),
        sa.Column('billing_rate_usd_cents', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['demand_id'], ['demands.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['client_reporting_manager_contact_id'], ['client_contacts.id']),
        sa.CheckConstraint("status IN ('ACTIVE','ENDED')", name='ck_employee_allocations_status'),
    )
    op.create_index(op.f('ix_employee_allocations_tenant_id'), 'employee_allocations', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_employee_allocations_employee_id'), 'employee_allocations', ['employee_id'], unique=False)
    op.create_index(op.f('ix_employee_allocations_demand_id'), 'employee_allocations', ['demand_id'], unique=False)
    op.create_index(op.f('ix_employee_allocations_client_id'), 'employee_allocations', ['client_id'], unique=False)

    # --- timesheets (HRMS-0901/0902) ---
    op.create_table(
        'timesheets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('allocation_id', sa.String(length=36), nullable=False),
        sa.Column('week_starting_date', sa.Date(), nullable=False),
        sa.Column('total_hours', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('billable_hours', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('non_billable_hours', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by', sa.String(length=50), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('client_approver_email', sa.String(length=300), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['allocation_id'], ['employee_allocations.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.UserID']),
        sa.UniqueConstraint(
            'tenant_id', 'employee_id', 'allocation_id', 'week_starting_date',
            name='uq_timesheet_per_employee_allocation_week',
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','APPROVED','REJECTED','DISPUTED')",
            name='ck_timesheets_status',
        ),
    )
    op.create_index(op.f('ix_timesheets_tenant_id'), 'timesheets', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_timesheets_employee_id'), 'timesheets', ['employee_id'], unique=False)
    op.create_index(op.f('ix_timesheets_allocation_id'), 'timesheets', ['allocation_id'], unique=False)

    # --- timesheet_entries ---
    op.create_table(
        'timesheet_entries',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('timesheet_id', sa.String(length=36), nullable=False),
        sa.Column('entry_date', sa.Date(), nullable=False),
        sa.Column('hours', sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column('entry_type', sa.String(length=15), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['timesheet_id'], ['timesheets.id']),
        sa.UniqueConstraint('timesheet_id', 'entry_date', name='uq_timesheet_entry_per_day'),
        sa.CheckConstraint('hours >= 0 AND hours <= 24', name='ck_timesheet_entry_hours_range'),
        sa.CheckConstraint(
            "entry_type IN ('BILLABLE','NON_BILLABLE','LEAVE','HOLIDAY')",
            name='ck_timesheet_entries_type',
        ),
    )
    op.create_index(op.f('ix_timesheet_entries_timesheet_id'), 'timesheet_entries', ['timesheet_id'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('timesheet_entries')
    op.drop_table('timesheets')
    op.drop_table('employee_allocations')
