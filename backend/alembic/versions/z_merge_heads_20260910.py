"""Merge migration heads to consolidate branches"""
from alembic import op
import sqlalchemy as sa

revision = 'z_merge_heads_20260910'
down_revision = ('2026_09_09_001', '2_add_clients', 'add_soft_delete_001')
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
