"""add projects + project_milestones, extend employee_allocations + demands (HRMS-0801/0803/0804)

Revision ID: c9d0e1f2a3b5
Revises: b8c9d0e1f2a4
Create Date: 2026-07-21 00:00:00.000008

HRMS-0801 (Project Lifecycle), HRMS-0804 (Milestones), HRMS-0803
(Assign Resource to Project -- extends the existing EmployeeAllocation
with project_id/role rather than a new table; utilization_pct/
client_reporting_manager_contact_id already existed and double as
HRMS-0803's allocation_pct/reporting-manager fields). Demand also gets
project_id for HRMS-0805's unfilled-role gap detection.

VERIFICATION NOTE: both op.create_table() calls (projects,
project_milestones, all inline FK/CHECK constraints) and both
op.add_column() batches (employee_allocations.project_id/role;
demands.project_id) were verified end-to-end against a throwaway
SQLite database and apply cleanly. The op.create_foreign_key() calls
adding employee_allocations.project_id -> projects.id and
demands.project_id -> projects.id could NOT be verified the same way
-- identical SQLite ALTER-on-existing-table limitation already
documented in every prior migration in this package that adds a
constraint to a pre-existing table. The real production target, SQL
Server, supports ALTER TABLE ADD CONSTRAINT natively. Run this on a
staging/dev SQL Server copy first, not production directly.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b5'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- projects (HRMS-0801) ---
    op.create_table(
        'projects',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('client_id', sa.String(length=36), nullable=False),
        sa.Column('opportunity_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=300), nullable=False),
        sa.Column('status', sa.String(length=15), nullable=False),
        sa.Column('billing_type', sa.String(length=25), nullable=False),
        sa.Column('currency', sa.String(length=5), nullable=False),
        sa.Column('continent', sa.String(length=50), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id']),
        sa.CheckConstraint("status IN ('PLANNING','ACTIVE','ON_HOLD','COMPLETED','CLOSED')", name='ck_projects_status'),
        sa.CheckConstraint("billing_type IN ('TIME_AND_MATERIALS','FIXED_BID')", name='ck_projects_billing_type'),
        sa.CheckConstraint("currency IN ('USD','INR','GBP','EUR','CAD','AUD')", name='ck_projects_currency'),
    )
    op.create_index(op.f('ix_projects_tenant_id'), 'projects', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_projects_client_id'), 'projects', ['client_id'], unique=False)
    op.create_index(op.f('ix_projects_opportunity_id'), 'projects', ['opportunity_id'], unique=False)

    # --- project_milestones (HRMS-0804) ---
    op.create_table(
        'project_milestones',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('owner_employee_id', sa.String(length=36), nullable=True),
        sa.Column('is_complete', sa.String(length=10), nullable=False),
        sa.Column('completion_date', sa.Date(), nullable=True),
        sa.Column('delay_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['owner_employee_id'], ['employees.id']),
        sa.CheckConstraint("is_complete IN ('PENDING','COMPLETE')", name='ck_project_milestones_is_complete'),
    )
    op.create_index(op.f('ix_project_milestones_tenant_id'), 'project_milestones', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_project_milestones_project_id'), 'project_milestones', ['project_id'], unique=False)

    # --- employee_allocations (HRMS-0803) ---
    op.add_column('employee_allocations', sa.Column('project_id', sa.String(length=36), nullable=True))
    op.add_column('employee_allocations', sa.Column('role', sa.String(length=200), nullable=True))
    op.create_index(op.f('ix_employee_allocations_project_id'), 'employee_allocations', ['project_id'], unique=False)
    op.create_foreign_key(None, 'employee_allocations', 'projects', ['project_id'], ['id'])

    # --- demands (HRMS-0805) ---
    op.add_column('demands', sa.Column('project_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_demands_project_id'), 'demands', ['project_id'], unique=False)
    op.create_foreign_key(None, 'demands', 'projects', ['project_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('demands', 'project_id')
    op.drop_column('employee_allocations', 'role')
    op.drop_column('employee_allocations', 'project_id')
    op.drop_table('project_milestones')
    op.drop_table('projects')
