"""Add org_level_access column to role_templates

Revision ID: 2026_09_09_001
Revises:
Create Date: 2026-09-09

This migration adds the org_level_access flag to RoleTemplate to replace
hardcoded role checks. Org-level users (CEO, Super User, etc.) have this flag
set to True and see organization-level data across all Business Units.
Regular users have this flag set to False and are scoped to their assigned BU.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_09_09_001'
down_revision = '2_add_clients'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # org_level_access column is now created in base migration
    # This migration just sets values for org-level roles

    # Set org_level_access=True for predefined org-level roles
    # This uses raw SQL to update based on role name
    op.execute("""
        UPDATE role_templates
        SET org_level_access = true
        WHERE name IN ('Super User', 'CEO', 'CFO', 'Admin', 'Partner')
        AND is_system = true
    """)

    print("[MIGRATION] Set org_level_access=true for org-level roles")


def downgrade() -> None:
    # org_level_access column is managed by base migration
    # This migration just reverses the org-level role updates
    op.execute("""
        UPDATE role_templates
        SET org_level_access = false
        WHERE name IN ('Super User', 'CEO', 'CFO', 'Admin', 'Partner')
        AND is_system = true
    """)
