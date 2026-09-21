"""Add candidate_notice_period column to candidates table

Revision ID: 003
Revises: 002_add_candidate_referral_fields
Create Date: 2026-09-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002_add_candidate_referral_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Add candidate_notice_period column if it doesn't exist
    with op.batch_alter_table('candidates', schema='app_schema') as batch_op:
        batch_op.add_column(sa.Column('candidate_notice_period', sa.Integer(), nullable=True))


def downgrade():
    # Remove candidate_notice_period column
    with op.batch_alter_table('candidates', schema='app_schema') as batch_op:
        batch_op.drop_column('candidate_notice_period')
