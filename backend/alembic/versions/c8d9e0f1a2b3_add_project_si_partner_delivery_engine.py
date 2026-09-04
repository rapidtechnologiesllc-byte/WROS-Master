import logging
"""add projects.si_partner/delivery_engine + employee_allocations.si_partner (S-358/HRMS-0519)

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-07-23 00:00:00.000000

S-358/HRMS-0519 -- SI Partner Engagement Tagging. delivery_engine is
new on Project (nothing in this codebase derived it any other way --
Project has no Demand link of its own). si_partner is denormalized to
employee_allocations at allocation-creation time per the doc's own
"fast lookup without a join" rationale.

VERIFICATION NOTE: three op.add_column() calls on existing tables,
verified end-to-end against a throwaway SQLite database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, Sequence[str], None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column(
        'projects',
        sa.Column(
            'delivery_engine',
            sa.Enum('SPECIALITY', 'CORE', name='project_delivery_engine', native_enum=False, create_constraint=True),
            nullable=False, server_default='SPECIALITY',
        ),
    )
    op.add_column(
        'projects',
        sa.Column(
            'si_partner',
            sa.Enum('PWC', 'EY', 'CASTLEBAY', 'ZENSAR', 'LTI_MINDTREE', 'OTHER', name='project_si_partner', native_enum=False, create_constraint=True),
            nullable=True,
        ),
    )
    op.add_column(
        'employee_allocations',
        sa.Column(
            'si_partner',
            sa.Enum('PWC', 'EY', 'CASTLEBAY', 'ZENSAR', 'LTI_MINDTREE', 'OTHER', name='employee_allocation_si_partner', native_enum=False, create_constraint=True),
            nullable=True,
        ),
    )

def downgrade() -> None:
    op.drop_column('employee_allocations', 'si_partner')
    op.drop_column('projects', 'si_partner')
    op.drop_column('projects', 'delivery_engine')
