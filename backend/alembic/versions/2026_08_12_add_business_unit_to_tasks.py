import logging
"""Add business_unit_id to Task model for BU cross-referencing

Revision ID: 2026_08_12_task_bu
Revises: 2026_08_12_invoice_bu
Create Date: 2026-08-12 18:25:00.000000

Session work (2026-08-12): Business Unit implementation - cross-reference across all entities.
Add BU field to tasks for easier filtering and reporting by business unit.
"""
from alembic import op
import sqlalchemy as sa


revision = '2026_08_12_task_bu'
down_revision = '2026_08_12_invoice_bu'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('business_unit_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_tasks_business_unit', 'tasks', 'business_units', ['business_unit_id'], ['id'])
    op.create_index('ix_task_tenant_bu', 'tasks', ['tenant_id', 'business_unit_id'])


def downgrade() -> None:
    op.drop_index('ix_task_tenant_bu', table_name='tasks')
    op.drop_constraint('fk_tasks_business_unit', 'tasks', type_='foreignkey')
    op.drop_column('tasks', 'business_unit_id')
