import logging
"""add users.msgraph_mail_last_synced_at (EPIC-14/S-435 lifecycle communication linking)

Revision ID: c5e7a9b1d3f6
Revises: b3d5f7a9c1e4
Create Date: 2026-08-05 00:00:00.000000

EPIC-14/S-435 (HRMS-1408) -- Candidate & Employee Lifecycle
Communication Linking. Nullable, only ever populated once a user's
first M365 mail sync runs; every existing row is unaffected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c5e7a9b1d3f6'
down_revision: Union[str, Sequence[str], None] = 'b3d5f7a9c1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('msgraph_mail_last_synced_at', sa.DateTime(), nullable=True))

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'msgraph_mail_last_synced_at')
