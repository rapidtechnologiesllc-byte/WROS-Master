"""Remove duplicate indexes created during schema initialization failures

Revision ID: 2026_08_15_001
Revises: 20260815_expand_persona 
Create Date: 2026-08-15 06:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_08_15_001'
down_revision = '20260815_expand_persona'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove duplicate indexes that may have been created during failed initialization."""
    # Drop all duplicate indexes if they exist
    duplicate_indexes = [
        "ix_role_permissions_role_id",
        "ix_role_permissions_permission_id",
        "ix_detailed_role_permissions_role_id",
        "ix_detailed_role_permissions_permission_id",
    ]

    for index_name in duplicate_indexes:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")
        print(f"[MIGRATION] Removed duplicate index: {index_name}")


def downgrade() -> None:
    """Downgrade migration - recreate the indexes if needed."""
    # This is a cleanup migration, downgrade is not typically needed
    pass
