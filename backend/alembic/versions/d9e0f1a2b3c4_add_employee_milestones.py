import logging
"""add employee_milestones table (S-356/HRMS-0517)

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-07-23 00:00:00.000000

S-356/HRMS-0517 -- Employee Milestone Tracker: Personal, Project & Org.
Deliberately a new table, not an extension of the already-shipped
project_milestones -- see app.models.employee_milestone's module
docstring for why this is a real table-name collision between two
stories, not drift to silently resolve.

VERIFICATION NOTE: op.create_table() plus two indexes, verified
end-to-end against a throwaway SQLite database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd9e0f1a2b3c4'
down_revision: Union[str, Sequence[str], None] = 'c8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'employee_milestones',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.String(length=36), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=True),
        sa.Column('milestone_type', sa.Enum('PERSONAL', 'PROJECT', 'ORG', name='employee_milestone_type', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_date', sa.Date(), nullable=False),
        sa.Column('completed_date', sa.Date(), nullable=True),
        sa.Column('status', sa.Enum('PENDING', 'IN_PROGRESS', 'COMPLETED', 'OVERDUE', 'CANCELLED', 'EXTENDED', name='employee_milestone_status', native_enum=False, create_constraint=True), nullable=False, server_default='PENDING'),
        sa.Column('completion_notes', sa.Text(), nullable=True),
        sa.Column('set_by', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
    )
    op.create_index(op.f('ix_employee_milestones_tenant_id'), 'employee_milestones', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_employee_milestones_project_id'), 'employee_milestones', ['project_id'], unique=False)
    op.create_index(op.f('ix_employee_milestones_employee_id'), 'employee_milestones', ['employee_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_employee_milestones_employee_id'), table_name='employee_milestones')
    op.drop_index(op.f('ix_employee_milestones_project_id'), table_name='employee_milestones')
    op.drop_index(op.f('ix_employee_milestones_tenant_id'), table_name='employee_milestones')
    op.drop_table('employee_milestones')
