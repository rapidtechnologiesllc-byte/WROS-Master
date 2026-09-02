import logging
"""Add business_unit_id to Opportunity model for BU cross-referencing

Revision ID: 2026_08_12_opportunity_bu
Revises: 2026_08_12_candidate_bu
Create Date: 2026-08-12 18:05:00.000000

Session work (2026-08-12): Business Unit implementation - cross-reference across all entities.
Auto-populate opportunity's BU from client's BU.
"""
from alembic import op
import sqlalchemy as sa


revision = '2026_08_12_opportunity_bu'
down_revision = '2026_08_12_candidate_bu'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('opportunities', sa.Column('business_unit_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_opportunities_business_unit', 'opportunities', 'business_units', ['business_unit_id'], ['id'])
    op.create_index('ix_opportunities_business_unit_id', 'opportunities', ['business_unit_id'])


def downgrade() -> None:
    op.drop_index('ix_opportunities_business_unit_id', table_name='opportunities')
    op.drop_constraint('fk_opportunities_business_unit', 'opportunities', type_='foreignkey')
    op.drop_column('opportunities', 'business_unit_id')
