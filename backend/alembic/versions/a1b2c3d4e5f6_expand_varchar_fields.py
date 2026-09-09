"""Expand varchar fields for gender, marital_status, nationality from 10 to 100 chars

Revision ID: a1b2c3d4e5f6
Revises: f8a9b0c1d2e3
Create Date: 2026-09-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on = None


def upgrade():
    # Fix candidates.candidateGender varchar(10) -> varchar(100)
    op.alter_column('candidates', 'candidateGender',
                   existing_type=sa.String(10),
                   type_=sa.String(100),
                   existing_nullable=True)

    # Fix candidate_forms fields
    op.alter_column('candidate_forms', 'gender',
                   existing_type=sa.String(10),
                   type_=sa.String(100),
                   existing_nullable=True)

    op.alter_column('candidate_forms', 'marital_status',
                   existing_type=sa.String(10),
                   type_=sa.String(100),
                   existing_nullable=True)

    op.alter_column('candidate_forms', 'nationality',
                   existing_type=sa.String(10),
                   type_=sa.String(100),
                   existing_nullable=True)


def downgrade():
    # Revert back to varchar(10) if needed
    op.alter_column('candidates', 'candidateGender',
                   existing_type=sa.String(100),
                   type_=sa.String(10),
                   existing_nullable=True)

    op.alter_column('candidate_forms', 'gender',
                   existing_type=sa.String(100),
                   type_=sa.String(10),
                   existing_nullable=True)

    op.alter_column('candidate_forms', 'marital_status',
                   existing_type=sa.String(100),
                   type_=sa.String(10),
                   existing_nullable=True)

    op.alter_column('candidate_forms', 'nationality',
                   existing_type=sa.String(100),
                   type_=sa.String(10),
                   existing_nullable=True)
