"""Add engagement_phase and Thunder redesign columns to candidate_conversations.

Revision ID: 2026_09_04_engagement_phase
Revises: f1a2b3c4d5e6_add_conversation_audit_log
Create Date: 2026-09-04 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2026_09_04_engagement_phase'
down_revision = 'f1a2b3c4d5e6_add_conversation_audit_log'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add Thunder redesign columns for engagement lifecycle tracking."""

    # engagement_phase: OUTREACH | CONVERSION | DORMANT | HIRED
    op.add_column('candidate_conversations', sa.Column(
        'engagement_phase',
        sa.String(50),
        nullable=False,
        server_default='OUTREACH',
        comment='Current engagement phase: OUTREACH | CONVERSION | DORMANT | HIRED'
    ))

    # knowledge_level: COLD | WARM | HOT
    op.add_column('candidate_conversations', sa.Column(
        'knowledge_level',
        sa.String(50),
        nullable=False,
        server_default='COLD',
        comment='Knowledge level based on behavioral signals: COLD | WARM | HOT'
    ))

    # When last message was sent
    op.add_column('candidate_conversations', sa.Column(
        'last_touch_sent_at',
        sa.DateTime(timezone=False),
        nullable=True,
        comment='When last message was sent (Day 0, 2-3, 5-7, 8-13, 14+)'
    ))

    # When next message should be sent (scheduled)
    op.add_column('candidate_conversations', sa.Column(
        'next_touch_scheduled_at',
        sa.DateTime(timezone=False),
        nullable=True,
        comment='When next message should be sent (scheduled for future execution)'
    ))

    # When candidate first responded to any message
    op.add_column('candidate_conversations', sa.Column(
        'candidate_responded_at',
        sa.DateTime(timezone=False),
        nullable=True,
        comment='When candidate first responded to any message'
    ))

    # Total number of engagement responses
    op.add_column('candidate_conversations', sa.Column(
        'response_count',
        sa.Integer,
        nullable=False,
        server_default='0',
        comment='Total number of times candidate has engaged (replied, clicked, opened)'
    ))

    # JSON tracking of behavioral signals
    op.add_column('candidate_conversations', sa.Column(
        'behavioral_signals',
        sa.JSON,
        nullable=True,
        server_default='{}',
        comment='JSON tracking of behavioral signals: { opened_email: bool, clicked_link: bool, replied: bool, ... }'
    ))

    # Days since last response
    op.add_column('candidate_conversations', sa.Column(
        'days_since_last_response',
        sa.Integer,
        nullable=True,
        comment='Days since candidate last response (auto-calculated, updated daily)'
    ))

    # Cycle count: number of 14-day cycles completed
    op.add_column('candidate_conversations', sa.Column(
        'cycle_count',
        sa.Integer,
        nullable=False,
        server_default='0',
        comment='How many 14-day cycles have completed (0 = first cycle, 1 = second, etc.)'
    ))

    # Create index on engagement_phase for efficient filtering
    op.create_index(
        'ix_candidate_conversations_engagement_phase',
        'candidate_conversations',
        ['engagement_phase'],
        comment='Index for efficient engagement phase filtering'
    )

    # Create index on next_touch_scheduled_at for scheduling queries
    op.create_index(
        'ix_candidate_conversations_next_touch_scheduled',
        'candidate_conversations',
        ['next_touch_scheduled_at'],
        comment='Index for efficient "get next candidates to touch" queries'
    )


def downgrade() -> None:
    """Remove Thunder redesign columns from candidate_conversations."""

    # Drop indexes
    op.drop_index('ix_candidate_conversations_next_touch_scheduled', table_name='candidate_conversations')
    op.drop_index('ix_candidate_conversations_engagement_phase', table_name='candidate_conversations')

    # Drop columns in reverse order
    op.drop_column('candidate_conversations', 'cycle_count')
    op.drop_column('candidate_conversations', 'days_since_last_response')
    op.drop_column('candidate_conversations', 'behavioral_signals')
    op.drop_column('candidate_conversations', 'response_count')
    op.drop_column('candidate_conversations', 'candidate_responded_at')
    op.drop_column('candidate_conversations', 'next_touch_scheduled_at')
    op.drop_column('candidate_conversations', 'last_touch_sent_at')
    op.drop_column('candidate_conversations', 'knowledge_level')
    op.drop_column('candidate_conversations', 'engagement_phase')
