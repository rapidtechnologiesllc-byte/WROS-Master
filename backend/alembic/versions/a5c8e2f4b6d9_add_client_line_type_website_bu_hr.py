import logging
"""add clients.line_type/website, business_units.hr_manager_employee_id, TIMESHEET_APPROVER contact role

Revision ID: a5c8e2f4b6d9
Revises: c7e9a1f3b5d7
Create Date: 2026-08-06 00:00:00.000000

Client Management redesign, confirmed directly with Avinash 2026-08-06
(see CLAUDE.md session log): line_type replaces client_type on the
create form (Core/Specialty, same taxonomy as Employee.delivery_engine);
website is a new dedup key; business_units.hr_manager_employee_id is
symmetric to the existing bu_head_employee_id, for Job-creation
auto-assignment; TIMESHEET_APPROVER is a new client_contacts role_type
value.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a5c8e2f4b6d9'
down_revision: Union[str, Sequence[str], None] = 'c7e9a1f3b5d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('clients', sa.Column('line_type', sa.String(length=20), nullable=True))
    op.create_check_constraint(
        'client_line_type', 'clients', "line_type IN ('CORE','SPECIALITY')",
    )
    op.add_column('clients', sa.Column('website', sa.String(length=300), nullable=True))

    op.add_column('business_units', sa.Column('hr_manager_employee_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(
        'fk_business_units_hr_manager_employee_id', 'business_units', 'employees',
        ['hr_manager_employee_id'], ['id'],
    )
    op.create_index(
        op.f('ix_business_units_hr_manager_employee_id'), 'business_units', ['hr_manager_employee_id'], unique=False,
    )

    with op.batch_alter_table('client_contacts') as batch_op:
        batch_op.drop_constraint('contact_role_type', type_='check')
        batch_op.create_check_constraint(
            'contact_role_type',
            "role_type IN ('HIRING_MANAGER','TECHNICAL_PANEL','PROCUREMENT','ACCOUNTS','PRIMARY','TIMESHEET_APPROVER')",
        )

def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('client_contacts') as batch_op:
        batch_op.drop_constraint('contact_role_type', type_='check')
        batch_op.create_check_constraint(
            'contact_role_type',
            "role_type IN ('HIRING_MANAGER','TECHNICAL_PANEL','PROCUREMENT','ACCOUNTS','PRIMARY')",
        )

    op.drop_index(op.f('ix_business_units_hr_manager_employee_id'), table_name='business_units')
    op.drop_constraint('fk_business_units_hr_manager_employee_id', 'business_units', type_='foreignkey')
    op.drop_column('business_units', 'hr_manager_employee_id')

    op.drop_column('clients', 'website')
    op.drop_constraint('client_line_type', 'clients', type_='check')
    op.drop_column('clients', 'line_type')
