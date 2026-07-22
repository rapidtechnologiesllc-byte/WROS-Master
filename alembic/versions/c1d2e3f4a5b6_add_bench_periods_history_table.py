"""add bench_periods history table (S-246/HRMS-0502, extended)

Revision ID: c1d2e3f4a5b6
Revises: ba6522085601
Create Date: 2026-07-22 00:00:00.000000

The real requirement doc for this area (found this round -- see
app.models.resource_management.BenchPeriod's docstring) calls for a
persistent, append-only bench-episode history table distinct from the
existing bench_pool "current state" table. This adds that table without
touching bench_pool or anything that already reads it.

VERIFICATION NOTE: verified against a throwaway SQLite database
(op.create_table only -- no ALTER of an existing table, so this is
straightforward on both SQLite and the real SQL Server target).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'ba6522085601'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bench_periods',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('bench_start_date', sa.Date(), nullable=False),
        sa.Column('bench_end_date', sa.Date(), nullable=True),
        sa.Column(
            'reason_for_bench',
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column('bench_cost_usd_cents', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], name='fk_bench_periods_tenant_id'),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name='fk_bench_periods_employee_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "reason_for_bench IN ('PROJECT_ENDED','PROJECT_DELAYED','NEWLY_JOINED','BETWEEN_PROJECTS','OTHER')",
            name='ck_bench_periods_reason',
        ),
    )
    op.create_index('ix_bench_periods_tenant_id', 'bench_periods', ['tenant_id'])
    op.create_index('ix_bench_periods_employee_id', 'bench_periods', ['employee_id'])


def downgrade() -> None:
    op.drop_index('ix_bench_periods_employee_id', table_name='bench_periods')
    op.drop_index('ix_bench_periods_tenant_id', table_name='bench_periods')
    op.drop_table('bench_periods')
