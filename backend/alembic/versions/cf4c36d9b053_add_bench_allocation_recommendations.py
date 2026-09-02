import logging
"""add bench_allocation_recommendations (HRMS-1105 Resource Management Agent, canonical S-320)

Revision ID: cf4c36d9b053
Revises: 35fbb8ebd5c8
Create Date: 2026-07-22 00:00:00.000000

See app.models.resource_agent and app.services.resource_management_agent_service
for the story rationale.

VERIFICATION NOTE: op.create_table() verified end-to-end against a
throwaway SQLite database. Run against a staging SQL Server copy first,
not production directly, same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf4c36d9b053'
down_revision: Union[str, Sequence[str], None] = '35fbb8ebd5c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'bench_allocation_recommendations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('demand_id', sa.String(length=36), nullable=False),
        sa.Column('confidence_pct', sa.Numeric(5, 2), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('reviewed_by', sa.String(length=50), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['demand_id'], ['demands.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.UserID']),
        sa.CheckConstraint(
            "status IN ('PENDING_RM_REVIEW','APPROVED','REJECTED')",
            name='ck_bench_allocation_recommendations_status',
        ),
    )
    op.create_index(op.f('ix_bench_allocation_recommendations_tenant_id'), 'bench_allocation_recommendations', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_bench_allocation_recommendations_employee_id'), 'bench_allocation_recommendations', ['employee_id'], unique=False)
    op.create_index(op.f('ix_bench_allocation_recommendations_demand_id'), 'bench_allocation_recommendations', ['demand_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('bench_allocation_recommendations')
