"""Add org_node_id to employees table

Revision ID: 2026_08_12_add_org_node_to_employees
Revises: 2026_08_12_org_hierarchy
Create Date: 2026-08-12 00:00:00.000000

Links employees to their org hierarchy node for approval chains and role-based access.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_08_12_add_org_node_to_employees'
down_revision = '2026_08_12_org_hierarchy'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add org_node_id column to employees table
    op.add_column(
        'employees',
        sa.Column('org_node_id', sa.String(36), nullable=True),
    )

    # Create index on org_node_id for fast lookups
    op.create_index(
        op.f('ix_employees_org_node_id'),
        'employees',
        ['org_node_id'],
        unique=False
    )

    # Create foreign key constraint
    op.create_foreign_key(
        'fk_employees_org_node_id',
        'employees', 'org_nodes',
        ['org_node_id'], ['id']
    )


def downgrade() -> None:
    # Drop foreign key and index
    op.drop_constraint('fk_employees_org_node_id', 'employees', type_='foreignkey')
    op.drop_index(op.f('ix_employees_org_node_id'), table_name='employees')

    # Drop column
    op.drop_column('employees', 'org_node_id')
