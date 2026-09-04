import logging
"""Add WorkOrder model for PO/SOW revenue linkage

Revision ID: 2026_08_12_work_orders
Revises: <previous_revision>
Create Date: 2026-08-12 00:00:00.000000

FEATURE-2026-08-12T5: Work Order / PO / Engagement Records
Links DIRECT-sourced demands to revenue authority (PO/SOW).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2026_08_12_work_orders'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'work_orders',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('po_number', sa.String(200), nullable=False),
        sa.Column('sow_reference', sa.String(500), nullable=True),
        sa.Column('demand_id', sa.String(36), nullable=False),
        sa.Column('client_id', sa.String(36), nullable=False),
        sa.Column('employee_id', sa.String(36), nullable=True),
        sa.Column('project_id', sa.String(36), nullable=True),
        sa.Column('billing_rate_usd_cents', sa.Integer(), nullable=False),
        sa.Column('pay_rate_usd_cents', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('invoicing_contact_email', sa.String(300), nullable=True),
        sa.Column('invoicing_contact_name', sa.String(200), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='ACTIVE'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['demand_id'], ['demands.id'], ),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_work_orders_tenant_id'), 'work_orders', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_work_orders_po_number'), 'work_orders', ['po_number'], unique=False)
    op.create_index(op.f('ix_work_orders_demand_id'), 'work_orders', ['demand_id'], unique=False)
    op.create_index(op.f('ix_work_orders_client_id'), 'work_orders', ['client_id'], unique=False)
    op.create_index(op.f('ix_work_orders_employee_id'), 'work_orders', ['employee_id'], unique=False)
    op.create_index(op.f('ix_work_orders_project_id'), 'work_orders', ['project_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_work_orders_project_id'), table_name='work_orders')
    op.drop_index(op.f('ix_work_orders_employee_id'), table_name='work_orders')
    op.drop_index(op.f('ix_work_orders_client_id'), table_name='work_orders')
    op.drop_index(op.f('ix_work_orders_demand_id'), table_name='work_orders')
    op.drop_index(op.f('ix_work_orders_po_number'), table_name='work_orders')
    op.drop_index(op.f('ix_work_orders_tenant_id'), table_name='work_orders')
    op.drop_table('work_orders')
