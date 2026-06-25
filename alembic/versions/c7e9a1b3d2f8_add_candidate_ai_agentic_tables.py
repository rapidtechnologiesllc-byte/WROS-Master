"""add_candidate_ai_agentic_tables

Adds three tables to support the agentic automated hiring process:
  - candidate_conversations   : AI-driven conversation thread per candidate
  - candidate_ai_assignments  : Tracks which AI agent is assigned to a candidate
  - conversation_events       : Immutable event log per conversation

Revision ID: c7e9a1b3d2f8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-24 09:04:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c7e9a1b3d2f8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — create AI agentic hiring tables."""

    # ------------------------------------------------------------------
    # 1. candidate_ai_assignments
    # ------------------------------------------------------------------
    op.create_table(
        'candidate_ai_assignments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=50), nullable=False),
        sa.Column('candidate_id', sa.String(length=50), nullable=False),
        sa.Column('ai_agent_name', sa.String(length=100), nullable=False),
        sa.Column('ai_agent_persona', sa.String(length=100), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('assigned_by', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False),
        sa.ForeignKeyConstraint(['assigned_by'],  ['users.UserID'],              ondelete='NO ACTION'),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID'],    ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'],    ['users.UserID'],              ondelete='NO ACTION'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_candidate_ai_assignments_id'),           'candidate_ai_assignments', ['id'],           unique=False)
    op.create_index(op.f('ix_candidate_ai_assignments_tenant_id'),    'candidate_ai_assignments', ['tenant_id'],    unique=False)
    op.create_index(op.f('ix_candidate_ai_assignments_candidate_id'), 'candidate_ai_assignments', ['candidate_id'], unique=False)

    # ------------------------------------------------------------------
    # 2. candidate_conversations
    # ------------------------------------------------------------------
    op.create_table(
        'candidate_conversations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.String(length=50), nullable=False),
        sa.Column('candidate_id', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='open', nullable=False),
        sa.Column('ai_agent_name', sa.String(length=100), nullable=True),
        sa.Column('channel_preference', sa.String(length=50), server_default='email', nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('next_action', sa.String(length=200), nullable=True),
        sa.Column('owner_type', sa.String(length=50), server_default='ai_agent', nullable=True),
        sa.Column('owner_id', sa.String(length=100), nullable=True),
        sa.Column('escalation_state', sa.String(length=50), server_default='none', nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'],    ['users.UserID'],           ondelete='NO ACTION'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_candidate_conversations_id'),           'candidate_conversations', ['id'],           unique=False)
    op.create_index(op.f('ix_candidate_conversations_tenant_id'),    'candidate_conversations', ['tenant_id'],    unique=False)
    op.create_index(op.f('ix_candidate_conversations_candidate_id'), 'candidate_conversations', ['candidate_id'], unique=False)

    # ------------------------------------------------------------------
    # 3. conversation_events
    # ------------------------------------------------------------------
    op.create_table(
        'conversation_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('triggered_by', sa.String(length=50), server_default='ai_agent', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['candidate_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_conversation_events_id'),              'conversation_events', ['id'],              unique=False)
    op.create_index(op.f('ix_conversation_events_conversation_id'), 'conversation_events', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_conversation_events_event_type'),      'conversation_events', ['event_type'],      unique=False)


def downgrade() -> None:
    """Downgrade schema — drop AI agentic hiring tables."""
    # Drop in reverse dependency order
    op.drop_index(op.f('ix_conversation_events_event_type'),       table_name='conversation_events')
    op.drop_index(op.f('ix_conversation_events_conversation_id'),  table_name='conversation_events')
    op.drop_index(op.f('ix_conversation_events_id'),               table_name='conversation_events')
    op.drop_table('conversation_events')

    op.drop_index(op.f('ix_candidate_conversations_candidate_id'), table_name='candidate_conversations')
    op.drop_index(op.f('ix_candidate_conversations_tenant_id'),    table_name='candidate_conversations')
    op.drop_index(op.f('ix_candidate_conversations_id'),           table_name='candidate_conversations')
    op.drop_table('candidate_conversations')

    op.drop_index(op.f('ix_candidate_ai_assignments_candidate_id'), table_name='candidate_ai_assignments')
    op.drop_index(op.f('ix_candidate_ai_assignments_tenant_id'),    table_name='candidate_ai_assignments')
    op.drop_index(op.f('ix_candidate_ai_assignments_id'),           table_name='candidate_ai_assignments')
    op.drop_table('candidate_ai_assignments')
