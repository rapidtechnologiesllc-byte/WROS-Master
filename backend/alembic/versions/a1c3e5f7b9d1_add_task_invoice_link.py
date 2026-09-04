import logging
"""add tasks.invoice_id (EPIC-16 AR follow-up)

Revision ID: a1c3e5f7b9d1
Revises: f6b8d0a2c4e6
Create Date: 2026-08-06 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1c3e5f7b9d1'
down_revision: Union[str, Sequence[str], None] = 'f6b8d0a2c4e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('invoice_id', sa.String(length=36), nullable=True))
    op.create_foreign_key('fk_tasks_invoice_id', 'tasks', 'invoices', ['invoice_id'], ['id'])
    op.create_index(op.f('ix_tasks_invoice_id'), 'tasks', ['invoice_id'], unique=False)

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tasks_invoice_id'), table_name='tasks')
    op.drop_constraint('fk_tasks_invoice_id', 'tasks', type_='foreignkey')
    op.drop_column('tasks', 'invoice_id')
