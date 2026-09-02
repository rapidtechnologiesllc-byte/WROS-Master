import logging
"""expand timesheet_anomaly_flags.anomaly_type CHECK to include UNLINKED_TASK

Revision ID: f1a3c5e7b9d2
Revises: e7f2a4c6b8d1
Create Date: 2026-08-05 00:00:00.000000

Backlog item, 2026-08-05 (Task<->Timesheet tie): "A user must NOT be
able to log an arbitrary/unlinked timesheet entry that doesn't trace
back to real Task work." UNLINKED_TASK is the new anomaly type
app.services.timesheet_anomaly_service flags on a task-linked
timesheet whose Task doesn't exist, or isn't actually assigned to the
employee who logged the entry. Same batch_alter_table drop/recreate
pattern as 2179e135a0ab (employees.status CHECK expansion).

VERIFICATION NOTE: verified end-to-end against a throwaway SQLite
database. Run against a staging SQL Server copy first, not production
directly, same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f1a3c5e7b9d2'
down_revision: Union[str, Sequence[str], None] = 'e7f2a4c6b8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_TYPES = "'WEEKEND','OVER_12H','COMPLETED_PROJECT','DUPLICATE'"
_NEW_TYPES = _OLD_TYPES + ",'UNLINKED_TASK'"


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('timesheet_anomaly_flags') as batch_op:
        batch_op.drop_constraint('timesheet_anomaly_type', type_='check')
        batch_op.create_check_constraint('timesheet_anomaly_type', f"anomaly_type IN ({_NEW_TYPES})")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('timesheet_anomaly_flags') as batch_op:
        batch_op.drop_constraint('timesheet_anomaly_type', type_='check')
        batch_op.create_check_constraint('timesheet_anomaly_type', f"anomaly_type IN ({_OLD_TYPES})")
