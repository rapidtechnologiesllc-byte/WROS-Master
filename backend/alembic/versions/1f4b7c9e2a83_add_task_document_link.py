import logging
"""add tasks.candidate_id / tasks.document_id (document review linkage)

Revision ID: 1f4b7c9e2a83
Revises: 076eb838c5cc
Create Date: 2026-08-05 00:00:00.000000

2026-08-05 -- Avinash's direct rule: rejecting a candidate document must
reopen (or create) a real Task, approving it closes that Task. Both
columns nullable -- every existing non-document-review Task row is
unaffected.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f4b7c9e2a83'
down_revision: Union[str, Sequence[str], None] = '076eb838c5cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('candidate_id', sa.String(length=50), nullable=True))
    op.add_column('tasks', sa.Column('document_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_tasks_candidate_id'), 'tasks', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_tasks_document_id'), 'tasks', ['document_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tasks_document_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_candidate_id'), table_name='tasks')
    op.drop_column('tasks', 'document_id')
    op.drop_column('tasks', 'candidate_id')
