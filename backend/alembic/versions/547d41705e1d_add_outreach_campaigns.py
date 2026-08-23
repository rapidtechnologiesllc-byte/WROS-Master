"""S-044/HRMS-0444: add outreach_campaigns and campaign_touchpoints tables

Revision ID: 547d41705e1d
Revises: f3b6e0e516dd
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "547d41705e1d"
down_revision = "f3b6e0e516dd"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "outreach_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("candidate_conversations.id"), nullable=False),
        sa.Column("campaign_type", sa.String(50), nullable=False, server_default="STANDARD_OUTREACH"),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("stop_reason", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_outreach_campaigns_tenant_id", "outreach_campaigns", ["tenant_id"])
    op.create_index("ix_outreach_campaigns_candidate_id", "outreach_campaigns", ["candidate_id"])
    op.create_index("ix_outreach_campaigns_conversation_id", "outreach_campaigns", ["conversation_id"])
    op.create_index("ix_outreach_campaigns_active_lookup", "outreach_campaigns", ["tenant_id", "candidate_id", "status"])

    op.create_table(
        "campaign_touchpoints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("outreach_campaigns.id"), nullable=False),
        sa.Column("tenant_id", sa.String(50), sa.ForeignKey("users.UserID"), nullable=False),
        sa.Column("candidate_id", sa.String(50), sa.ForeignKey("candidates.candidateID"), nullable=False),
        sa.Column("touchpoint_number", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("message_type", sa.String(50), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("message_event_id", sa.Integer(), sa.ForeignKey("conversation_events.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_campaign_touchpoints_campaign_id", "campaign_touchpoints", ["campaign_id"])
    op.create_index("ix_campaign_touchpoints_tenant_id", "campaign_touchpoints", ["tenant_id"])
    op.create_index("ix_campaign_touchpoints_candidate_id", "campaign_touchpoints", ["candidate_id"])
    op.create_index("ix_campaign_touchpoints_job_queue", "campaign_touchpoints", ["tenant_id", "scheduled_at", "status"])


def downgrade():
    op.drop_index("ix_campaign_touchpoints_job_queue", table_name="campaign_touchpoints")
    op.drop_index("ix_campaign_touchpoints_candidate_id", table_name="campaign_touchpoints")
    op.drop_index("ix_campaign_touchpoints_tenant_id", table_name="campaign_touchpoints")
    op.drop_index("ix_campaign_touchpoints_campaign_id", table_name="campaign_touchpoints")
    op.drop_table("campaign_touchpoints")

    op.drop_index("ix_outreach_campaigns_active_lookup", table_name="outreach_campaigns")
    op.drop_index("ix_outreach_campaigns_conversation_id", table_name="outreach_campaigns")
    op.drop_index("ix_outreach_campaigns_candidate_id", table_name="outreach_campaigns")
    op.drop_index("ix_outreach_campaigns_tenant_id", table_name="outreach_campaigns")
    op.drop_table("outreach_campaigns")
