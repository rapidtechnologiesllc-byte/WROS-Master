"""
Migration: Create SLM Decision table for accountability & business impact tracking

Creates table to store every SLM decision with:
- Pre-flight analysis (Place 1): What SLM recommended before handler
- Post-flight outcome (Place 2): What actually happened after handler
- Business impact: Candidate affected, cost impact, 90-day validation plan
- Accountability: Who decided, can it be reversed, audit trail

Revision ID: slm_decision_table
Revises: (Applies after all current migrations)
Create Date: 2026-09-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'slm_decision_table'
down_revision = '2_add_clients'  # Follows the latest applied migration
branch_labels = None
depends_on = None


def upgrade():
    """Create slm_decisions table."""
    op.create_table(
        'slm_decisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_type', sa.String(100), nullable=False),

        # Pre-flight analysis (PLACE 1)
        sa.Column('slm_analysis', sa.JSON, nullable=True),
        sa.Column('slm_decision_id_precheck', sa.String(255), nullable=True),

        # Handler execution
        sa.Column('handler_name', sa.String(255), nullable=False),
        sa.Column('handler_duration_ms', sa.Integer, nullable=True),

        # Post-flight outcome (PLACE 2)
        sa.Column('handler_result', sa.JSON, nullable=True),
        sa.Column('handler_status', sa.String(50), nullable=True),

        # Business impact & accountability
        sa.Column('business_impact', sa.JSON, nullable=True),
        sa.Column('validation_plan', sa.JSON, nullable=True),
        sa.Column('accountability', sa.JSON, nullable=True),

        # Confidence & escalation
        sa.Column('slm_confidence', sa.Float, nullable=True),
        sa.Column('risk_level', sa.String(50), nullable=True),
        sa.Column('was_escalated', sa.Boolean, default=False),
        sa.Column('escalation_reason', sa.String(500), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('analysis_at', sa.DateTime, nullable=True),
        sa.Column('handler_started_at', sa.DateTime, nullable=True),
        sa.Column('handler_completed_at', sa.DateTime, nullable=True),
        sa.Column('outcome_recorded_at', sa.DateTime, nullable=True),
        sa.Column('validated_at', sa.DateTime, nullable=True),

        # Indexes for queries
        sa.Index('idx_slm_decisions_message_id', 'message_id'),
        sa.Index('idx_slm_decisions_message_type', 'message_type'),
        sa.Index('idx_slm_decisions_was_escalated', 'was_escalated'),
        sa.Index('idx_slm_decisions_created_at', 'created_at'),
    )

    # Create index for FK to channel_queue_items
    op.create_index(
        'idx_slm_decisions_message_id_fk',
        'slm_decisions',
        ['message_id'],
        unique=False
    )


def downgrade():
    """Drop slm_decisions table."""
    op.drop_index('idx_slm_decisions_created_at')
    op.drop_index('idx_slm_decisions_was_escalated')
    op.drop_index('idx_slm_decisions_message_type')
    op.drop_index('idx_slm_decisions_message_id_fk')
    op.drop_index('idx_slm_decisions_message_id')
    op.drop_table('slm_decisions')
