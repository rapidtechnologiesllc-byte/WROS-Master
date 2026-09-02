import logging
"""add demands.delivery_engine, employee_allocations.CORE_PULLED status, core_pull_events, specialty_pool_replacement_plans (S-353/S-373)

Revision ID: 35fbb8ebd5c8
Revises: ec029402efc6
Create Date: 2026-07-22 00:00:00.000000

S-353/HRMS-0514 Core-Pull Conflict Rule Engine + S-373/HRMS-0529 Specialty
Pool Minimum 40 Guard. See app.models.core_pull and app.services.core_pull_service
for the story rationale (and the HRMS-0312 mislabeling this deliberately
builds against the corrected ID instead of).

VERIFICATION NOTE: op.add_column() + op.create_check_constraint() on
`demands`, batch_alter_table on `employee_allocations` to widen its status
CHECK constraint, and op.create_table() x2 all verified end-to-end against
a throwaway SQLite database. Run against a staging SQL Server copy first,
not production directly, same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35fbb8ebd5c8'
down_revision: Union[str, Sequence[str], None] = 'ec029402efc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'demands',
        sa.Column('delivery_engine', sa.String(length=20), nullable=False, server_default='SPECIALITY'),
    )
    with op.batch_alter_table('demands') as batch_op:
        batch_op.create_check_constraint(
            'ck_demands_delivery_engine', "delivery_engine IN ('SPECIALITY','CORE')",
        )

    with op.batch_alter_table('employee_allocations') as batch_op:
        batch_op.drop_constraint('ck_employee_allocations_status', type_='check')
        batch_op.create_check_constraint(
            'ck_employee_allocations_status', "status IN ('ACTIVE','ENDED','CORE_PULLED')",
        )

    op.create_table(
        'core_pull_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('core_demand_id', sa.String(length=36), nullable=False),
        sa.Column('speciality_allocation_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('override_justification', sa.Text(), nullable=True),
        sa.Column('overridden_by', sa.String(length=50), nullable=True),
        sa.Column('overridden_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['core_demand_id'], ['demands.id']),
        sa.ForeignKeyConstraint(['speciality_allocation_id'], ['employee_allocations.id']),
        sa.ForeignKeyConstraint(['overridden_by'], ['users.UserID']),
        sa.CheckConstraint("status IN ('PENDING','EXECUTED','OVERRIDDEN')", name='ck_core_pull_events_status'),
    )
    op.create_index(op.f('ix_core_pull_events_tenant_id'), 'core_pull_events', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_core_pull_events_employee_id'), 'core_pull_events', ['employee_id'], unique=False)
    op.create_index(op.f('ix_core_pull_events_core_demand_id'), 'core_pull_events', ['core_demand_id'], unique=False)
    op.create_index(op.f('ix_core_pull_events_speciality_allocation_id'), 'core_pull_events', ['speciality_allocation_id'], unique=False)

    op.create_table(
        'specialty_pool_replacement_plans',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id_moving', sa.String(length=36), nullable=False),
        sa.Column('replacement_strategy', sa.Text(), nullable=False),
        sa.Column('expected_replacement_date', sa.Date(), nullable=False),
        sa.Column('logged_by', sa.String(length=50), nullable=True),
        sa.Column('logged_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id_moving'], ['employees.id']),
        sa.ForeignKeyConstraint(['logged_by'], ['users.UserID']),
    )
    op.create_index(op.f('ix_specialty_pool_replacement_plans_tenant_id'), 'specialty_pool_replacement_plans', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_specialty_pool_replacement_plans_employee_id_moving'), 'specialty_pool_replacement_plans', ['employee_id_moving'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('specialty_pool_replacement_plans')
    op.drop_table('core_pull_events')
    with op.batch_alter_table('employee_allocations') as batch_op:
        batch_op.drop_constraint('ck_employee_allocations_status', type_='check')
        batch_op.create_check_constraint(
            'ck_employee_allocations_status', "status IN ('ACTIVE','ENDED')",
        )
    with op.batch_alter_table('demands') as batch_op:
        batch_op.drop_constraint('ck_demands_delivery_engine', type_='check')
        batch_op.drop_column('delivery_engine')
