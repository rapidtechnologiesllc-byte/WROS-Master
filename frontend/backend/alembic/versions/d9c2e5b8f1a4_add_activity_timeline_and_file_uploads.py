"""add activity_timeline and file_uploads tables (S-216/HRMS-0118)

Revision ID: d9c2e5b8f1a4
Revises: b3f8d2a7c4e6
Create Date: 2026-08-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "d9c2e5b8f1a4"
down_revision = "b3f8d2a7c4e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "activity_timeline",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(50), nullable=False),
        sa.Column("actor_type", sa.String(20), nullable=False, server_default="USER"),
        sa.Column("actor_id", sa.String(50), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_activity_timeline_tenant_id"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.UserID"], name="fk_activity_timeline_actor_id"),
    )
    op.create_index("ix_activity_timeline_tenant_id", "activity_timeline", ["tenant_id"])
    op.create_index("ix_activity_timeline_entity_type", "activity_timeline", ["entity_type"])
    op.create_index("ix_activity_timeline_entity_id", "activity_timeline", ["entity_id"])
    op.create_index("ix_activity_timeline_created_at", "activity_timeline", ["created_at"])

    op.create_table(
        "file_uploads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(50), nullable=False),
        sa.Column("file_category", sa.String(50), nullable=False, server_default="GENERIC"),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("unique_filename", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_extension", sa.String(20), nullable=True),
        sa.Column("sharepoint_url", sa.String(1000), nullable=True),
        sa.Column("scan_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("uploaded_by", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_file_uploads_tenant_id"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.UserID"], name="fk_file_uploads_uploaded_by"),
    )
    op.create_index("ix_file_uploads_tenant_id", "file_uploads", ["tenant_id"])
    op.create_index("ix_file_uploads_entity_type", "file_uploads", ["entity_type"])
    op.create_index("ix_file_uploads_entity_id", "file_uploads", ["entity_id"])


def downgrade():
    op.drop_index("ix_file_uploads_entity_id", table_name="file_uploads")
    op.drop_index("ix_file_uploads_entity_type", table_name="file_uploads")
    op.drop_index("ix_file_uploads_tenant_id", table_name="file_uploads")
    op.drop_table("file_uploads")

    op.drop_index("ix_activity_timeline_created_at", table_name="activity_timeline")
    op.drop_index("ix_activity_timeline_entity_id", table_name="activity_timeline")
    op.drop_index("ix_activity_timeline_entity_type", table_name="activity_timeline")
    op.drop_index("ix_activity_timeline_tenant_id", table_name="activity_timeline")
    op.drop_table("activity_timeline")
