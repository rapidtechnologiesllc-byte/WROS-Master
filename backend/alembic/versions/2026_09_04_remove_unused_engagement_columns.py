"""Remove unused engagement phase columns from candidate_conversations.

Revision ID: 2026_09_04_remove_engagement
Revises: 2026_09_04_engagement_phase
Create Date: 2026-09-04 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2026_09_04_remove_engagement'
down_revision = '2026_09_04_engagement_phase'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove Thunder redesign columns that are commented out in the ORM model."""

    # Drop indexes first (may not exist if previous migration didn't run)
    try:
        op.drop_index('ix_candidate_conversations_next_touch_scheduled', table_name='candidate_conversations')
    except Exception:
        pass  # Intentional: Index may not exist if migration was never run

    try:
        op.drop_index('ix_candidate_conversations_engagement_phase', table_name='candidate_conversations')
    except Exception:
        pass  # Intentional: Index may not exist if migration was never run

    # Drop columns in reverse order (they won't exist if the previous migration never ran)
    try:
        op.drop_column('candidate_conversations', 'cycle_count')
    except Exception:
        pass  # Intentional: Column may not exist if migration was never run

    try:
        op.drop_column('candidate_conversations', 'days_since_last_response')
    except Exception:
        pass  # Intentional: Column may not exist if migration was never run

    try:
        op.drop_column('candidate_conversations', 'behavioral_signals')
    except Exception:
        pass  # Intentional: Column may not exist if migration was never run

    try:
        op.drop_column('candidate_conversations', 'response_count')
    except Exception:
        pass  # Intentional: Column may not exist if migration was never run

    try:
        op.drop_column('candidate_conversations', 'candidate_responded_at')
    except Exception:
        pass  # Intentional: Column may not exist if migration was never run

    try:
        op.drop_column('candidate_conversations', 'last_touch_sent_at')
    except Exception:
        pass  # Intentional: Column may not exist if migration was never run

    try:
        op.drop_column('candidate_conversations', 'knowledge_level')
    except Exception:
        pass  # Intentional: Column may not exist if migration was never run

    try:
        op.drop_column('candidate_conversations', 'engagement_phase')
    except Exception:
        pass  # Intentional: Column may not exist if migration was never run


def downgrade() -> None:
    """Restore Thunder redesign columns (for rollback)."""

    op.add_column('candidate_conversations', sa.Column(
        'engagement_phase',
        sa.String(50),
        nullable=False,
        server_default='OUTREACH',
    ))

    op.add_column('candidate_conversations', sa.Column(
        'knowledge_level',
        sa.String(50),
        nullable=False,
        server_default='COLD',
    ))

    op.add_column('candidate_conversations', sa.Column(
        'last_touch_sent_at',
        sa.DateTime(timezone=False),
        nullable=True,
    ))

    op.add_column('candidate_conversations', sa.Column(
        'candidate_responded_at',
        sa.DateTime(timezone=False),
        nullable=True,
    ))

    op.add_column('candidate_conversations', sa.Column(
        'response_count',
        sa.Integer,
        nullable=False,
        server_default='0',
    ))

    op.add_column('candidate_conversations', sa.Column(
        'behavioral_signals',
        sa.JSON,
        nullable=True,
        server_default='{}',
    ))

    op.add_column('candidate_conversations', sa.Column(
        'days_since_last_response',
        sa.Integer,
        nullable=True,
    ))

    op.add_column('candidate_conversations', sa.Column(
        'cycle_count',
        sa.Integer,
        nullable=False,
        server_default='0',
    ))

    op.create_index(
        'ix_candidate_conversations_engagement_phase',
        'candidate_conversations',
        ['engagement_phase'],
    )

    op.create_index(
        'ix_candidate_conversations_next_touch_scheduled',
        'candidate_conversations',
        ['next_touch_scheduled_at'],
    )
