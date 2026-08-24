"""add users.email_otp_code_hash/email_otp_expires_at (email 2FA, supplements TOTP)

Revision ID: b3d5f7a9c1e4
Revises: f1a3c5e7b9d2
Create Date: 2026-08-05 00:00:00.000000

Backlog item, 2026-08-05 (wros_email_2fa_backlog): "Missing two step
validation via email for employees and internal users" -- supplements
the existing TOTP MFA flow (app.core.mfa), does not replace it. Both
columns nullable, only ever populated at the moment a code is issued;
every existing row is unaffected. See app.core.mfa's EMAIL_OTP_* section
for the real, off-by-default (EMAIL_OTP_ENFORCEMENT_ENABLED) gate this
feeds -- adding these columns changes no existing login behavior.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3d5f7a9c1e4'
down_revision: Union[str, Sequence[str], None] = 'f1a3c5e7b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('email_otp_code_hash', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('email_otp_expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'email_otp_expires_at')
    op.drop_column('users', 'email_otp_code_hash')
