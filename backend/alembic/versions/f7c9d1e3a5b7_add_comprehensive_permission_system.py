import logging
"""Add comprehensive permission system with job titles and field-level controls

Revision ID: f7c9d1e3a5b7
Revises: f6b8d0a2c4e6
Create Date: 2026-08-13 00:00:00.000000

This migration adds:
1. job_titles table - Admin-managed list of job positions
2. job_title_roles junction table - Maps job titles to roles
3. permissions table - Granular permissions (module, field, scope, action, dashboard)
4. field_permissions table - Field-level access control (masking, hiding PII)
5. data_scope_permissions table - Data scope rules (BU, multi-BU, team, own, org-wide)
6. role_permissions junction table - Maps roles to permissions
7. Updates to users table - Add job_title_id, org_position_id, org_node_id
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7c9d1e3a5b7'
down_revision: Union[str, Sequence[str], None] = '2026_08_12_task_bu'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create job_titles table
    op.create_table(
        'job_titles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_job_title_name_per_tenant'),
    )
    op.create_index('ix_job_titles_tenant_id', 'job_titles', ['tenant_id'])
    op.create_index('ix_job_titles_active', 'job_titles', ['active'])

    # Create job_title_roles junction table
    op.create_table(
        'job_title_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_title_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_title_id'], ['job_titles.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.UniqueConstraint('job_title_id', 'role_id', name='uq_job_title_role'),
    )
    op.create_index('ix_job_title_roles_job_id', 'job_title_roles', ['job_title_id'])
    op.create_index('ix_job_title_roles_role_id', 'job_title_roles', ['role_id'])

    # Create permissions table
    op.create_table(
        'permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('layer', sa.String(50), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_permission_name_per_tenant'),
    )
    op.create_index('ix_permissions_tenant_id', 'permissions', ['tenant_id'])
    op.create_index('ix_permissions_category', 'permissions', ['category'])
    op.create_index('ix_permissions_layer', 'permissions', ['layer'])

    # Create role_permissions junction table
    op.create_table(
        'role_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ),
        sa.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
    )
    op.create_index('ix_role_permissions_role_id', 'role_permissions', ['role_id'])
    op.create_index('ix_role_permissions_permission_id', 'role_permissions', ['permission_id'])

    # Create field_permissions table
    op.create_table(
        'field_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('table_name', sa.String(100), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('access_level', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.UniqueConstraint('role_id', 'table_name', 'field_name', name='uq_field_permission'),
    )
    op.create_index('ix_field_permissions_tenant_id', 'field_permissions', ['tenant_id'])
    op.create_index('ix_field_permissions_role_id', 'field_permissions', ['role_id'])
    op.create_index('ix_field_permissions_table', 'field_permissions', ['table_name'])

    # Create data_scope_permissions table
    op.create_table(
        'data_scope_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('module', sa.String(100), nullable=False),
        sa.Column('scope_type', sa.String(50), nullable=False),
        sa.Column('filter_rule', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.UniqueConstraint('role_id', 'module', name='uq_data_scope_per_role_module'),
    )
    op.create_index('ix_data_scope_tenant_id', 'data_scope_permissions', ['tenant_id'])
    op.create_index('ix_data_scope_role_id', 'data_scope_permissions', ['role_id'])
    op.create_index('ix_data_scope_module', 'data_scope_permissions', ['module'])

    # Add columns to users table
    op.add_column('users', sa.Column('job_title_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('org_position_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('org_node_id', sa.String(36), nullable=True))

    # Create indexes for new user columns
    op.create_index('ix_users_job_title_id', 'users', ['job_title_id'])
    op.create_index('ix_users_org_position_id', 'users', ['org_position_id'])
    op.create_index('ix_users_org_node_id', 'users', ['org_node_id'])

    # Add foreign key constraints
    op.create_foreign_key('fk_users_job_title_id', 'users', 'job_titles', ['job_title_id'], ['id'])
    op.create_foreign_key('fk_users_org_position_id', 'users', 'org_positions', ['org_position_id'], ['id'])
    op.create_foreign_key('fk_users_org_node_id', 'users', 'org_nodes', ['org_node_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop foreign keys
    op.drop_constraint('fk_users_org_node_id', 'users', type_='foreignkey')
    op.drop_constraint('fk_users_org_position_id', 'users', type_='foreignkey')
    op.drop_constraint('fk_users_job_title_id', 'users', type_='foreignkey')

    # Drop indexes
    op.drop_index('ix_users_org_node_id', 'users')
    op.drop_index('ix_users_org_position_id', 'users')
    op.drop_index('ix_users_job_title_id', 'users')

    # Drop columns from users
    op.drop_column('users', 'org_node_id')
    op.drop_column('users', 'org_position_id')
    op.drop_column('users', 'job_title_id')

    # Drop tables
    op.drop_table('data_scope_permissions')
    op.drop_table('field_permissions')
    op.drop_table('role_permissions')
    op.drop_table('permissions')
    op.drop_table('job_title_roles')
    op.drop_table('job_titles')
