import logging
"""add pipeline_leakage_flags (S-243 EPIC-02 Revenue Leakage Detection)

Revision ID: c7e9a1f3b5d7
Revises: b5d7f9a1c3e5
Create Date: 2026-08-06 00:00:00.000000

New table only -- no ALTER on any existing table. Per the production
DB-drift incident logged in CLAUDE.md the same day, this codebase's
create_all(checkfirst=True) startup hook will likely create this table
automatically before this migration ever runs against production;
running `alembic upgrade head` (or stamping) afterward is still
required so alembic_version reflects reality. See CLAUDE.md's
"production login outage" session log entry for the full context.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7e9a1f3b5d7'
down_revision: Union[str, Sequence[str], None] = 'b5d7f9a1c3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'pipeline_leakage_flags',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('pattern_type', sa.String(length=30), nullable=False),
        sa.Column('business_unit_id', sa.Integer(), nullable=True),
        sa.Column('opportunity_id', sa.String(length=36), nullable=True),
        sa.Column('demand_id', sa.String(length=36), nullable=True),
        sa.Column('revenue_leakage_flag_id', sa.String(length=36), nullable=True),
        sa.Column('sub_vendor_request_id', sa.String(length=36), nullable=True),
        sa.Column('estimated_impact_usd_cents', sa.Integer(), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.CheckConstraint(
            "pattern_type IN ('STALLED_OPPORTUNITY','UNFILLED_DEMAND','UNBILLED_TIME','SUBVENDOR_COST_OVERRUN')",
            name='ck_pipeline_leakage_flags_pattern_type',
        ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['business_unit_id'], ['business_units.id']),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id']),
        sa.ForeignKeyConstraint(['demand_id'], ['demands.id']),
        sa.ForeignKeyConstraint(['revenue_leakage_flag_id'], ['revenue_leakage_time_layer.id']),
        sa.ForeignKeyConstraint(['sub_vendor_request_id'], ['sub_vendor_requests.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pipeline_leakage_flags_tenant_id'), 'pipeline_leakage_flags', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_pipeline_leakage_flags_pattern_type'), 'pipeline_leakage_flags', ['pattern_type'], unique=False)
    op.create_index(op.f('ix_pipeline_leakage_flags_business_unit_id'), 'pipeline_leakage_flags', ['business_unit_id'], unique=False)
    op.create_index(op.f('ix_pipeline_leakage_flags_opportunity_id'), 'pipeline_leakage_flags', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_pipeline_leakage_flags_demand_id'), 'pipeline_leakage_flags', ['demand_id'], unique=False)
    op.create_index(op.f('ix_pipeline_leakage_flags_revenue_leakage_flag_id'), 'pipeline_leakage_flags', ['revenue_leakage_flag_id'], unique=False)
    op.create_index(op.f('ix_pipeline_leakage_flags_sub_vendor_request_id'), 'pipeline_leakage_flags', ['sub_vendor_request_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('pipeline_leakage_flags')
