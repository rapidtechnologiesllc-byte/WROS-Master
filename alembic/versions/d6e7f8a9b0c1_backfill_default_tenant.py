"""backfill default tenant for existing rows

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-20 05:00:00.000000

IMPORTANT: this migration must run BEFORE any route is switched to use
app.core.tenant_context.get_tenant_scoped_query() in production.
get_tenant_scoped_query() fails closed (403) for a user with
tenant_id = NULL -- every existing row has NULL today, since HRMS-0109
added the column as nullable-for-safe-upgrade. Without this backfill,
switching a live route to tenant-scoped queries would lock every
current user out of it immediately.

Seeds exactly one tenant ("BlitzenX") and points every existing
users/candidates/jobs row with a NULL tenant_id at it -- this platform
has exactly one real tenant today, so this is a safe, correct backfill,
not a guess. Future tenants get their own row + their users/candidates/
jobs get created with that tenant_id from the start.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, Sequence[str], None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    tenants = sa.table(
        'tenants',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('is_active', sa.Boolean),
    )

    existing = conn.execute(sa.text("SELECT id FROM tenants WHERE name = :name"), {"name": "BlitzenX"}).fetchone()
    if existing:
        tenant_id = existing[0]
    else:
        result = conn.execute(
            tenants.insert().values(name="BlitzenX", is_active=True)
        )
        tenant_id = result.inserted_primary_key[0]

    conn.execute(sa.text("UPDATE users SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": tenant_id})
    conn.execute(sa.text("UPDATE candidates SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": tenant_id})
    conn.execute(sa.text("UPDATE jobs SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": tenant_id})


def downgrade() -> None:
    """
    Deliberately a no-op: reverting to tenant_id = NULL for every row
    would immediately break any route that by then depends on
    get_tenant_scoped_query()'s fail-closed behavior. If this tenant
    was created in error, fix the data directly rather than via
    downgrade.
    """
    pass
