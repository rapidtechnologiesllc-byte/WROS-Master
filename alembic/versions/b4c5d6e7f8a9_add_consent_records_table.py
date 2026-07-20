"""add consent_records table

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-07-20 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('consent_records',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=True),
    sa.Column('subject_type', sa.String(length=50), nullable=False),
    sa.Column('subject_id', sa.String(length=50), nullable=False),
    sa.Column('consent_type', sa.String(length=100), nullable=False),
    sa.Column('consent_given', sa.Boolean(), nullable=False),
    sa.Column('captured_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    sa.Column('captured_by', sa.String(length=50), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
    )
    op.create_index(op.f('ix_consent_records_id'), 'consent_records', ['id'], unique=False)
    op.create_index(op.f('ix_consent_records_tenant_id'), 'consent_records', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_consent_records_subject_id'), 'consent_records', ['subject_id'], unique=False)
    op.create_index(op.f('ix_consent_records_consent_type'), 'consent_records', ['consent_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_consent_records_consent_type'), table_name='consent_records')
    op.drop_index(op.f('ix_consent_records_subject_id'), table_name='consent_records')
    op.drop_index(op.f('ix_consent_records_tenant_id'), table_name='consent_records')
    op.drop_index(op.f('ix_consent_records_id'), table_name='consent_records')
    op.drop_table('consent_records')
