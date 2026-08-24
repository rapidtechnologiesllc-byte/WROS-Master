"""S-043/HRMS-0443: add candidate_ghosting_status table

Revision ID: f3b6e0e516dd
Revises: 84838a711e64
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "f3b6e0e516dd"
down_revision = "84838a711e64"
branch_labels = None
depends_on = None

_DEFAULT_REASON = "No response after 3 follow-up messages"


def upgrade():
    op.create_table(
        "candidate_ghosting_status",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("candidate_conversations.id"), nullable=False),
        sa.Column("ghosted_at", sa.DateTime(), nullable=False),
        sa.Column("ghosting_reason", sa.String(200), nullable=False, server_default=_DEFAULT_REASON),
        sa.Column("reactivation_scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("is_reactivated", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("reactivated_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "candidate_id", name="uq_candidate_ghosting_status"),
    )
    op.create_index("ix_candidate_ghosting_status_tenant_id", "candidate_ghosting_status", ["tenant_id"])
    op.create_index("ix_candidate_ghosting_status_candidate_id", "candidate_ghosting_status", ["candidate_id"])
    op.create_index("ix_candidate_ghosting_status_conversation_id", "candidate_ghosting_status", ["conversation_id"])


def downgrade():
    op.drop_index("ix_candidate_ghosting_status_conversation_id", table_name="candidate_ghosting_status")
    op.drop_index("ix_candidate_ghosting_status_candidate_id", table_name="candidate_ghosting_status")
    op.drop_index("ix_candidate_ghosting_status_tenant_id", table_name="candidate_ghosting_status")
    op.drop_table("candidate_ghosting_status")
