import logging
"""add_business_unit_id_to_departments

Revision ID: a1b2c3d4e5f6
Revises: 0d0274b3c291
Create Date: 2026-06-09 08:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'b8a2a9677931'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    """Check whether any FK from table_name.column_name -> ref_table already exists."""
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
    """Add business_unit_id FK column to departments table (idempotent)."""
    bind = op.get_bind()

    # Add business_unit_id column to departments
    if not _column_exists(bind, 'departments', 'business_unit_id'):
        op.add_column(
            'departments',
            sa.Column('business_unit_id', sa.Integer(), nullable=True)
        )

    # Create index on departments.business_unit_id
    if not _index_exists(bind, 'ix_departments_business_unit_id'):
        op.create_index(
            'ix_departments_business_unit_id',
            'departments',
            ['business_unit_id'],
            unique=False,
        )

    # Add FK: departments.business_unit_id -> business_units.id
    if not _fk_exists(bind, 'departments', 'business_unit_id', 'business_units'):
        op.create_foreign_key(
            'fk_departments_business_unit_id',
            'departments',
            'business_units',
            ['business_unit_id'],
            ['id'],
        )


def downgrade() -> None:
    """Remove business_unit_id FK column from departments table."""
    bind = op.get_bind()

    if _fk_exists(bind, 'departments', 'business_unit_id', 'business_units'):
        op.drop_constraint('fk_departments_business_unit_id', 'departments', type_='foreignkey')

    if _index_exists(bind, 'ix_departments_business_unit_id'):
        op.drop_index('ix_departments_business_unit_id', table_name='departments')

    if _column_exists(bind, 'departments', 'business_unit_id'):
        op.drop_column('departments', 'business_unit_id')
