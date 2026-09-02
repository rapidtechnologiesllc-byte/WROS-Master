import logging
"""Fix module unique constraint for multi-tenant support

Revision ID: fix_module_tenant
Revises:
Create Date: 2026-09-02

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'fix_module_tenant'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Change module name unique constraint to composite (name, tenant_id)"""
    # Drop the old unique constraint on name
    op.drop_constraint('modules_name_key', 'modules', type_='unique')

    # Add new composite unique constraint
    op.create_unique_constraint('uq_module_name_tenant', 'modules', ['name', 'tenant_id'])


def downgrade():
    """Revert to old unique constraint on name only"""
    # Drop the composite constraint
    op.drop_constraint('uq_module_name_tenant', 'modules', type_='unique')

    # Add back the old unique constraint on name
    op.create_unique_constraint('modules_name_key', 'modules', ['name'])
