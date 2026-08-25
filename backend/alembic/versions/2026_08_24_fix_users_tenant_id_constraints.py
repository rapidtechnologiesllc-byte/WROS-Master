"""Fix users table tenant_id constraints for production safety.

Add NOT NULL constraint and ensure all existing users have tenant_id set.

Revision ID: 2026_08_24_002
Revises:
Create Date: 2026-08-24

This migration:
1. Ensures tenant_id is NOT NULL with default 1
2. Updates all existing users without tenant_id to use tenant_id = 1
3. Adds database-level constraints to prevent invalid states
"""

from alembic import op
import sqlalchemy as sa


revision = '2026_08_24_002'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Apply migrations to fix users tenant_id constraints."""

    # 1. Set tenant_id to 1 for any users that don't have it
    op.execute("""
        UPDATE app_schema.users
        SET tenant_id = 1
        WHERE tenant_id IS NULL;
    """)

    # 2. Add NOT NULL constraint to tenant_id column with default
    op.alter_column(
        'users',
        'tenant_id',
        existing_type=sa.Integer(),
        nullable=False,
        server_default='1',
        schema='app_schema'
    )

    print("✓ Users tenant_id constraints fixed:")
    print("  - tenant_id column: NOT NULL DEFAULT 1")
    print("  - All existing users updated to have tenant_id = 1")


def downgrade():
    """Revert the constraints (not recommended in production)."""

    # Remove NOT NULL constraint
    op.alter_column(
        'users',
        'tenant_id',
        existing_type=sa.Integer(),
        nullable=True,
        schema='app_schema'
    )

    print("⚠️  Users tenant_id constraints removed (downgrade)")
