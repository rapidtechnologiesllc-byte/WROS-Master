"""Add comprehensive message queue system for operation tracking

Revision ID: 2026_08_27_message_queue
Revises: f8a9b0c1d2e3
Create Date: 2026-08-27 00:00:00.000000

This migration adds:
1. message_queue table - Central message queue for all system operations
2. message_queue_log table - Audit trail for each message processing attempt
3. Indexes for efficient query performance
4. Status tracking: PENDING, PROCESSING, COMPLETED, FAILED, RETRYING
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2026_08_27_message_queue'
down_revision: Union[str, Sequence[str], None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Create message_queue table
    op.create_table(
        'message_queue',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='PENDING'),
        sa.Column('resource_id', sa.String(100), nullable=True),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_started_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create indexes for message_queue
    op.create_index('ix_message_queue_status_retry', 'message_queue', ['status', 'next_retry_at'])
    op.create_index('ix_message_queue_created_at', 'message_queue', ['created_at'])
    op.create_index('ix_message_queue_type_resource', 'message_queue', ['type', 'resource_id'])
    op.create_index('ix_message_queue_tenant_status', 'message_queue', ['tenant_id', 'status'])
    op.create_index('ix_message_queue_created_by', 'message_queue', ['created_by'])

    # Create message_queue_log table (audit trail)
    op.create_table(
        'message_queue_log',
        sa.Column('id', sa.String(36), nullable=False, primary_key=True),
        sa.Column('message_id', sa.String(36), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('retry_attempt', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['message_queue.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create indexes for message_queue_log
    op.create_index('ix_message_queue_log_message_id', 'message_queue_log', ['message_id'])
    op.create_index('ix_message_queue_log_timestamp', 'message_queue_log', ['timestamp'])
    op.create_index('ix_message_queue_log_status', 'message_queue_log', ['status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_message_queue_log_status')
    op.drop_index('ix_message_queue_log_timestamp')
    op.drop_index('ix_message_queue_log_message_id')
    op.drop_table('message_queue_log')

    op.drop_index('ix_message_queue_created_by')
    op.drop_index('ix_message_queue_tenant_status')
    op.drop_index('ix_message_queue_type_resource')
    op.drop_index('ix_message_queue_created_at')
    op.drop_index('ix_message_queue_status_retry')
    op.drop_table('message_queue')
