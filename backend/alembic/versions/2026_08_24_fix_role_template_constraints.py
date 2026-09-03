import logging
"""Fix role template constraints for production safety.

Add NOT NULL constraints and ensure all existing role templates are enabled.

Revision ID: 2026_08_24_001
Revises:
Create Date: 2026-08-24

This migration:
1. Ensures enabled column defaults to TRUE
2. Ensures tenant_id is NOT NULL with default 1
3. Updates all existing role templates to be enabled
4. Adds database-level constraints to prevent invalid states
"""

from alembic import op
import sqlalchemy as sa

revision = '2026_08_24_001'
down_revision = 'e7a1c3f9b2d6'
branch_labels = None
depends_on = None

def upgrade():
    """Apply migrations to fix role template constraints."""

    # 1. Update all role templates to have enabled=true if they don't
    op.execute("""
        UPDATE app_schema.role_templates
        SET enabled = true
        WHERE enabled IS NULL OR enabled = false;
    """)

    # 2. Set tenant_id to 1 for any role templates that don't have it
    op.execute("""
        UPDATE app_schema.role_templates
        SET tenant_id = 1
        WHERE tenant_id IS NULL;
    """)

    # 3. Add NOT NULL constraint to enabled column with default
    op.alter_column(
        'role_templates',
        'enabled',
        existing_type=sa.Boolean(),
        nullable=False,
        server_default='true',
        schema='app_schema'
    )

    # 4. Add NOT NULL constraint to tenant_id column with default
    op.alter_column(
        'role_templates',
        'tenant_id',
        existing_type=sa.Integer(),
        nullable=False,
        server_default='1',
        schema='app_schema'
    )

    print("✓ Role template constraints fixed:")
    print("  - enabled column: NOT NULL DEFAULT TRUE")
    print("  - tenant_id column: NOT NULL DEFAULT 1")
    print("  - All existing role templates updated to be enabled")

def downgrade():
    """Revert the constraints (not recommended in production)."""

    # Remove NOT NULL constraints
    op.alter_column(
        'role_templates',
        'enabled',
        existing_type=sa.Boolean(),
        nullable=True,
        schema='app_schema'
    )

    op.alter_column(
        'role_templates',
        'tenant_id',
        existing_type=sa.Integer(),
        nullable=True,
        schema='app_schema'
    )

    print("⚠️  Role template constraints removed (downgrade)")
