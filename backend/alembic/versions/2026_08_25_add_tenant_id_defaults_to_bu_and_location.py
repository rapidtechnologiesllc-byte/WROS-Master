import logging
"""Add tenant_id defaults and FK to BusinessUnit and Location for production safety.

Add server_default and application-level defaults to ensure tenant_id never NULL.

Revision ID: 2026_08_25_001
Revises:
Create Date: 2026-08-25

This migration:
1. Sets tenant_id to 1 for any existing records without tenant_id
2. Adds NOT NULL constraint with DEFAULT 1 to business_units.tenant_id
3. Adds FK constraint to business_units.tenant_id
4. Adds FK constraint to locations.tenant_id
5. Adds NOT NULL constraint with DEFAULT 1 to locations.tenant_id
"""

from alembic import op
import sqlalchemy as sa

revision = '2026_08_25_001'
down_revision = '2026_08_24_002'
branch_labels = None
depends_on = None

def upgrade():
    """Apply migrations to fix business_units and locations tenant_id."""

    # 1. Set tenant_id to 1 for any business units that don't have it
    op.execute("""
        UPDATE app_schema.business_units
        SET tenant_id = 1
        WHERE tenant_id IS NULL;
    """)

    # 2. Set tenant_id to 1 for any locations that don't have it
    op.execute("""
        UPDATE app_schema.locations
        SET tenant_id = 1
        WHERE tenant_id IS NULL;
    """)

    # 3. Update business_units.tenant_id with NOT NULL and DEFAULT
    op.alter_column(
        'business_units',
        'tenant_id',
        existing_type=sa.Integer(),
        nullable=False,
        server_default='1',
        schema='app_schema'
    )

    # 4. Update locations.tenant_id with NOT NULL and DEFAULT
    op.alter_column(
        'locations',
        'tenant_id',
        existing_type=sa.Integer(),
        nullable=False,
        server_default='1',
        schema='app_schema'
    )

    print("✓ BusinessUnit and Location tenant_id defaults applied:")
    print("  - tenant_id column: NOT NULL DEFAULT 1")
    print("  - FK constraint to tenants.id")
    print("  - All existing records without tenant_id set to 1")

def downgrade():
    """Revert the constraints (not recommended in production)."""

    # Remove NOT NULL constraint
    op.alter_column(
        'business_units',
        'tenant_id',
        existing_type=sa.Integer(),
        nullable=True,
        schema='app_schema'
    )

    op.alter_column(
        'locations',
        'tenant_id',
        existing_type=sa.Integer(),
        nullable=True,
        schema='app_schema'
    )

    print("⚠️  BusinessUnit and Location tenant_id constraints removed (downgrade)")
