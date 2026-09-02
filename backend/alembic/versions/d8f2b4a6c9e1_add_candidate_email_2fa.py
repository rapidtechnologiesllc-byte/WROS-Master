import logging
"""add candidates.email_2fa_opted_in/email_otp_code_hash/email_otp_expires_at (candidate email 2FA opt-in)

Revision ID: d8f2b4a6c9e1
Revises: c5e7a9b1d3f6
Create Date: 2026-08-05 00:00:00.000000

Backlog item, 2026-08-05 (wros_email_2fa_backlog, candidate half).
email_2fa_opted_in is tri-state (NULL = never asked, True = opted in,
False = declined) -- see the model's own column comment. All three
columns nullable; every existing row is unaffected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8f2b4a6c9e1'
down_revision: Union[str, Sequence[str], None] = 'c5e7a9b1d3f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('candidates', sa.Column('email_2fa_opted_in', sa.Boolean(), nullable=True))
    op.add_column('candidates', sa.Column('email_otp_code_hash', sa.String(length=64), nullable=True))
    op.add_column('candidates', sa.Column('email_otp_expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('candidates', 'email_otp_expires_at')
    op.drop_column('candidates', 'email_otp_code_hash')
    op.drop_column('candidates', 'email_2fa_opted_in')
