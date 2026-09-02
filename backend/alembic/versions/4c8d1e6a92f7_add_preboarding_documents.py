import logging
"""S-057/HRMS-0457: add preboarding_documents table

Revision ID: 4c8d1e6a92f7
Revises: 9b4e7a1f6d23
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

revision = "4c8d1e6a92f7"
down_revision = "9b4e7a1f6d23"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "preboarding_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("offer_id", sa.Integer(), sa.ForeignKey("offer_letters.id"), nullable=False),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column("document_label", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("document_url", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("reminder_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reminded_at", sa.DateTime(), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "candidate_id", "offer_id", "document_type", name="uq_preboarding_document"),
    )
    op.create_index("ix_preboarding_documents_tenant_id", "preboarding_documents", ["tenant_id"])
    op.create_index("ix_preboarding_documents_candidate_id", "preboarding_documents", ["candidate_id"])
    op.create_index("ix_preboarding_documents_offer_id", "preboarding_documents", ["offer_id"])
    op.create_index("ix_preboarding_documents_job_queue", "preboarding_documents", ["status", "last_reminded_at"])


def downgrade():
    op.drop_index("ix_preboarding_documents_job_queue", table_name="preboarding_documents")
    op.drop_index("ix_preboarding_documents_offer_id", table_name="preboarding_documents")
    op.drop_index("ix_preboarding_documents_candidate_id", table_name="preboarding_documents")
    op.drop_index("ix_preboarding_documents_tenant_id", table_name="preboarding_documents")
    op.drop_table("preboarding_documents")
