"""Add clients table for BU -> Client -> Job workflow

Revision ID: 2_add_clients
Revises: 0_init_base
Create Date: 2026-09-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '2_add_clients'
down_revision = '0_init_base'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create clients table"""

    op.create_table(
        'clients',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=512), nullable=False),
        sa.Column('email', sa.String(length=512), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('business_unit_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['business_unit_id'], ['business_units.id']),
        sa.Index('ix_clients_business_unit_id', 'business_unit_id'),
    )


def downgrade() -> None:
    """Drop clients table"""
    op.drop_table('clients')
