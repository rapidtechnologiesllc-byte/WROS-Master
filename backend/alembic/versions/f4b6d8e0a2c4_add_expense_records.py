import logging
"""add expense_records (Partner/BU spend tracking, purpose+client tagged)

Revision ID: f4b6d8e0a2c4
Revises: e1a3c5f7b9d2
Create Date: 2026-08-05 00:00:00.000000

Avinash, 2026-08-05: expense tracking needs a `purpose` (client-current
/ client-prospect / conference / investment / other) and, for
client-directed spend, a client_id -- even while that client is still
a PROSPECT -- so the full investment-to-breakeven history for a client
can be computed from day one. Structure mirrors the real FY26-27
finance workbook's Expense Ledger (Category/Subcategory/Employee-
Partner/Location/Client/Home BU/Amount/Description/Receipt Ref/
Approved By/Date/Payment Status) -- no real figures, this is schema
only.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f4b6d8e0a2c4'
down_revision: Union[str, Sequence[str], None] = 'e1a3c5f7b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'expense_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('business_unit_id', sa.Integer(), nullable=True),
        sa.Column('logged_by_user_id', sa.String(length=50), nullable=False),
        sa.Column('purpose', sa.String(length=30), nullable=False),
        sa.Column('client_id', sa.String(length=36), nullable=True),
        sa.Column('conference_name', sa.String(length=200), nullable=True),
        sa.Column('investment_label', sa.String(length=200), nullable=True),
        sa.Column('expense_category', sa.String(length=30), nullable=False),
        sa.Column('travel_type', sa.String(length=30), nullable=True),
        sa.Column('trip_label', sa.String(length=200), nullable=True),
        sa.Column('amount_usd_cents', sa.Integer(), nullable=False),
        sa.Column('location', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('receipt_ref', sa.String(length=300), nullable=True),
        sa.Column('expense_date', sa.Date(), nullable=False),
        sa.Column('payment_status', sa.String(length=20), nullable=False),
        sa.Column('approved_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['business_unit_id'], ['business_units.id']),
        sa.ForeignKeyConstraint(['logged_by_user_id'], ['users.UserID']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.UserID']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "purpose IN ('CLIENT_CURRENT','CLIENT_PROSPECT','CONFERENCE','INVESTMENT','OTHER')",
            name='ck_expense_records_purpose',
        ),
        sa.CheckConstraint(
            "expense_category IN ('TRAVEL','MEALS','LODGING','ENTERTAINMENT','OTHER')",
            name='ck_expense_records_category',
        ),
        sa.CheckConstraint(
            "travel_type IS NULL OR travel_type IN ('AIRFARE','GROUND_TRANSPORT','HOTEL','MEALS','OTHER')",
            name='ck_expense_records_travel_type',
        ),
        sa.CheckConstraint(
            "payment_status IN ('PENDING','APPROVED','REIMBURSED')",
            name='ck_expense_records_payment_status',
        ),
    )
    op.create_index(op.f('ix_expense_records_tenant_id'), 'expense_records', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_expense_records_business_unit_id'), 'expense_records', ['business_unit_id'], unique=False)
    op.create_index(op.f('ix_expense_records_logged_by_user_id'), 'expense_records', ['logged_by_user_id'], unique=False)
    op.create_index(op.f('ix_expense_records_client_id'), 'expense_records', ['client_id'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_expense_records_client_id'), table_name='expense_records')
    op.drop_index(op.f('ix_expense_records_logged_by_user_id'), table_name='expense_records')
    op.drop_index(op.f('ix_expense_records_business_unit_id'), table_name='expense_records')
    op.drop_index(op.f('ix_expense_records_tenant_id'), table_name='expense_records')
    op.drop_table('expense_records')
