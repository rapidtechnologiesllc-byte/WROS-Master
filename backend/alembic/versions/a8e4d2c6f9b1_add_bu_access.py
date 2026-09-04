import logging
"""add bu_access table (S-205/HRMS-0107)

Revision ID: a8e4d2c6f9b1
Revises: f6a3c9e1b7d2
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "a8e4d2c6f9b1"
down_revision = "f6a3c9e1b7d2"
branch_labels = None
depends_on = None

def upgrade():
    # S-205's own Data Mapping/UI Fields ask for continent/region/is_active
    # on BusinessUnit -- extending the existing table (same "extend, don't
    # fork" convention bu_code/parent_bu_id already used on it) rather
    # than a second business_units table.
    with op.batch_alter_table("business_units") as batch_op:
        batch_op.add_column(sa.Column("continent", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("region", sa.String(60), nullable=True))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"))

    op.create_table(
        "bu_access",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(50), nullable=False),
        sa.Column("business_unit_id", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.UserID"], name="fk_bu_access_user_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_unit_id"], ["business_units.id"], name="fk_bu_access_business_unit_id", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "business_unit_id", name="uq_bu_access_user_bu"),
    )
    op.create_index("ix_bu_access_user_id", "bu_access", ["user_id"])
    op.create_index("ix_bu_access_business_unit_id", "bu_access", ["business_unit_id"])

def downgrade():
    op.drop_index("ix_bu_access_business_unit_id", table_name="bu_access")
    op.drop_index("ix_bu_access_user_id", table_name="bu_access")
    op.drop_table("bu_access")

    with op.batch_alter_table("business_units") as batch_op:
        batch_op.drop_column("is_active")
        batch_op.drop_column("region")
        batch_op.drop_column("continent")
