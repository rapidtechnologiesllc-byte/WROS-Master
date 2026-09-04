import logging
"""Add business_unit_id to Timesheet model for BU cross-referencing

Revision ID: 2026_08_12_timesheet_bu
Revises: 2026_08_12_perf_events_bu
Create Date: 2026-08-12 18:15:00.000000

Session work (2026-08-12): Business Unit implementation - cross-reference across all entities.
Add BU field to timesheets for easier querying by business unit.
"""
from alembic import op
import sqlalchemy as sa

revision = '2026_08_12_timesheet_bu'
down_revision = '2026_08_12_perf_events_bu'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('timesheets', sa.Column('business_unit_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_timesheets_business_unit', 'timesheets', 'business_units', ['business_unit_id'], ['id'])
    op.create_index('ix_timesheet_tenant_bu', 'timesheets', ['tenant_id', 'business_unit_id'])

def downgrade() -> None:
    op.drop_index('ix_timesheet_tenant_bu', table_name='timesheets')
    op.drop_constraint('fk_timesheets_business_unit', 'timesheets', type_='foreignkey')
    op.drop_column('timesheets', 'business_unit_id')
