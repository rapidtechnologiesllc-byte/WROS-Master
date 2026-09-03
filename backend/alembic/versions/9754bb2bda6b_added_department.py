import logging
"""added department

Revision ID: 9754bb2bda6b
Revises: 0f65c25a6e4b
Create Date: 2026-04-17 15:35:06.330509

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '9754bb2bda6b'
down_revision: Union[str, Sequence[str], None] = '0f65c25a6e4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(
        text("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = :t"),
        {"t": table_name},
    )
    return result.scalar() > 0

def _column_exists(conn, table_name: str, column_name: str) -> bool:
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = :t AND COLUMN_NAME = :c"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.scalar() > 0

def _fk_exists(conn, table_name: str, column_name: str, ref_table: str) -> bool:
    """Check whether any FK from table_name.column_name → ref_table already exists."""
    result = conn.execute(
        text(
            "SELECT COUNT(*) "
            "FROM sys.foreign_key_columns fkc "
            "JOIN sys.foreign_keys fk ON fkc.constraint_object_id = fk.object_id "
            "JOIN sys.tables t  ON fk.parent_object_id  = t.object_id "
            "JOIN sys.columns c  ON fkc.parent_column_id = c.column_id AND c.object_id = t.object_id "
            "JOIN sys.tables rt ON fk.referenced_object_id = rt.object_id "
            "WHERE t.name = :t AND c.name = :c AND rt.name = :r"
        ),
        {"t": table_name, "c": column_name, "r": ref_table},
    )
    return result.scalar() > 0

def _index_exists(conn, index_name: str) -> bool:
    result = conn.execute(
        text("SELECT COUNT(*) FROM sys.indexes WHERE name = :n"),
        {"n": index_name},
    )
    return result.scalar() > 0

def upgrade() -> None:
    """Upgrade schema — idempotent (safe to re-run)."""
    bind = op.get_bind()

    # ── 1. departments table (may already exist if app ran create_all) ─────────
    if not _table_exists(bind, 'departments'):
        op.create_table(
            'departments',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETDATE()'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
    if not _index_exists(bind, 'ix_departments_id'):
        op.create_index('ix_departments_id', 'departments', ['id'], unique=False)
    if not _index_exists(bind, 'ix_departments_name'):
        op.create_index('ix_departments_name', 'departments', ['name'], unique=True)

    # ── 2. jobs.department_id column + FK ──────────────────────────────────────
    if not _column_exists(bind, 'jobs', 'department_id'):
        op.add_column('jobs', sa.Column('department_id', sa.Integer(), nullable=True))
    if not _index_exists(bind, 'ix_jobs_department_id'):
        op.create_index('ix_jobs_department_id', 'jobs', ['department_id'], unique=False)
    if not _fk_exists(bind, 'jobs', 'department_id', 'departments'):
        op.create_foreign_key(None, 'jobs', 'departments', ['department_id'], ['id'])

    # ── 3. contactPerson: NULL out old free-text data, resize, then add FK ─────
    #    Old data was plain contact names, NOT UserIDs → must be cleared first.
    bind.execute(text("UPDATE jobs SET contactPerson = NULL WHERE contactPerson IS NOT NULL"))
    op.alter_column(
        'jobs', 'contactPerson',
        existing_type=sa.VARCHAR(length=100, collation='SQL_Latin1_General_CP1_CI_AS'),
        type_=sa.String(length=50),
        existing_nullable=True,
    )
    if not _fk_exists(bind, 'jobs', 'contactPerson', 'users'):
        op.create_foreign_key(None, 'jobs', 'users', ['contactPerson'], ['UserID'])

    # ── 4. users.department_id column + FK ────────────────────────────────────
    if not _column_exists(bind, 'users', 'department_id'):
        op.add_column('users', sa.Column('department_id', sa.Integer(), nullable=True))
    if not _index_exists(bind, 'ix_users_department_id'):
        op.create_index('ix_users_department_id', 'users', ['department_id'], unique=False)
    if not _fk_exists(bind, 'users', 'department_id', 'departments'):
        op.create_foreign_key(None, 'users', 'departments', ['department_id'], ['id'])

def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    if _fk_exists(bind, 'users', 'department_id', 'departments'):
        op.drop_constraint(None, 'users', type_='foreignkey')
    if _index_exists(bind, 'ix_users_department_id'):
        op.drop_index('ix_users_department_id', table_name='users')
    if _column_exists(bind, 'users', 'department_id'):
        op.drop_column('users', 'department_id')

    if _fk_exists(bind, 'jobs', 'contactPerson', 'users'):
        op.drop_constraint(None, 'jobs', type_='foreignkey')
    if _fk_exists(bind, 'jobs', 'department_id', 'departments'):
        op.drop_constraint(None, 'jobs', type_='foreignkey')
    if _index_exists(bind, 'ix_jobs_department_id'):
        op.drop_index('ix_jobs_department_id', table_name='jobs')
    op.alter_column(
        'jobs', 'contactPerson',
        existing_type=sa.String(length=50),
        type_=sa.VARCHAR(length=100, collation='SQL_Latin1_General_CP1_CI_AS'),
        existing_nullable=True,
    )
    if _column_exists(bind, 'jobs', 'department_id'):
        op.drop_column('jobs', 'department_id')

    if _table_exists(bind, 'departments'):
        if _index_exists(bind, 'ix_departments_name'):
            op.drop_index('ix_departments_name', table_name='departments')
        if _index_exists(bind, 'ix_departments_id'):
            op.drop_index('ix_departments_id', table_name='departments')
        op.drop_table('departments')
