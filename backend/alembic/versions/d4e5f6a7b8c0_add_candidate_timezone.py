import logging
"""add candidates.timezone for conversation-inactivity send-window gating

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b9
Create Date: 2026-07-21 00:00:00.000004

app.services.conversation_inactivity_service needs the candidate's
local timezone to decide whether it's a reasonable hour (09:00-21:00)
to auto-message them, and to anchor the weekend-pause math on the
candidate's own calendar. Every existing row backfills to BlitzenX's
default (same as users.timezone).

VERIFICATION NOTE: verified end-to-end against a throwaway SQLite
database (plain nullable-compatible ADD COLUMN with server_default, no
ALTER-on-constraint operation). Run against a staging SQL Server copy
first, not production directly, same as every migration in this
package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c0'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'candidates',
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='Asia/Kolkata'),
    )

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('candidates', 'timezone')
