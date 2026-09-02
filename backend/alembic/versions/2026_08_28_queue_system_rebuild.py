import logging
"""Complete message queue system rebuild with channel-based architecture

Revision ID: 2026_08_28_queue_system_rebuild
Revises: 2026_08_27_message_queue
Create Date: 2026-08-28 00:00:00.000000

Changes:
1. Add queue_type field to message_queue (THUNDER, EMAIL, WHATSAPP, SMS, SLACK, etc.)
2. Update status flow: PENDING → SLM_PROCESSING → CHANNEL_QUEUED → COMPLETED/FAILED
3. Add slm_decision_id reference to message_queue
4. Create channel_queue_item table for specific channel processing
5. Create channel_queue_log table for audit trail of channel processing
"""
from alembic import op
import sqlalchemy as sa


revision = '2026_08_28_queue_system_rebuild'
down_revision = '2026_08_27_message_queue'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add queue_type to message_queue (PRIMARY queue type, e.g., THUNDER, TIMESHEET)
    op.add_column(
        'message_queue',
        sa.Column('queue_type', sa.String(100), nullable=True, index=True)
    )

    # Add slm_decision_id for linking to SLM decision
    op.add_column(
        'message_queue',
        sa.Column('slm_decision_id', sa.String(36), nullable=True, index=True)
    )

    # Create channel_queue_item table (specific channel processing)
    # Example: THUNDER_QUEUE processes message, creates EMAIL_QUEUE entry
    op.create_table(
        'channel_queue_item',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('message_id', sa.String(36), nullable=False, index=True),  # FK to message_queue
        sa.Column('channel_type', sa.String(100), nullable=False, index=True),  # EMAIL, WHATSAPP, SMS, SLACK, etc.
        sa.Column('status', sa.String(50), nullable=False, index=True),  # PENDING, PROCESSING, COMPLETED, FAILED
        sa.Column('payload', sa.JSON(), nullable=False),  # Channel-specific payload
        sa.Column('recipient', sa.String(200), nullable=True),  # Email, phone, user_id, etc.
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=False), nullable=True, index=True),
        sa.Column('processed_at', sa.DateTime(timezone=False), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=False), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create indexes for efficient channel queue processing
    op.create_index('ix_channel_queue_item_channel_status', 'channel_queue_item', ['channel_type', 'status'])
    op.create_index('ix_channel_queue_item_retry', 'channel_queue_item', ['status', 'next_retry_at'])
    op.create_index('ix_channel_queue_item_message', 'channel_queue_item', ['message_id'])

    # Create channel_queue_log table (audit trail)
    op.create_table(
        'channel_queue_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('channel_item_id', sa.String(36), nullable=False, index=True),  # FK to channel_queue_item
        sa.Column('status', sa.String(50), nullable=False),  # Status at this point
        sa.Column('message', sa.Text(), nullable=True),  # Status message
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=False), server_default=sa.func.now()),
    )

    # Create slm_channel_decision table (SLM's decision on which channels to trigger)
    op.create_table(
        'slm_channel_decision',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('slm_decision_id', sa.String(36), nullable=False, index=True),  # FK to slm_decision
        sa.Column('message_id', sa.String(36), nullable=False, index=True),  # FK to message_queue
        sa.Column('channels_to_trigger', sa.JSON(), nullable=False),  # List of {channel: EMAIL, action: send}
        sa.Column('reasoning', sa.Text(), nullable=True),  # Why these channels?
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop in reverse order
    op.drop_table('slm_channel_decision')
    op.drop_table('channel_queue_log')
    op.drop_index('ix_channel_queue_item_message', table_name='channel_queue_item')
    op.drop_index('ix_channel_queue_item_retry', table_name='channel_queue_item')
    op.drop_index('ix_channel_queue_item_channel_status', table_name='channel_queue_item')
    op.drop_table('channel_queue_item')
    op.drop_column('message_queue', 'slm_decision_id')
    op.drop_column('message_queue', 'queue_type')
