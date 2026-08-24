"""S-021/HRMS-0421: add candidate_memory and candidate_memory_facts tables

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "f5a6b7c8d9e0"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "candidate_memory",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False, unique=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_candidate_memory_tenant_id", "candidate_memory", ["tenant_id"])
    op.create_index("ix_candidate_memory_candidate_id", "candidate_memory", ["candidate_id"], unique=True)

    op.create_table(
        "candidate_memory_facts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("fact_category", sa.String(50), nullable=False),
        sa.Column("fact_key", sa.String(100), nullable=False),
        sa.Column("fact_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("source_message_id", sa.Integer(), sa.ForeignKey("conversation_events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("extracted_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
    )
    op.create_index("ix_candidate_memory_facts_tenant_id", "candidate_memory_facts", ["tenant_id"])
    op.create_index("ix_candidate_memory_facts_candidate_id", "candidate_memory_facts", ["candidate_id"])
    op.create_index(
        "ix_candidate_memory_facts_lookup", "candidate_memory_facts",
        ["candidate_id", "tenant_id", "fact_category", "is_active"],
    )


def downgrade():
    op.drop_index("ix_candidate_memory_facts_lookup", table_name="candidate_memory_facts")
    op.drop_index("ix_candidate_memory_facts_candidate_id", table_name="candidate_memory_facts")
    op.drop_index("ix_candidate_memory_facts_tenant_id", table_name="candidate_memory_facts")
    op.drop_table("candidate_memory_facts")

    op.drop_index("ix_candidate_memory_candidate_id", table_name="candidate_memory")
    op.drop_index("ix_candidate_memory_tenant_id", table_name="candidate_memory")
    op.drop_table("candidate_memory")
