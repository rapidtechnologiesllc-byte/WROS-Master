"""Add queue_doctor_state table for queue diagnostics

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-08 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'queue_doctor_state',
        sa.Column('id', sa.String(512), nullable=False),
        sa.Column('message_id', sa.String(512), nullable=False),
        sa.Column('message_type', sa.String(100), nullable=False),
        sa.Column('queued_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), default=1),
        sa.Column('max_attempts', sa.Integer(), default=5),
        sa.Column('is_stalled', sa.Boolean(), default=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('candidate_id', sa.String(512), nullable=True),
        sa.Column('workflow_id', sa.String(512), nullable=True),
        sa.Column('healing_attempted', sa.Boolean(), default=False),
        sa.Column('healing_succeeded', sa.Boolean(), nullable=True),
        sa.Column('healing_strategy', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_id'),
    )
    op.create_index('idx_message_id', 'queue_doctor_state', ['message_id'])
    op.create_index('idx_candidate_id', 'queue_doctor_state', ['candidate_id'])
    op.create_index('idx_message_type', 'queue_doctor_state', ['message_type'])
    op.create_index('idx_status', 'queue_doctor_state', ['status'])
    op.create_index('idx_queued_at', 'queue_doctor_state', ['queued_at'])
    op.create_index('idx_is_stalled', 'queue_doctor_state', ['is_stalled'])


def downgrade():
    op.drop_index('idx_is_stalled', table_name='queue_doctor_state')
    op.drop_index('idx_queued_at', table_name='queue_doctor_state')
    op.drop_index('idx_status', table_name='queue_doctor_state')
    op.drop_index('idx_message_type', table_name='queue_doctor_state')
    op.drop_index('idx_candidate_id', table_name='queue_doctor_state')
    op.drop_index('idx_message_id', table_name='queue_doctor_state')
    op.drop_table('queue_doctor_state')
