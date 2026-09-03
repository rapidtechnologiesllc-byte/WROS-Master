import logging
"""add user lifecycle termination tracking (Users screen lifecycle management)

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-08-12 00:00:00.000000

Adds user termination tracking to the Users table:
- terminated_at: DateTime when user was terminated (NULL = active)
- terminated_by_user_id: FK to the user who terminated them

This enables:
1. Marking users as terminated without deletion (audit trail preserved)
2. Tracking who performed the termination
3. Reinstatement capability (clearing terminated_at)
4. Task redistribution workflow on termination
5. Status badges in Users lifecycle management screen
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a9b0c1d2e3f4'
down_revision: Union[str, Sequence[str], None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    # Add termination tracking columns to users table
    op.add_column(
        'users',
        sa.Column('terminated_at', sa.DateTime(timezone=False), nullable=True, index=True)
    )
    op.add_column(
        'users',
        sa.Column('terminated_by_user_id', sa.String(length=50), nullable=True, index=True)
    )
    # Add FK constraint from terminated_by_user_id to users.UserID
    op.create_foreign_key(
        'fk_users_terminated_by_user_id',
        'users',
        'users',
        ['terminated_by_user_id'],
        ['UserID'],
    )

def downgrade() -> None:
    """Downgrade schema."""
    # Drop FK constraint and columns
    op.drop_constraint('fk_users_terminated_by_user_id', 'users', type_='foreignkey')
    op.drop_column('users', 'terminated_by_user_id')
    op.drop_column('users', 'terminated_at')
