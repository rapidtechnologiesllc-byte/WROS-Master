import logging
"""add htd_intake_status/htd_monthly_metrics/htd_pause_log (S-359/HRMS-P511)

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-07-23 00:00:00.000000

S-359/HRMS-P511 -- HTD Intake Pause Engine: Conversion Rate Breach.
Three new tables -- see app.models.htd_intake_pause's module docstring
for why this uses dedicated tables instead of the doc's generic
system_config key-value store.

VERIFICATION NOTE: three op.create_table() calls plus indexes, verified
end-to-end against a throwaway SQLite database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e0f1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'd9e0f1a2b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'htd_intake_status',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('is_paused', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('paused_at', sa.DateTime(), nullable=True),
        sa.Column('pause_reason', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.UniqueConstraint('tenant_id'),
    )
    op.create_index(op.f('ix_htd_intake_status_tenant_id'), 'htd_intake_status', ['tenant_id'], unique=True)

    op.create_table(
        'htd_monthly_metrics',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('month_start', sa.Date(), nullable=False),
        sa.Column('cohort_size', sa.Integer(), nullable=False),
        sa.Column('converted', sa.Integer(), nullable=False),
        sa.Column('conversion_rate', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
    )
    op.create_index(op.f('ix_htd_monthly_metrics_tenant_id'), 'htd_monthly_metrics', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_htd_monthly_metrics_month_start'), 'htd_monthly_metrics', ['month_start'], unique=False)

    op.create_table(
        'htd_pause_log',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.Enum('PAUSED', 'RESUMED', name='htd_pause_log_action', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('audit_findings', sa.Text(), nullable=True),
        sa.Column('corrective_actions', sa.Text(), nullable=True),
        sa.Column('resumed_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
    )
    op.create_index(op.f('ix_htd_pause_log_tenant_id'), 'htd_pause_log', ['tenant_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_htd_pause_log_tenant_id'), table_name='htd_pause_log')
    op.drop_table('htd_pause_log')
    op.drop_index(op.f('ix_htd_monthly_metrics_month_start'), table_name='htd_monthly_metrics')
    op.drop_index(op.f('ix_htd_monthly_metrics_tenant_id'), table_name='htd_monthly_metrics')
    op.drop_table('htd_monthly_metrics')
    op.drop_index(op.f('ix_htd_intake_status_tenant_id'), table_name='htd_intake_status')
    op.drop_table('htd_intake_status')
