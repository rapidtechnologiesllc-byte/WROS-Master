"""Message Queue System Rebuild - Channel-based architecture with email tracking

This migration creates the complete message queue infrastructure with:
- Channel-based routing (THUNDER_QUEUE, EMAIL_QUEUE, WHATSAPP_QUEUE, etc.)
- Email tracking fields (opened_at, clicked_at, bounced_at, etc.)
- Message channel junction table for routing to multiple channels
- Email provider tracking (Gmail, Outlook, Yahoo, Apple, SMTP)
- Comprehensive indexing for performance

Revision ID: 2026_08_28_message_queue_rebuild
Revises: 2026_08_27_agent_config
Create Date: 2026-08-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = '2026_08_28_message_queue_rebuild'
down_revision = '2026_08_27_agent_config'
branch_labels = None
depends_on = None


def upgrade():
    """Create or enhance message queue tables for channel-based routing and email tracking."""

    # Check if message_queue table exists and needs enhancement
    connection = op.get_bind()
    inspector = sa.inspect(connection)

    # Add new columns to message_queue if they don't exist
    message_queue_columns = {col.name for col in inspector.get_columns('message_queue')}

    if 'queue_type' not in message_queue_columns:
        op.add_column('message_queue', sa.Column('queue_type', sa.String(50), nullable=True, index=True))

    if 'email_status' not in message_queue_columns:
        op.add_column('message_queue', sa.Column('email_status', sa.String(50), nullable=True))

    if 'opened_at' not in message_queue_columns:
        op.add_column('message_queue', sa.Column('opened_at', sa.DateTime(timezone=False), nullable=True))

    if 'clicked_at' not in message_queue_columns:
        op.add_column('message_queue', sa.Column('clicked_at', sa.DateTime(timezone=False), nullable=True))

    if 'replied_at' not in message_queue_columns:
        op.add_column('message_queue', sa.Column('replied_at', sa.DateTime(timezone=False), nullable=True))

    if 'bounced_at' not in message_queue_columns:
        op.add_column('message_queue', sa.Column('bounced_at', sa.DateTime(timezone=False), nullable=True))

    if 'spam_marked_at' not in message_queue_columns:
        op.add_column('message_queue', sa.Column('spam_marked_at', sa.DateTime(timezone=False), nullable=True))

    if 'deleted_at' not in message_queue_columns:
        op.add_column('message_queue', sa.Column('deleted_at', sa.DateTime(timezone=False), nullable=True))

    if 'email_provider' not in message_queue_columns:
        op.add_column('message_queue', sa.Column('email_provider', sa.String(50), nullable=True))

    if 'last_tracked_at' not in message_queue_columns:
        op.add_column('message_queue', sa.Column('last_tracked_at', sa.DateTime(timezone=False), nullable=True))

    if 'tracking_error' not in message_queue_columns:
        op.add_column('message_queue', sa.Column('tracking_error', sa.Text(), nullable=True))

    # Create message_channels table (junction table for routing to multiple channels)
    if not inspector.has_table('message_channels'):
        op.create_table(
            'message_channels',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('message_id', sa.String(36), sa.ForeignKey('message_queue.id'), nullable=False, index=True),
            sa.Column('queue_type', sa.String(50), nullable=False, index=True),
            sa.Column('status', sa.String(50), nullable=False, default='PENDING'),
            sa.Column('error_details', sa.Text(), nullable=True),
            sa.Column('processed_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
            sa.Index('ix_message_channels_message_queue_type', 'message_id', 'queue_type'),
        )

    # Create email_tracking table (for detailed email engagement tracking)
    if not inspector.has_table('email_tracking'):
        op.create_table(
            'email_tracking',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('message_id', sa.String(36), sa.ForeignKey('message_queue.id'), nullable=False, index=True),
            sa.Column('recipient_email', sa.String(255), nullable=False, index=True),
            sa.Column('provider', sa.String(50), nullable=False),  # gmail, outlook, yahoo, apple, smtp
            sa.Column('message_id_external', sa.String(255), nullable=True),  # External message ID from provider
            sa.Column('thread_id', sa.String(255), nullable=True),  # Gmail thread ID
            sa.Column('status', sa.String(50), nullable=False, default='PENDING'),  # PENDING, SENT, DELIVERED, OPENED, CLICKED, REPLIED, BOUNCED, SPAM, DELETED

            # Engagement timestamps
            sa.Column('sent_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('delivered_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('opened_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('first_click_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('last_click_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('replied_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('bounced_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('spam_marked_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('deleted_at', sa.DateTime(timezone=False), nullable=True),

            # Engagement metrics
            sa.Column('open_count', sa.Integer(), default=0),
            sa.Column('click_count', sa.Integer(), default=0),
            sa.Column('bounce_reason', sa.String(255), nullable=True),

            # Polling state
            sa.Column('last_checked_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('check_count', sa.Integer(), default=0),
            sa.Column('last_error', sa.Text(), nullable=True),

            # Audit
            sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=False), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),

            sa.Index('ix_email_tracking_message_recipient', 'message_id', 'recipient_email'),
            sa.Index('ix_email_tracking_status', 'status'),
            sa.Index('ix_email_tracking_last_checked', 'last_checked_at'),
        )

    # Create email_tracking_events table (for detailed event log)
    if not inspector.has_table('email_tracking_events'):
        op.create_table(
            'email_tracking_events',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('tracking_id', sa.String(36), sa.ForeignKey('email_tracking.id'), nullable=False, index=True),
            sa.Column('event_type', sa.String(50), nullable=False),  # sent, delivered, opened, clicked, replied, bounced, spam, deleted
            sa.Column('event_data', sa.JSON(), nullable=True),  # Additional event details
            sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False),
            sa.Index('ix_email_tracking_events_tracking_type', 'tracking_id', 'event_type'),
        )

    # Create queue_processing_state table (for tracking processing state per queue)
    if not inspector.has_table('queue_processing_state'):
        op.create_table(
            'queue_processing_state',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('queue_type', sa.String(50), nullable=False, unique=True, index=True),
            sa.Column('last_processed_message_id', sa.String(36), nullable=True),
            sa.Column('last_processed_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('is_processing', sa.Boolean(), default=False),
            sa.Column('process_count_total', sa.Integer(), default=0),
            sa.Column('error_count_total', sa.Integer(), default=0),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('last_error_at', sa.DateTime(timezone=False), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=False), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        )

    # Create indexes for performance
    try:
        op.create_index('ix_message_queue_queue_type_status', 'message_queue', ['queue_type', 'status'])
    except:
        pass  # Index might already exist

    try:
        op.create_index('ix_message_queue_email_status_tracking', 'message_queue', ['email_status', 'last_tracked_at'])
    except:
        pass

    try:
        op.create_index('ix_message_queue_created_at_queue_type', 'message_queue', ['created_at', 'queue_type'])
    except:
        pass


def downgrade():
    """Rollback message queue schema changes."""

    # Drop tables
    op.drop_table('queue_processing_state')
    op.drop_table('email_tracking_events')
    op.drop_table('email_tracking')
    op.drop_table('message_channels')

    # Drop columns from message_queue (commented out - safer to keep data)
    # These columns would be dropped if we want full rollback
    # But we keep them for data preservation in production
    pass
