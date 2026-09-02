import logging
"""Add message queue infrastructure tables (message_queue, message_log, slm_decision)

Revision ID: 2026_08_27_message_queue
Revises: f8a9b0c1d2e3
Create Date: 2026-08-27 00:00:00.000000

Implements:
- message_queue: Core queue for all operations (candidate add, Thunder email, Flash action)
- message_log: Audit trail of message processing
- slm_decision: Small Language Model decisions after message processing
"""
from alembic import op
import sqlalchemy as sa


revision = '2026_08_27_message_queue'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create message_queue table
    op.create_table(
        'message_queue',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('type', sa.String(100), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, index=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('resource_id', sa.String(36), nullable=True, index=True),
        sa.Column('created_by', sa.String(50), nullable=False),
        sa.Column('next_retry_at', sa.DateTime(timezone=False), nullable=True, index=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=False), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create composite index for processing (status and next_retry_at)
    op.create_index('ix_message_queue_status_retry', 'message_queue', ['status', 'next_retry_at'])

    # Create composite index for history (type and resource_id)
    op.create_index('ix_message_queue_type_resource', 'message_queue', ['type', 'resource_id'])

    # Create index for created_at DESC (recent messages first)
    op.create_index('ix_message_queue_created_at', 'message_queue', ['created_at'])

    # Create message_log table (audit trail)
    op.create_table(
        'message_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('message_id', sa.String(36), sa.ForeignKey('message_queue.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=False), server_default=sa.func.now()),
    )

    # Create slm_decision table (Small Language Model decisions)
    op.create_table(
        'slm_decision',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('message_id', sa.String(36), sa.ForeignKey('message_queue.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('decision_type', sa.String(100), nullable=False),
        sa.Column('decision_details', sa.JSON(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('next_action', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.func.now()),
    )


def downgrade() -> None:
    # Drop slm_decision table
    op.drop_table('slm_decision')

    # Drop message_log table
    op.drop_table('message_log')

    # Drop message_queue table
    op.drop_index('ix_message_queue_created_at', table_name='message_queue')
    op.drop_index('ix_message_queue_type_resource', table_name='message_queue')
    op.drop_index('ix_message_queue_status_retry', table_name='message_queue')
    op.drop_table('message_queue')
