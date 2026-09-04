import logging
"""Add business_unit_id to Invoice model for BU cross-referencing

Revision ID: 2026_08_12_invoice_bu
Revises: 2026_08_12_timesheet_bu
Create Date: 2026-08-12 18:20:00.000000

Session work (2026-08-12): Business Unit implementation - cross-reference across all entities.
Add BU field to invoices for easier querying and reporting by business unit.
"""
from alembic import op
import sqlalchemy as sa

revision = '2026_08_12_invoice_bu'
down_revision = '2026_08_12_timesheet_bu'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('invoices', sa.Column('business_unit_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_invoices_business_unit', 'invoices', 'business_units', ['business_unit_id'], ['id'])
    op.create_index('ix_invoice_tenant_bu', 'invoices', ['tenant_id', 'business_unit_id'])

def downgrade() -> None:
    op.drop_index('ix_invoice_tenant_bu', table_name='invoices')
    op.drop_constraint('fk_invoices_business_unit', 'invoices', type_='foreignkey')
    op.drop_column('invoices', 'business_unit_id')
