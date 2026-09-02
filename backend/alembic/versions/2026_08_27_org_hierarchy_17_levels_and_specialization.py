import logging
"""Add 17-level hierarchy and specialization to org system

Revision ID: 2026_08_27_org_hierarchy_levels
Revises: 2026_08_27_message_queue
Create Date: 2026-08-27 10:00:00.000000

This migration adds:
1. hierarchy_level field to org_nodes table (1-17 level enforcement)
2. specialization field to org_nodes table (17-level hierarchy specialization)
3. hierarchy_level and specialization fields to role_templates table
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_08_27_org_hierarchy_levels'
down_revision = '2026_08_27_message_queue'
branch_labels = None
depends_on = None


def upgrade():
    """Add hierarchy_level and specialization fields for 17-level org structure"""

    # Add hierarchy_level to org_nodes table (existing table)
    op.add_column('org_nodes', sa.Column(
        'hierarchy_level',
        sa.Integer(),
        nullable=False,
        server_default='5',
        comment='1-17: Intern→CEO, defines authority'
    ))

    # Add specialization to org_nodes table (existing table)
    op.add_column('org_nodes', sa.Column(
        'specialization',
        sa.String(100),
        nullable=False,
        server_default='General',
        comment='Specialization domain: Recruitment, Development, HR, Finance, Project Management, QA, Business Analysis'
    ))

    # Add hierarchy_level to role_templates table
    op.add_column('role_templates', sa.Column(
        'hierarchy_level',
        sa.Integer(),
        nullable=False,
        server_default='5',
        comment='Org hierarchy level (1-17): 1=Intern through 17=CEO'
    ))

    # Add specialization to role_templates table
    op.add_column('role_templates', sa.Column(
        'specialization',
        sa.String(100),
        nullable=False,
        server_default='General',
        comment='Specialization domain: Recruitment, Development, HR, Finance, Project Management, QA, Business Analysis'
    ))


def downgrade():
    """Remove hierarchy_level and specialization fields"""

    # Remove from org_nodes
    op.drop_column('org_nodes', 'hierarchy_level')
    op.drop_column('org_nodes', 'specialization')

    # Remove from role_templates
    op.drop_column('role_templates', 'hierarchy_level')
    op.drop_column('role_templates', 'specialization')
