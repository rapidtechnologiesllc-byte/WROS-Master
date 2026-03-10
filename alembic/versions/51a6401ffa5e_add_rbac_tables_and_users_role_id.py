"""add_rbac_tables_and_users_role_id

Revision ID: 51a6401ffa5e
Revises: 91a71eaaad47
Create Date: 2026-03-10 09:25:27.575728

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51a6401ffa5e'
down_revision: Union[str, Sequence[str], None] = '91a71eaaad47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# SQL Server-compatible default: GETDATE()
_NOW = sa.text('(GETDATE())')


def upgrade() -> None:
    """Upgrade schema — add RBAC tables and role_id FK on users."""

    # 1. permissions
    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=_NOW, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_permissions_id'),   'permissions', ['id'],   unique=False)
    op.create_index(op.f('ix_permissions_name'), 'permissions', ['name'], unique=True)

    # 2. roles
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=_NOW, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=_NOW, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_roles_id'),   'roles', ['id'],   unique=False)
    op.create_index(op.f('ix_roles_name'), 'roles', ['name'], unique=True)

    # 3. role_attributes
    op.create_table(
        'role_attributes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('attribute_name', sa.String(length=100), nullable=False),
        sa.Column('attribute_value', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'attribute_name', name='uq_role_attribute'),
    )
    op.create_index(op.f('ix_role_attributes_id'),      'role_attributes', ['id'],      unique=False)
    op.create_index(op.f('ix_role_attributes_role_id'), 'role_attributes', ['role_id'], unique=False)

    # 4. role_permissions
    op.create_table(
        'role_permissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
    )
    op.create_index(op.f('ix_role_permissions_permission_id'), 'role_permissions', ['permission_id'], unique=False)
    op.create_index(op.f('ix_role_permissions_role_id'),       'role_permissions', ['role_id'],       unique=False)

    # 5. Add role_id FK to users (nullable — backward-compatible)
    op.add_column('users', sa.Column('role_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_users_role_id'), 'users', ['role_id'], unique=False)
    op.create_foreign_key('fk_users_role_id', 'users', 'roles', ['role_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema — remove RBAC tables and role_id from users."""
    op.drop_constraint('fk_users_role_id', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_role_id'), table_name='users')
    op.drop_column('users', 'role_id')

    op.drop_index(op.f('ix_role_permissions_role_id'),       table_name='role_permissions')
    op.drop_index(op.f('ix_role_permissions_permission_id'), table_name='role_permissions')
    op.drop_table('role_permissions')

    op.drop_index(op.f('ix_role_attributes_role_id'), table_name='role_attributes')
    op.drop_index(op.f('ix_role_attributes_id'),      table_name='role_attributes')
    op.drop_table('role_attributes')

    op.drop_index(op.f('ix_roles_name'), table_name='roles')
    op.drop_index(op.f('ix_roles_id'),   table_name='roles')
    op.drop_table('roles')

    op.drop_index(op.f('ix_permissions_name'), table_name='permissions')
    op.drop_index(op.f('ix_permissions_id'),   table_name='permissions')
    op.drop_table('permissions')
