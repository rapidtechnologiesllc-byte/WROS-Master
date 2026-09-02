import logging
"""RBAC Template System - Modules, Resources, Role Templates

Revision ID: 2026_08_15_001
Revises:
Create Date: 2026-08-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2026_08_15_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create modules table
    op.create_table(
        'modules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('display_name', sa.String(150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_modules_tenant_id', 'tenant_id'),
    )

    # Create resources table
    op.create_table(
        'resources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('module_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(150), nullable=False),
        sa.Column('route_path', sa.String(200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['module_id'], ['modules.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_resources_module_id', 'module_id'),
        sa.Index('ix_resources_tenant_id', 'tenant_id'),
    )

    # Create role_templates table
    op.create_table(
        'role_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_role_templates_tenant_id', 'tenant_id'),
    )

    # Create role_template_permissions table
    op.create_table(
        'role_template_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role_template_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('can_view', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('can_create', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('can_edit', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('can_delete', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['role_template_id'], ['role_templates.id'], ),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_role_template_permissions_role_id', 'role_template_id'),
        sa.Index('ix_role_template_permissions_resource_id', 'resource_id'),
    )

    # Add columns to users table
    op.add_column('users', sa.Column('job_title', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('role_template_id', sa.Integer(), nullable=True))
    op.create_index('ix_users_job_title', 'users', ['job_title'])
    op.create_index('ix_users_role_template_id', 'users', ['role_template_id'])
    op.create_foreign_key('fk_users_role_template_id', 'users', 'role_templates', ['role_template_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_users_role_template_id', 'users', type_='foreignkey')
    op.drop_index('ix_users_role_template_id', 'users')
    op.drop_index('ix_users_job_title', 'users')
    op.drop_column('users', 'role_template_id')
    op.drop_column('users', 'job_title')

    op.drop_table('role_template_permissions')
    op.drop_table('role_templates')
    op.drop_table('resources')
    op.drop_table('modules')
