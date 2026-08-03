"""S-061/HRMS-0461: add activity_feed_read_state table

Revision ID: 9d3b7e1c5a26
Revises: 7f2a9c4e83b1
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "9d3b7e1c5a26"
down_revision = "7f2a9c4e83b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "activity_feed_read_state",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False),
        sa.Column("conversation_event_id", sa.Integer(), sa.ForeignKey("conversation_events.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("read_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("conversation_event_id", name="uq_activity_feed_read_state_event"),
    )
    op.create_index("ix_activity_feed_read_state_tenant_id", "activity_feed_read_state", ["tenant_id"])
    op.create_index("ix_activity_feed_read_state_event_id", "activity_feed_read_state", ["conversation_event_id"])


def downgrade():
    op.drop_index("ix_activity_feed_read_state_event_id", table_name="activity_feed_read_state")
    op.drop_index("ix_activity_feed_read_state_tenant_id", table_name="activity_feed_read_state")
    op.drop_table("activity_feed_read_state")
