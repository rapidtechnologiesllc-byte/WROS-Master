import logging
"""add conversation_audit_log (S-076/HRMS-0476)

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-07-23 00:00:00.000000

S-076/HRMS-0476 -- Conversation Audit Log. Insert-only at the application
level (see app.services.audit_log_service) -- no update/delete function
exists for this table anywhere in this codebase.

VERIFICATION NOTE: single op.create_table() plus indexes, verified
end-to-end against a throwaway SQLite database.

FIXED 2026-07-23 (never successfully applied to any real target before this
fix -- caught the first time this environment could actually reach SQL
Server): conversation_id's ondelete was SET NULL, which SQL Server rejects
as a multiple-cascade-path conflict against the direct CASCADE path from
candidate_id -- SQLite's FK enforcement doesn't catch this, so the original
SQLite verification never surfaced it. Changed to NO ACTION.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e0f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'conversation_audit_log',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('tenant_id', sa.String(length=50), nullable=False),
        sa.Column('candidate_id', sa.String(length=50), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('audit_event_type', sa.String(length=100), nullable=False),
        sa.Column('audit_event_description', sa.Text(), nullable=False),
        sa.Column('actor_type', sa.String(length=20), nullable=False),
        sa.Column('actor_id', sa.String(length=100), nullable=False),
        sa.Column('before_state', sa.JSON(), nullable=True),
        sa.Column('after_state', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['users.UserID'], ondelete='NO ACTION'),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['candidate_conversations.id'], ondelete='NO ACTION'),
    )
    op.create_index(op.f('ix_conversation_audit_log_tenant_id'), 'conversation_audit_log', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_conversation_audit_log_candidate_id'), 'conversation_audit_log', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_conversation_audit_log_conversation_id'), 'conversation_audit_log', ['conversation_id'], unique=False)
    op.create_index(
        'ix_conversation_audit_log_tenant_candidate_created',
        'conversation_audit_log', ['tenant_id', 'candidate_id', 'created_at'], unique=False,
    )

def downgrade() -> None:
    op.drop_index('ix_conversation_audit_log_tenant_candidate_created', table_name='conversation_audit_log')
    op.drop_index(op.f('ix_conversation_audit_log_conversation_id'), table_name='conversation_audit_log')
    op.drop_index(op.f('ix_conversation_audit_log_candidate_id'), table_name='conversation_audit_log')
    op.drop_index(op.f('ix_conversation_audit_log_tenant_id'), table_name='conversation_audit_log')
    op.drop_table('conversation_audit_log')
