import logging
"""Add organizational hierarchy tables

Revision ID: 2026_08_12_org_hierarchy
Revises: 2026_08_12_work_orders
Create Date: 2026-08-12 00:00:00.000000

Foundation for approval chains, role-based access, context-aware UI.
Creates: org_positions, org_nodes, approval_chains tables.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2026_08_12_org_hierarchy'
down_revision = '2026_08_12_work_orders'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create org_positions table (named titles like CEO, Partner, BU Head, etc.)
    # This must come first since other tables reference it
    op.create_table(
        'org_positions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('approves_to_rank', sa.Integer(), nullable=True),
        sa.Column('approves_workflows', sa.String(500), nullable=True),
        sa.Column('rbac_role_name', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_org_positions_name'), 'org_positions', ['name'], unique=True)
    op.create_index(op.f('ix_org_positions_rank'), 'org_positions', ['rank'], unique=False)
    op.create_index(op.f('ix_org_positions_rbac_role_name'), 'org_positions', ['rbac_role_name'], unique=False)

    # Create departments table (teams within business units)
    # Temporarily nullable hiring_manager_id since org_nodes don't exist yet
    op.create_table(
        'departments',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('business_unit_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('hiring_manager_id', sa.String(36), nullable=True),
        sa.Column('cost_center_code', sa.String(50), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['business_unit_id'], ['business_units.id'], ),
        # hiring_manager_id FK will be added after org_nodes table
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_departments_tenant_id'), 'departments', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_departments_active'), 'departments', ['active'], unique=False)
    op.create_index('ix_departments_tenant_id_bu_id', 'departments', ['tenant_id', 'business_unit_id'], unique=False)

    # Create org_nodes table (instances of positions in the tree)
    op.create_table(
        'org_nodes',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('position_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('parent_id', sa.String(36), nullable=True),
        sa.Column('department_id', sa.String(36), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['position_id'], ['org_positions.id'], ),
        sa.ForeignKeyConstraint(['parent_id'], ['org_nodes.id'], ),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_org_nodes_tenant_id'), 'org_nodes', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_org_nodes_position_id'), 'org_nodes', ['position_id'], unique=False)
    op.create_index(op.f('ix_org_nodes_parent_id'), 'org_nodes', ['parent_id'], unique=False)
    op.create_index(op.f('ix_org_nodes_active'), 'org_nodes', ['active'], unique=False)
    op.create_index(op.f('ix_org_nodes_department_id'), 'org_nodes', ['department_id'], unique=False)
    op.create_index('ix_org_nodes_tenant_id_position_id', 'org_nodes', ['tenant_id', 'position_id'], unique=False)
    op.create_index('ix_org_nodes_tenant_id_parent_id', 'org_nodes', ['tenant_id', 'parent_id'], unique=False)
    op.create_index('ix_org_nodes_tenant_id_department_id', 'org_nodes', ['tenant_id', 'department_id'], unique=False)

    # Add hiring_manager_id FK to departments now that org_nodes exists
    op.create_foreign_key(
        'fk_departments_hiring_manager_id',
        'departments', 'org_nodes',
        ['hiring_manager_id'], ['id']
    )

    # Create partner_bu_assignments table (links Partners to Business Units they oversee)
    op.create_table(
        'partner_bu_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('partner_org_node_id', sa.String(36), nullable=False),
        sa.Column('business_unit_id', sa.String(36), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['partner_org_node_id'], ['org_nodes.id'], ),
        sa.ForeignKeyConstraint(['business_unit_id'], ['business_units.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_partner_bu_assignments_tenant_id'), 'partner_bu_assignments', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_partner_bu_assignments_active'), 'partner_bu_assignments', ['active'], unique=False)
    op.create_index('ix_partner_bu_tenant_bu', 'partner_bu_assignments', ['tenant_id', 'business_unit_id'], unique=False)
    op.create_index('ix_partner_bu_partner_node', 'partner_bu_assignments', ['tenant_id', 'partner_org_node_id'], unique=False)

    # Create approval_chains table (routes workflows from position to approver position)
    op.create_table(
        'approval_chains',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('from_position_id', sa.Integer(), nullable=False),
        sa.Column('to_position_id', sa.Integer(), nullable=False),
        sa.Column('workflow', sa.String(100), nullable=False),
        sa.Column('auto_escalate', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('escalate_after_days', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.ForeignKeyConstraint(['from_position_id'], ['org_positions.id'], ),
        sa.ForeignKeyConstraint(['to_position_id'], ['org_positions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approval_chains_tenant_id'), 'approval_chains', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_approval_chains_from_position_id'), 'approval_chains', ['from_position_id'], unique=False)
    op.create_index(op.f('ix_approval_chains_to_position_id'), 'approval_chains', ['to_position_id'], unique=False)
    op.create_index(op.f('ix_approval_chains_active'), 'approval_chains', ['active'], unique=False)
    op.create_index('ix_approval_chains_tenant_workflow', 'approval_chains', ['tenant_id', 'workflow'], unique=False)

def downgrade() -> None:
    # Drop in reverse order of creation

    op.drop_index('ix_approval_chains_tenant_workflow', table_name='approval_chains')
    op.drop_index(op.f('ix_approval_chains_active'), table_name='approval_chains')
    op.drop_index(op.f('ix_approval_chains_to_position_id'), table_name='approval_chains')
    op.drop_index(op.f('ix_approval_chains_from_position_id'), table_name='approval_chains')
    op.drop_index(op.f('ix_approval_chains_tenant_id'), table_name='approval_chains')
    op.drop_table('approval_chains')

    op.drop_index('ix_partner_bu_partner_node', table_name='partner_bu_assignments')
    op.drop_index('ix_partner_bu_tenant_bu', table_name='partner_bu_assignments')
    op.drop_index(op.f('ix_partner_bu_assignments_active'), table_name='partner_bu_assignments')
    op.drop_index(op.f('ix_partner_bu_assignments_tenant_id'), table_name='partner_bu_assignments')
    op.drop_table('partner_bu_assignments')

    # Drop foreign key from departments to org_nodes
    op.drop_constraint('fk_departments_hiring_manager_id', 'departments', type_='foreignkey')

    op.drop_index('ix_org_nodes_tenant_id_department_id', table_name='org_nodes')
    op.drop_index('ix_org_nodes_tenant_id_parent_id', table_name='org_nodes')
    op.drop_index('ix_org_nodes_tenant_id_position_id', table_name='org_nodes')
    op.drop_index(op.f('ix_org_nodes_department_id'), table_name='org_nodes')
    op.drop_index(op.f('ix_org_nodes_active'), table_name='org_nodes')
    op.drop_index(op.f('ix_org_nodes_parent_id'), table_name='org_nodes')
    op.drop_index(op.f('ix_org_nodes_position_id'), table_name='org_nodes')
    op.drop_index(op.f('ix_org_nodes_tenant_id'), table_name='org_nodes')
    op.drop_table('org_nodes')

    op.drop_index('ix_departments_tenant_id_bu_id', table_name='departments')
    op.drop_index(op.f('ix_departments_active'), table_name='departments')
    op.drop_index(op.f('ix_departments_tenant_id'), table_name='departments')
    op.drop_table('departments')

    op.drop_index(op.f('ix_org_positions_rbac_role_name'), table_name='org_positions')
    op.drop_index(op.f('ix_org_positions_rank'), table_name='org_positions')
    op.drop_index(op.f('ix_org_positions_name'), table_name='org_positions')
    op.drop_table('org_positions')
