"""add notification engine (HRMS-0113) + users.timezone

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-07-21 00:00:00.000002

HRMS-0113 Notification Engine Base. Adds users.timezone (nullable-
compatible via server_default, since HRMS-0121 -- the story that was
meant to supply per-tenant/per-user locale config -- doesn't exist in
this codebase) and the notifications table itself.

VERIFICATION NOTE: the op.add_column() call and the notifications
op.create_table() (all inline FKs/CHECK constraints) were verified
end-to-end against a throwaway SQLite database and apply cleanly.
Run against a staging SQL Server copy first, not production directly,
same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='Asia/Kolkata'),
    )

    op.create_table(
        'notifications',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('recipient_id', sa.String(length=50), nullable=False),
        sa.Column('channel', sa.String(length=10), nullable=False),
        sa.Column('fallback_channel', sa.String(length=10), nullable=True),
        sa.Column('priority_tier', sa.String(length=5), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('delivery_status', sa.String(length=15), nullable=False),
        sa.Column('scheduled_release_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.UserID']),
        sa.CheckConstraint("channel IN ('IN_APP','EMAIL','WHATSAPP','SMS')", name='ck_notifications_channel'),
        sa.CheckConstraint(
            "fallback_channel IS NULL OR fallback_channel IN ('IN_APP','EMAIL','WHATSAPP','SMS')",
            name='ck_notifications_fallback_channel',
        ),
        sa.CheckConstraint("priority_tier IN ('P0','P1','P2')", name='ck_notifications_priority_tier'),
        sa.CheckConstraint(
            "delivery_status IN ('PENDING','SENT','FALLBACK_SENT','FAILED')",
            name='ck_notifications_delivery_status',
        ),
    )
    op.create_index(op.f('ix_notifications_tenant_id'), 'notifications', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_notifications_recipient_id'), 'notifications', ['recipient_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('notifications')
    op.drop_column('users', 'timezone')
