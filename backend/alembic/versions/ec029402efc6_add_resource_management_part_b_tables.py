import logging
"""add bench_pool, employee_utilization_metrics, allocation_conflict_log (Phase 4 Part B)

Revision ID: ec029402efc6
Revises: 2179e135a0ab
Create Date: 2026-07-22 00:00:00.000000

04-RESOURCE-MANAGEMENT.md Part B -- the foundational bench/utilization
schema HRMS-1105 (Part A) needs to query. See app.models.resource_management
for the per-table rationale.

VERIFICATION NOTE: op.create_table() x3 plus their indexes verified
end-to-end against a throwaway SQLite database and apply cleanly. Run
against a staging SQL Server copy first, not production directly, same
as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ec029402efc6'
down_revision: Union[str, Sequence[str], None] = '2179e135a0ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'bench_pool',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('available_from', sa.Date(), nullable=False),
        sa.Column('skill_tags', sa.Text(), nullable=True),
        sa.Column('bench_cost_usd_cents', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.UniqueConstraint('employee_id', name='uq_bench_pool_employee'),
    )
    op.create_index(op.f('ix_bench_pool_tenant_id'), 'bench_pool', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_bench_pool_employee_id'), 'bench_pool', ['employee_id'], unique=False)

    op.create_table(
        'employee_utilization_metrics',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('utilization_pct', sa.Numeric(5, 2), nullable=False),
        sa.Column('billable_hours', sa.Numeric(6, 2), nullable=False),
        sa.Column('bench_hours', sa.Numeric(6, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
    )
    op.create_index(op.f('ix_employee_utilization_metrics_tenant_id'), 'employee_utilization_metrics', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_employee_utilization_metrics_employee_id'), 'employee_utilization_metrics', ['employee_id'], unique=False)

    op.create_table(
        'allocation_conflict_log',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('conflicting_allocation_ids_json', sa.Text(), nullable=False),
        sa.Column('attempted_utilization_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('existing_utilization_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('resolution', sa.String(length=50), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
    )
    op.create_index(op.f('ix_allocation_conflict_log_tenant_id'), 'allocation_conflict_log', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_allocation_conflict_log_employee_id'), 'allocation_conflict_log', ['employee_id'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('allocation_conflict_log')
    op.drop_table('employee_utilization_metrics')
    op.drop_table('bench_pool')
