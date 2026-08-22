"""Remove recruiter assignment fields from CareerApplication

Revision ID: b9f1a3c5d7e9
Revises: e7a1c3f9b2d6
Create Date: 2026-08-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9f1a3c5d7e9'
down_revision = 'e7a1c3f9b2d6'
branch_labels = None
depends_on = None


def upgrade():
    # Remove recruiter assignment fields from career_applications table
    op.drop_column('career_applications', 'assigned_recruiter_id')
    op.drop_column('career_applications', 'assigned_recruiter_name')
    op.drop_column('career_applications', 'assigned_at')


def downgrade():
    # Re-add recruiter assignment fields if downgrading
    op.add_column('career_applications',
        sa.Column('assigned_recruiter_id', sa.String(36), nullable=True, index=True)
    )
    op.add_column('career_applications',
        sa.Column('assigned_recruiter_name', sa.String(200), nullable=True)
    )
    op.add_column('career_applications',
        sa.Column('assigned_at', sa.DateTime(), nullable=True)
    )
