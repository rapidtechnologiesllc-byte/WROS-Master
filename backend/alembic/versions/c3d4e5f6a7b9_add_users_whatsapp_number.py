import logging
"""add users.whatsapp_number for per-staff WhatsApp conversation routing

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-07-21 00:00:00.000003

Extends HRMS-0410's ownership model (candidate_conversations.owner_type/
owner_id) so a conversation owned by a specific recruiter/HR user routes
outbound WhatsApp sends through that user's own number instead of the
single shared number every requirements doc describes. Genuinely new
capability, not from an existing story -- see
app.services.whatsapp_routing_service's docstring.

VERIFICATION NOTE: the op.add_column() call was verified end-to-end
against a throwaway SQLite database and applies cleanly. The
op.create_unique_constraint() call could NOT be verified the same way
-- identical SQLite limitation already documented in e7f8a9b0c1d2's and
f8a9b0c1d2e3's migrations (SQLite has no ALTER-based constraint support
outside of Alembic's batch/copy-recreate mode). The real production
target, SQL Server, supports ALTER TABLE ADD CONSTRAINT natively. Run
this on a staging/dev SQL Server copy first, not production directly,
same as every migration in this package.

FIXED 2026-07-23 (first real run against SQL Server, never actually
possible before this environment's ODBC driver got installed): a plain
UNIQUE CONSTRAINT on SQL Server rejects more than one NULL -- unlike
SQLite/Postgres, which treat NULL as distinct from itself for uniqueness.
Every existing user has whatsapp_number = NULL today, so the constraint
failed immediately on real data. Replaced with a filtered unique index
(unique among non-NULL values only), the standard SQL Server idiom for
"optional but unique when present." mssql_where is a dialect-specific
kwarg other dialects silently ignore, and SQLite already tolerates
multiple NULLs in a plain unique index on its own, so this stays a no-op
change for the SQLite test path.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b9'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('whatsapp_number', sa.String(length=20), nullable=True))
    op.create_index(
        'uq_users_whatsapp_number', 'users', ['whatsapp_number'],
        unique=True,
        mssql_where=sa.text('whatsapp_number IS NOT NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_users_whatsapp_number', 'users')
    op.drop_column('users', 'whatsapp_number')
