import logging
"""add bu_revenue_targets + partner_goals (S-267 + CEO-set PartnerGoal)

Revision ID: b5d7f9a1c3e5
Revises: a3c5e7f9b1d3
Create Date: 2026-08-05 00:00:00.000000

S-267/HRMS-0301 BU Revenue Target (BU Head/Director/Admin-set) +
net-new PartnerGoal (CEO-set only, per Avinash's explicit 2026-08-05
override for the Partner level). Both append-only -- no update/delete
path, only new rows superseding the prior active target for a period.

`id` is a real autoincrement integer, not this codebase's usual UUID
string PK -- a deliberate deviation. These two tables need a portable,
DB-guaranteed strict insertion order to correctly resolve "most recent
target wins," and a created_at timestamp tiebreak is not safe for that
(reproduced directly: two targets set in rapid succession can land in
the same wall-clock instant). See app.models.revenue_target's module
docstring for the full reasoning.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b5d7f9a1c3e5'
down_revision: Union[str, Sequence[str], None] = 'a3c5e7f9b1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'bu_revenue_targets',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('business_unit_id', sa.Integer(), nullable=False),
        sa.Column('target_period', sa.String(length=10), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('target_amount_usd_cents', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['business_unit_id'], ['business_units.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.UserID']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "target_period IN ('Q1','Q2','Q3','Q4','H1','H2','ANNUAL')",
            name='ck_bu_revenue_targets_period',
        ),
    )
    op.create_index(op.f('ix_bu_revenue_targets_tenant_id'), 'bu_revenue_targets', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_bu_revenue_targets_business_unit_id'), 'bu_revenue_targets', ['business_unit_id'], unique=False)

    op.create_table(
        'partner_goals',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('partner_user_id', sa.String(length=50), nullable=False),
        sa.Column('target_period', sa.String(length=10), nullable=False),
        sa.Column('fiscal_year', sa.Integer(), nullable=False),
        sa.Column('target_amount_usd_cents', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['partner_user_id'], ['users.UserID']),
        sa.ForeignKeyConstraint(['created_by'], ['users.UserID']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "target_period IN ('Q1','Q2','Q3','Q4','H1','H2','ANNUAL')",
            name='ck_partner_goals_period',
        ),
    )
    op.create_index(op.f('ix_partner_goals_tenant_id'), 'partner_goals', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_partner_goals_partner_user_id'), 'partner_goals', ['partner_user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_partner_goals_partner_user_id'), table_name='partner_goals')
    op.drop_index(op.f('ix_partner_goals_tenant_id'), table_name='partner_goals')
    op.drop_table('partner_goals')

    op.drop_index(op.f('ix_bu_revenue_targets_business_unit_id'), table_name='bu_revenue_targets')
    op.drop_index(op.f('ix_bu_revenue_targets_tenant_id'), table_name='bu_revenue_targets')
    op.drop_table('bu_revenue_targets')
