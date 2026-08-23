"""Add client_owner_id to Opportunity model for auto-population from job

Revision ID: 2026_08_12_client_owner_opp
Revises: 2026_08_12_work_orders
Create Date: 2026-08-12 00:00:00.000000

DEFECT-4: Client Owner field auto-population from job.client_owner
"""
from alembic import op
import sqlalchemy as sa


revision = '2026_08_12_client_owner_opp'
down_revision = '2026_08_12_work_orders'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('opportunities', sa.Column('client_owner_id', sa.String(36), nullable=True))
    op.create_foreign_key('fk_opportunities_client_owner', 'opportunities', 'users', ['client_owner_id'], ['UserID'])
    op.create_index('ix_opportunities_client_owner_id', 'opportunities', ['client_owner_id'])


def downgrade() -> None:
    op.drop_index('ix_opportunities_client_owner_id', table_name='opportunities')
    op.drop_constraint('fk_opportunities_client_owner', 'opportunities', type_='foreignkey')
    op.drop_column('opportunities', 'client_owner_id')
