import logging
"""S-062/HRMS-0462: add recruiter_intervention_queue table

Revision ID: 3c8f1a94d726
Revises: 9d3b7e1c5a26
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "3c8f1a94d726"
down_revision = "9d3b7e1c5a26"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "recruiter_intervention_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "queue_reason",
            sa.Enum(
                "ESCALATION", "HIGH_DROP_RISK", "CRITICAL_DROP_RISK", "SLA_BREACH",
                "HIGH_ABANDONMENT", "NO_SHOW", "OFFER_COUNTER", "DOCUMENT_OVERDUE",
                name="intervention_queue_reason", native_enum=False, create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("reason_detail", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("OPEN", "IN_PROGRESS", "RESOLVED", name="intervention_queue_status", native_enum=False, create_constraint=True),
            nullable=False, server_default="OPEN",
        ),
        sa.Column("assigned_to_user_id", sa.String(50), sa.ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=True),
        sa.Column("added_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by", sa.String(50), sa.ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_recruiter_intervention_queue_tenant_id", "recruiter_intervention_queue", ["tenant_id"])
    op.create_index("ix_recruiter_intervention_queue_candidate_id", "recruiter_intervention_queue", ["candidate_id"])
    op.create_index(
        "ix_one_open_item_per_candidate_reason", "recruiter_intervention_queue",
        ["tenant_id", "candidate_id", "queue_reason"], unique=True,
        sqlite_where=sa.text("status = 'OPEN'"), mssql_where=sa.text("status = 'OPEN'"),
    )

def downgrade():
    op.drop_index("ix_one_open_item_per_candidate_reason", table_name="recruiter_intervention_queue")
    op.drop_index("ix_recruiter_intervention_queue_candidate_id", table_name="recruiter_intervention_queue")
    op.drop_index("ix_recruiter_intervention_queue_tenant_id", table_name="recruiter_intervention_queue")
    op.drop_table("recruiter_intervention_queue")
