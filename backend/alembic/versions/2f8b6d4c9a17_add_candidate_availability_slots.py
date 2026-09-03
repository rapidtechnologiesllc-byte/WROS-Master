import logging
"""S-047/HRMS-0447: add candidate_availability_slots table

Revision ID: 2f8b6d4c9a17
Revises: 9c3a7f1e2b4d
Create Date: 2026-08-02
"""
from alembic import op
import sqlalchemy as sa

revision = "2f8b6d4c9a17"
down_revision = "9c3a7f1e2b4d"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "candidate_availability_slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("candidate_conversations.id"), nullable=False),
        sa.Column("slot_date", sa.Date(), nullable=False),
        sa.Column("slot_start_time", sa.Time(), nullable=False),
        sa.Column("slot_end_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("slot_source", sa.String(20), nullable=False, server_default="CANDIDATE_MESSAGE"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_candidate_availability_slots_tenant_id", "candidate_availability_slots", ["tenant_id"])
    op.create_index("ix_candidate_availability_slots_candidate_id", "candidate_availability_slots", ["candidate_id"])
    op.create_index("ix_candidate_availability_slots_conversation_id", "candidate_availability_slots", ["conversation_id"])
    op.create_index("ix_candidate_availability_slots_candidate_date", "candidate_availability_slots", ["candidate_id", "slot_date"])

def downgrade():
    op.drop_index("ix_candidate_availability_slots_candidate_date", table_name="candidate_availability_slots")
    op.drop_index("ix_candidate_availability_slots_conversation_id", table_name="candidate_availability_slots")
    op.drop_index("ix_candidate_availability_slots_candidate_id", table_name="candidate_availability_slots")
    op.drop_index("ix_candidate_availability_slots_tenant_id", table_name="candidate_availability_slots")
    op.drop_table("candidate_availability_slots")
