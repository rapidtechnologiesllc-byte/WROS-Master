import logging
"""add tasks.interview_id (feedback-pending vs HM-decision-pending linkage)

Revision ID: a8c3f1e6d9b2
Revises: 5e9f3a7c1d64
Create Date: 2026-08-05 00:00:00.000000

2026-08-05 -- backlog item: distinguish "interviewer hasn't submitted
feedback yet" Tasks from "hiring manager hasn't decided yet" Tasks
without clubbing across a candidate's other rounds/jobs. Nullable --
every existing non-interview Task row is unaffected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a8c3f1e6d9b2'
down_revision: Union[str, Sequence[str], None] = '5e9f3a7c1d64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('interview_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_tasks_interview_id'), 'tasks', ['interview_id'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tasks_interview_id'), table_name='tasks')
    op.drop_column('tasks', 'interview_id')
