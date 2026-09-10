"""
CYCLE 19 Queue Columns Migration (2026-09-10)

Adds missing columns that queue_processor_service.py expects but database doesn't have.
Without these columns, first queued message will crash with AttributeError.

Columns added:
- handler_duration_ms: How long handler took (for SLM learning)
- last_attempted_at: When this message was last processed (for retry tracking)
- scheduled_for: When message should be processed (for delayed scheduling)
- idempotency_key: For deduplication (prevent double-processing)
"""
from alembic import op
import sqlalchemy as sa


revision = '20260910_001'
down_revision = None  # Set to previous migration if one exists
branch_labels = None
depends_on = None


def upgrade():
    """Add CYCLE 19 queue columns"""
    # Add handler_duration_ms column
    try:
        op.add_column(
            'channel_queue',
            sa.Column('handler_duration_ms', sa.Integer, nullable=True, default=0)
        )
    except Exception as e:
        # Column might already exist
        pass

    # Add last_attempted_at column
    try:
        op.add_column(
            'channel_queue',
            sa.Column('last_attempted_at', sa.DateTime, nullable=True)
        )
    except Exception as e:
        # Column might already exist
        pass

    # Add scheduled_for column
    try:
        op.add_column(
            'channel_queue',
            sa.Column('scheduled_for', sa.DateTime, nullable=True)
        )
    except Exception as e:
        # Column might already exist
        pass

    # Add idempotency_key column
    try:
        op.add_column(
            'channel_queue',
            sa.Column('idempotency_key', sa.String(256), nullable=True, unique=False)
        )
    except Exception as e:
        # Column might already exist
        pass

    # Create index on idempotency_key for fast lookups
    try:
        op.create_index(
            'ix_channel_queue_idempotency_key',
            'channel_queue',
            ['idempotency_key'],
            unique=False
        )
    except Exception as e:
        # Index might already exist
        pass

    # Create index on scheduled_for for querying pending scheduled messages
    try:
        op.create_index(
            'ix_channel_queue_scheduled_for',
            'channel_queue',
            ['scheduled_for'],
            unique=False
        )
    except Exception as e:
        # Index might already exist
        pass


def downgrade():
    """Remove CYCLE 19 queue columns"""
    try:
        op.drop_index('ix_channel_queue_scheduled_for', table_name='channel_queue')
    except Exception:
        pass

    try:
        op.drop_index('ix_channel_queue_idempotency_key', table_name='channel_queue')
    except Exception:
        pass

    try:
        op.drop_column('channel_queue', 'idempotency_key')
    except Exception:
        pass

    try:
        op.drop_column('channel_queue', 'scheduled_for')
    except Exception:
        pass

    try:
        op.drop_column('channel_queue', 'last_attempted_at')
    except Exception:
        pass

    try:
        op.drop_column('channel_queue', 'handler_duration_ms')
    except Exception:
        pass
