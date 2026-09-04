import logging
"""Add business_unit_id to Candidate model for BU cross-referencing

Revision ID: 2026_08_12_candidate_bu
Revises: 2026_08_12_client_owner_opp
Create Date: 2026-08-12 18:00:00.000000

Session work (2026-08-12): Business Unit implementation - cross-reference across all entities.
Auto-populate candidate's BU from job's BU when submitted to job.
"""
from alembic import op
import sqlalchemy as sa

revision = '2026_08_12_candidate_bu'
down_revision = '2026_08_12_client_owner_opp'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('candidates', sa.Column('business_unit_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_candidates_business_unit', 'candidates', 'business_units', ['business_unit_id'], ['id'])
    op.create_index('ix_candidates_business_unit_id', 'candidates', ['business_unit_id'])

def downgrade() -> None:
    op.drop_index('ix_candidates_business_unit_id', table_name='candidates')
    op.drop_constraint('fk_candidates_business_unit', 'candidates', type_='foreignkey')
    op.drop_column('candidates', 'business_unit_id')
