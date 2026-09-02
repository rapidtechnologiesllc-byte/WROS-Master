import logging
"""add timesheets.task_id, make allocation_id nullable (Task<->Timesheet tie)

Revision ID: e7f2a4c6b8d1
Revises: d4e6f8a1c3b5
Create Date: 2026-08-05 00:00:00.000000

Backlog item, 2026-08-05 (Task<->Timesheet tie, wros_task_numbering_s434_backlog):
Avinash -- task effort and the timesheet must be tied together directly.
Real architecture fork this needed a decision on, resolved by Avinash:
nullable allocation_id + a new task_id column as the alternative source,
rather than forcing every Task type (an HR ticket has no client
allocation) through the revenue-critical, allocation-required Timesheet
table as it stood.

ck_timesheet_allocation_or_task is a real DB CHECK constraint, not just
service-layer enforcement -- this is a structural invariant (a timesheet
must trace back to SOMETHING billable-or-trackable), unlike the
softer si_partner/business_type conditional-field rules on Project
which stayed service-layer-only because create_project() is reused by
many unrelated tests' fixtures with no opinion on those fields.

VERIFICATION NOTE: batch_alter_table used for the allocation_id nullable
change and the new CHECK/UNIQUE constraints, verified end-to-end against
a throwaway SQLite database. Run against a staging SQL Server copy
first, not production directly, same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7f2a4c6b8d1'
down_revision: Union[str, Sequence[str], None] = 'd4e6f8a1c3b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('timesheets') as batch_op:
        batch_op.add_column(sa.Column('task_id', sa.Integer(), nullable=True))
        batch_op.alter_column('allocation_id', existing_type=sa.String(length=36), nullable=True)
        batch_op.create_foreign_key('fk_timesheets_task_id', 'tasks', ['task_id'], ['id'])
        batch_op.create_index(op.f('ix_timesheets_task_id'), ['task_id'], unique=False)
        batch_op.create_unique_constraint(
            'uq_timesheet_per_employee_task_week',
            ['tenant_id', 'employee_id', 'task_id', 'week_starting_date'],
        )
        batch_op.create_check_constraint(
            'ck_timesheet_allocation_or_task',
            '(allocation_id IS NOT NULL) OR (task_id IS NOT NULL)',
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('timesheets') as batch_op:
        batch_op.drop_constraint('ck_timesheet_allocation_or_task', type_='check')
        batch_op.drop_constraint('uq_timesheet_per_employee_task_week', type_='unique')
        batch_op.drop_index(op.f('ix_timesheets_task_id'))
        batch_op.drop_constraint('fk_timesheets_task_id', type_='foreignkey')
        batch_op.alter_column('allocation_id', existing_type=sa.String(length=36), nullable=False)
        batch_op.drop_column('task_id')
