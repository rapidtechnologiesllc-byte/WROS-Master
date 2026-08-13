"""Add business_unit_id to EmployeePerformanceEvent model for BU cross-referencing

Revision ID: 2026_08_12_perf_events_bu
Revises: 2026_08_12_opportunity_bu
Create Date: 2026-08-12 18:10:00.000000

Session work (2026-08-12): Business Unit implementation - cross-reference across all entities.
Add BU field to performance events for easier querying by business unit.
"""
from alembic import op
import sqlalchemy as sa


revision = '2026_08_12_perf_events_bu'
down_revision = '2026_08_12_opportunity_bu'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('employee_performance_events', sa.Column('business_unit_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_perf_events_business_unit', 'employee_performance_events', 'business_units', ['business_unit_id'], ['id'])
    op.create_index('ix_perf_events_tenant_bu', 'employee_performance_events', ['tenant_id', 'business_unit_id'])
    op.create_index('ix_perf_events_employee_bu', 'employee_performance_events', ['employee_id', 'business_unit_id'])


def downgrade() -> None:
    op.drop_index('ix_perf_events_employee_bu', table_name='employee_performance_events')
    op.drop_index('ix_perf_events_tenant_bu', table_name='employee_performance_events')
    op.drop_constraint('fk_perf_events_business_unit', 'employee_performance_events', type_='foreignkey')
    op.drop_column('employee_performance_events', 'business_unit_id')
