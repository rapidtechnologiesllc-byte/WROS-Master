import logging
"""Add agent_configs table for Agent Config system.

Revision ID: 2026_08_26_add_agent_config
Revises:
Create Date: 2026-08-26 10:00:00.000000

This migration creates the agent_configs table to support dynamic agent
configuration and pipeline orchestration by the Flash Orchestrator.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = '2026_08_26_add_agent_config'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create agent_configs table with indexes."""
    op.create_table(
        'agent_configs',
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('queue_name', sa.String(100), nullable=False),
        sa.Column('next_queue_name', sa.String(100), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes for efficient querying
    op.create_index(
        'ix_agent_configs_tenant_id_name',
        'agent_configs',
        ['tenant_id', 'name'],
        unique=False
    )
    op.create_index(
        'ix_agent_configs_tenant_id_order',
        'agent_configs',
        ['tenant_id', 'order'],
        unique=False
    )
    op.create_unique_constraint(
        'uq_agent_configs_name',
        'agent_configs',
        ['name']
    )


def downgrade():
    """Drop agent_configs table and indexes."""
    op.drop_constraint('uq_agent_configs_name', 'agent_configs', type_='unique')
    op.drop_index('ix_agent_configs_tenant_id_order', table_name='agent_configs')
    op.drop_index('ix_agent_configs_tenant_id_name', table_name='agent_configs')
    op.drop_table('agent_configs')
