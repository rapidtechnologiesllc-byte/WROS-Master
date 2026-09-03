import logging
"""S-065/HRMS-0465: add users.digest_enabled

Revision ID: 5e91c3d4a8f7
Revises: 3c8f1a94d726
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "5e91c3d4a8f7"
down_revision = "3c8f1a94d726"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("digest_enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")))

def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("digest_enabled")
