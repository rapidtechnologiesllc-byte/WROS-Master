"""add interview_rehire_reviews (rehire guard, Part 2 of the interview
regrouping + rehire guard priority)

Revision ID: 076eb838c5cc
Revises: d9c2e5b8f1a4
Create Date: 2026-08-05 00:00:00.000000

Same conventions as every other new table this project: Integer
autoincrement PK, String(50) UserID/candidateID/jobID FKs,
Enum(native_enum=False, create_constraint=True) rendered as VARCHAR +
CHECK constraint. No tenant_id column -- attaches to the legacy
interview_panels/interviews/interview_feedback system
(app.models.user), which itself has no tenant_id in this codebase.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '076eb838c5cc'
down_revision: Union[str, Sequence[str], None] = 'd9c2e5b8f1a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'interview_rehire_reviews',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('candidate_id', sa.String(length=50), nullable=False),
        sa.Column('round_name', sa.String(length=50), nullable=False),
        sa.Column('job_id', sa.String(length=50), nullable=True),
        sa.Column('requested_by', sa.String(length=50), nullable=True),
        sa.Column('justification', sa.Text(), nullable=False),
        sa.Column('past_no_hire_panel_ids', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING_HM_APPROVAL'),
        sa.Column('ai_decision', sa.String(length=10), nullable=True),
        sa.Column('ai_reasoning', sa.Text(), nullable=True),
        sa.Column('ai_confidence', sa.Numeric(3, 2), nullable=True),
        sa.Column('decided_by', sa.String(length=50), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('decision_note', sa.Text(), nullable=True),
        sa.Column('resulting_panel_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID']),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.jobID']),
        sa.ForeignKeyConstraint(['requested_by'], ['users.UserID']),
        sa.ForeignKeyConstraint(['decided_by'], ['users.UserID']),
        sa.ForeignKeyConstraint(['resulting_panel_id'], ['interview_panels.id']),
        sa.CheckConstraint(
            "status IN ('PENDING_HM_APPROVAL','AI_CLEARED','APPROVED','REJECTED')",
            name='ck_interview_rehire_reviews_status',
        ),
        sa.CheckConstraint(
            "ai_decision IS NULL OR ai_decision IN ('CLEAR','ESCALATE')",
            name='ck_interview_rehire_reviews_ai_decision',
        ),
    )
    op.create_index(
        op.f('ix_interview_rehire_reviews_candidate_id'), 'interview_rehire_reviews', ['candidate_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_interview_rehire_reviews_candidate_id'), table_name='interview_rehire_reviews')
    op.drop_table('interview_rehire_reviews')
