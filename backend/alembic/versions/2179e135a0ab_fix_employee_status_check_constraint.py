import logging
"""fix employees.status CHECK constraint to include SPECIALITY_READY/PERFORMANCE_MANAGED (S-365/HRMS-0521)

Revision ID: 2179e135a0ab
Revises: f3a4b5c6d7e8
Create Date: 2026-07-22 00:00:00.000000

Real, deployable gap found while scoping Phase 4 (Resource Management):
S-365/HRMS-0521's Buddy Program Graduation Gate (commit 2d7604f) added
SPECIALITY_READY and PERFORMANCE_MANAGED to app.models.employee.EMPLOYEE_STATUSES
and to ALLOWED_STATUS_TRANSITIONS, but that commit touched no migration file --
it built on columns the original employees migration
(e7f8a9b0c1d2_add_employee_client_demand_entities.py) already had, so nothing
*looked* missing. The one thing that migration did NOT anticipate is these two
new status values: `ck_employees_status`'s CHECK constraint there only allows
the original 7 values. Every later Workstream 3 test passes because tests
create tables fresh from the CURRENT ORM model via Base.metadata.create_all(),
never through this constraint's original text -- masking the gap completely.
Against the real deployed database, transitioning an employee to
SPECIALITY_READY or PERFORMANCE_MANAGED (S-365's whole feature) would fail
with a CHECK constraint violation, since app.main's create_all(checkfirst=True)
startup fallback only creates tables that don't exist yet -- it never alters
an existing table's constraints.

Scope check: this is the only CHECK-constraint/enum drift found between the
current ORM model and its original migration for tables touched by
Workstream 1/2/3 -- delivery_engine, buddy_program_status, and htd_phase were
all "folded in from the start" per that same original migration and already
include every value the model currently defines.

VERIFICATION NOTE: batch_alter_table's drop/recreate verified end-to-end
against a throwaway SQLite database. Run against a staging SQL Server copy
first, not production directly, same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2179e135a0ab'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_STATUSES = "'PRE_JOINING','ACTIVE','ON_LEAVE','BENCH','ALLOCATED','NOTICE_PERIOD','EXITED'"
_NEW_STATUSES = _OLD_STATUSES + ",'SPECIALITY_READY','PERFORMANCE_MANAGED'"

def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('employees') as batch_op:
        batch_op.drop_constraint('ck_employees_status', type_='check')
        batch_op.create_check_constraint('ck_employees_status', f"status IN ({_NEW_STATUSES})")

def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('employees') as batch_op:
        batch_op.drop_constraint('ck_employees_status', type_='check')
        batch_op.create_check_constraint('ck_employees_status', f"status IN ({_OLD_STATUSES})")
