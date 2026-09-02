import logging
"""add audit_log table

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-20 02:00:00.000000

IMPORTANT -- manual step required after running this migration:
The DENY statement below assumes the application's SQL Server login is
named [onboard_user]. Before running against a real database, replace that
name with whatever login DATABASE_URL actually authenticates as (check
.env on the VPS). Without this step, audit_log is append-only only at
the application/ORM layer (see app/models/audit_log.py's event
listeners), not at the database level HRMS-0110 actually requires --
a direct SQL client would still be able to UPDATE/DELETE rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('audit_log',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=True),
    sa.Column('entity_type', sa.String(length=100), nullable=False),
    sa.Column('entity_id', sa.String(length=100), nullable=False),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('user_id', sa.String(length=50), nullable=True),
    sa.Column('old_value', sa.Text(), nullable=True),
    sa.Column('new_value', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
    )
    op.create_index(op.f('ix_audit_log_id'), 'audit_log', ['id'], unique=False)
    op.create_index(op.f('ix_audit_log_tenant_id'), 'audit_log', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_audit_log_entity_id'), 'audit_log', ['entity_id'], unique=False)
    op.create_index(op.f('ix_audit_log_user_id'), 'audit_log', ['user_id'], unique=False)

    # --- Database-grant-level append-only enforcement (SQL Server) ---
    # MANUAL STEP: confirm/replace 'onboard_user' with the real login name
    # from DATABASE_URL before running this against any real database.
    # This intentionally has no equivalent effect on SQLite -- it's a
    # no-op there, which is fine since local/CI tests only exercise the
    # ORM-level guard in app/models/audit_log.py.
    bind = op.get_bind()
    if bind.dialect.name == "mssql":
        op.execute("DENY UPDATE, DELETE ON audit_log TO [onboard_user];")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "mssql":
        op.execute("REVOKE DENY UPDATE, DELETE ON audit_log FROM [onboard_user];")

    op.drop_index(op.f('ix_audit_log_user_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_entity_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_tenant_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_id'), table_name='audit_log')
    op.drop_table('audit_log')
