"""add clients.business_unit_id (EPIC-02/03 partner/BU ownership)

Revision ID: e1a3c5f7b9d2
Revises: d8f2b4a6c9e1
Create Date: 2026-08-05 00:00:00.000000

EPIC-02/03 access spec, 2026-08-05. Avinash: "a partner has it's own
clients and the work is done in their BU only... any business he
generates should go only to that BU." Nullable -- every existing
client row is unaffected (visible to everyone until a partner/BU is
assigned, same Org-Pool-until-claimed posture as CandidateOwnership).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1a3c5f7b9d2'
down_revision: Union[str, Sequence[str], None] = 'd8f2b4a6c9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('clients', sa.Column('business_unit_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_clients_business_unit_id'), 'clients', ['business_unit_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_clients_business_unit_id'), table_name='clients')
    op.drop_column('clients', 'business_unit_id')
