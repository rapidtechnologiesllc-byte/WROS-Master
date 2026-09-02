import logging
"""add invoices, invoice_line_items, revenue_leakage_time_layer, reconciliation_alerts (HRMS-0907/0906/0903)

Revision ID: e2f3a4b5c6d7
Revises: d0e1f2a3b4c6
Create Date: 2026-07-21 00:00:00.000010

HRMS-0907 (Invoice Generation/Status), HRMS-0906 (Revenue Leakage
detection), HRMS-0903 (Timesheet-to-Revenue Reconciliation). All four
tables are brand new -- no ALTER on an existing table, so none of the
SQLite batch-mode limitations documented in earlier migrations apply
here.

VERIFICATION NOTE: all four op.create_table() calls (plus indexes)
verified end-to-end against a throwaway SQLite database and apply
cleanly. Run against a staging SQL Server copy first, not production
directly, same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd0e1f2a3b4c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'invoices',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('client_id', sa.String(length=36), nullable=False),
        sa.Column('billing_period_start', sa.Date(), nullable=False),
        sa.Column('billing_period_end', sa.Date(), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'APPROVED', 'SENT', 'PAID', name='invoice_status', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('total_usd_cents', sa.Integer(), nullable=False),
        sa.Column('currency', sa.Enum('USD', 'INR', 'GBP', 'EUR', 'CAD', 'AUD', name='invoice_currency', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('approved_by', sa.String(length=50), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.UserID']),
    )
    op.create_index(op.f('ix_invoices_tenant_id'), 'invoices', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_invoices_project_id'), 'invoices', ['project_id'], unique=False)
    op.create_index(op.f('ix_invoices_client_id'), 'invoices', ['client_id'], unique=False)

    op.create_table(
        'invoice_line_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('invoice_id', sa.String(length=36), nullable=False),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('timesheet_id', sa.String(length=36), nullable=False),
        sa.Column('hours', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('rate_usd_cents', sa.Integer(), nullable=False),
        sa.Column('amount_usd_cents', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['timesheet_id'], ['timesheets.id']),
    )
    op.create_index(op.f('ix_invoice_line_items_invoice_id'), 'invoice_line_items', ['invoice_id'], unique=False)

    op.create_table(
        'revenue_leakage_time_layer',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('approved_hours', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('invoiced_hours', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('unbilled_hours', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('partial_billing_reason', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
    )
    op.create_index(op.f('ix_revenue_leakage_time_layer_tenant_id'), 'revenue_leakage_time_layer', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_revenue_leakage_time_layer_project_id'), 'revenue_leakage_time_layer', ['project_id'], unique=False)

    op.create_table(
        'reconciliation_alerts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('timesheet_id', sa.String(length=36), nullable=False),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('billable_hours', sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column('gap_detected_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('status', sa.Enum('UNRESOLVED', 'RESOLVED', name='reconciliation_alert_status', native_enum=False, create_constraint=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['timesheet_id'], ['timesheets.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
    )
    op.create_index(op.f('ix_reconciliation_alerts_tenant_id'), 'reconciliation_alerts', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_reconciliation_alerts_timesheet_id'), 'reconciliation_alerts', ['timesheet_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('reconciliation_alerts')
    op.drop_table('revenue_leakage_time_layer')
    op.drop_table('invoice_line_items')
    op.drop_table('invoices')
