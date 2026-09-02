import logging
"""add tasks.expense_id + partner_incentive_rules/events

Revision ID: a3c5e7f9b1d3
Revises: f4b6d8e0a2c4
Create Date: 2026-08-05 00:00:00.000000

Avinash, 2026-08-05: approved expenses need a real Task assigned to
Finance to track "mark it paid once paid" (tasks.expense_id). Separate,
same-day ask: partner new-logo/revenue-share incentive eligibility is
config data (partner_incentive_rules), not hardcoded per-partner logic
-- "this is not applicable to Curtis" is expressed by him simply having
no NEW_LOGO_BONUS rule row, not a name check anywhere in code.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3c5e7f9b1d3'
down_revision: Union[str, Sequence[str], None] = 'f4b6d8e0a2c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('expense_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_tasks_expense_id'), 'tasks', ['expense_id'], unique=False)

    op.create_table(
        'partner_incentive_rules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('partner_user_id', sa.String(length=50), nullable=False),
        sa.Column('incentive_type', sa.String(length=30), nullable=False),
        sa.Column('amount_usd_cents', sa.Integer(), nullable=True),
        sa.Column('revenue_share_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('trigger_description', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['partner_user_id'], ['users.UserID']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "incentive_type IN ('NEW_LOGO_BONUS','REVENUE_SHARE','DEPLOYMENT_BONUS','OTHER')",
            name='ck_partner_incentive_rules_type',
        ),
    )
    op.create_index(op.f('ix_partner_incentive_rules_tenant_id'), 'partner_incentive_rules', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_partner_incentive_rules_partner_user_id'), 'partner_incentive_rules', ['partner_user_id'], unique=False)

    op.create_table(
        'partner_incentive_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('rule_id', sa.String(length=36), nullable=False),
        sa.Column('partner_user_id', sa.String(length=50), nullable=False),
        sa.Column('client_id', sa.String(length=36), nullable=True),
        sa.Column('amount_usd_cents', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('triggered_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['rule_id'], ['partner_incentive_rules.id']),
        sa.ForeignKeyConstraint(['partner_user_id'], ['users.UserID']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('PENDING','PAID')", name='ck_partner_incentive_events_status'),
        # DB-level idempotency, not just an application-side check-then-
        # insert (which races under concurrent calls) -- at most one
        # NEW_LOGO_BONUS event per (rule, client) ever.
        sa.UniqueConstraint('rule_id', 'client_id', name='uq_partner_incentive_events_rule_client'),
    )
    op.create_index(op.f('ix_partner_incentive_events_tenant_id'), 'partner_incentive_events', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_partner_incentive_events_rule_id'), 'partner_incentive_events', ['rule_id'], unique=False)
    op.create_index(op.f('ix_partner_incentive_events_partner_user_id'), 'partner_incentive_events', ['partner_user_id'], unique=False)
    op.create_index(op.f('ix_partner_incentive_events_client_id'), 'partner_incentive_events', ['client_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_partner_incentive_events_client_id'), table_name='partner_incentive_events')
    op.drop_index(op.f('ix_partner_incentive_events_partner_user_id'), table_name='partner_incentive_events')
    op.drop_index(op.f('ix_partner_incentive_events_rule_id'), table_name='partner_incentive_events')
    op.drop_index(op.f('ix_partner_incentive_events_tenant_id'), table_name='partner_incentive_events')
    op.drop_table('partner_incentive_events')

    op.drop_index(op.f('ix_partner_incentive_rules_partner_user_id'), table_name='partner_incentive_rules')
    op.drop_index(op.f('ix_partner_incentive_rules_tenant_id'), table_name='partner_incentive_rules')
    op.drop_table('partner_incentive_rules')

    op.drop_index(op.f('ix_tasks_expense_id'), table_name='tasks')
    op.drop_column('tasks', 'expense_id')
