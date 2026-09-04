import logging
"""widen employees.employment_type CHECK constraint to include INTERN

Revision ID: a4b5c6d7e8f9
Revises: f1a2b3c4d5e6
Create Date: 2026-07-23 00:00:00.000000

Direct instruction from Avinash, 2026-07-23: Employment Type
(Intern / Full Time / Contract) collection moves from candidate intake
to employee conversion -- it's a decision made when someone is actually
hired, not something to ask a candidate before that. The existing
Employee.employment_type column (app.models.employee.EMPLOYMENT_TYPES)
already covers PERMANENT/CONTRACT/FIXED_TERM; INTERN is the one new
value needed so the conversion-time UI can offer Intern as an option.

Same CHECK-constraint-widening pattern as
2179e135a0ab_fix_employee_status_check_constraint.py (adding new enum
values to an already-migrated table needs a real ALTER, not just an
ORM model change -- app.main's create_all(checkfirst=True) startup
fallback never alters an existing table's constraints).

VERIFICATION NOTE: batch_alter_table's drop/recreate verified
end-to-end against a throwaway SQLite database.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_TYPES = "'PERMANENT','CONTRACT','FIXED_TERM'"
_NEW_TYPES = _OLD_TYPES + ",'INTERN'"

def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('employees') as batch_op:
        batch_op.drop_constraint('ck_employees_employment_type', type_='check')
        batch_op.create_check_constraint('ck_employees_employment_type', f"employment_type IN ({_NEW_TYPES})")

def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('employees') as batch_op:
        batch_op.drop_constraint('ck_employees_employment_type', type_='check')
        batch_op.create_check_constraint('ck_employees_employment_type', f"employment_type IN ({_OLD_TYPES})")
