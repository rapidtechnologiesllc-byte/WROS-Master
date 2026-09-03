import logging
"""add opportunities table, extend clients + demands (HRMS-0201/0207/0210/0211)

Revision ID: e5f6a7b8c9d1
Revises: d4e5f6a7b8c0
Create Date: 2026-07-21 00:00:00.000005

HRMS-0201 (extends the existing HRMS-0102 clients table rather than
forking it -- see app.models.client's module docstring for the fork
analysis), HRMS-0207 (new opportunities table), HRMS-0210/0211 (extends
the existing HRMS-0103 demands table with opportunity linkage and
revenue-potential fields -- a tag, not a schema branch, per that
story's own BR-0210-01).

VERIFICATION NOTE: op.create_table('opportunities') (with all its
inline FK/CHECK constraints) and both op.add_column() batches
(clients.country; demands.opportunity_id/source_type/duration_hours/
revenue_potential_usd_cents) were verified end-to-end against a
throwaway SQLite database and apply cleanly. The op.create_foreign_key()
adding demands.opportunity_id -> opportunities.id could NOT be verified
the same way -- identical SQLite ALTER-on-existing-table limitation
already documented in e7f8a9b0c1d2/f8a9b0c1d2e3/c3d4e5f6a7b9's
migrations (SQLite has no ALTER-based constraint support outside of
Alembic's batch/copy-recreate mode). The real production target, SQL
Server, supports ALTER TABLE ADD CONSTRAINT natively. Run this on a
staging/dev SQL Server copy first, not production directly, same as
every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d1'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    # --- clients (HRMS-0201) ---
    op.add_column('clients', sa.Column('country', sa.String(length=100), nullable=True))

    # --- opportunities (HRMS-0207) ---
    op.create_table(
        'opportunities',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('client_id', sa.String(length=36), nullable=False),
        sa.Column('owner_employee_id', sa.String(length=36), nullable=True),
        sa.Column('stage', sa.String(length=15), nullable=False),
        sa.Column('revenue_value_usd_cents', sa.Integer(), nullable=False),
        sa.Column('revenue_value_native', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(length=5), nullable=False),
        sa.Column('probability_pct', sa.Integer(), nullable=False),
        sa.Column('expected_close_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['owner_employee_id'], ['employees.id']),
        sa.CheckConstraint(
            "stage IN ('QUALIFICATION','PROPOSAL','NEGOTIATION','WON','LOST')",
            name='ck_opportunities_stage',
        ),
        sa.CheckConstraint(
            "currency IN ('USD','INR','GBP','EUR','CAD','AUD')", name='ck_opportunities_currency',
        ),
        sa.CheckConstraint(
            "probability_pct >= 0 AND probability_pct <= 100", name='ck_opportunities_probability_pct',
        ),
    )
    op.create_index(op.f('ix_opportunities_tenant_id'), 'opportunities', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_opportunities_client_id'), 'opportunities', ['client_id'], unique=False)
    op.create_index(op.f('ix_opportunities_owner_employee_id'), 'opportunities', ['owner_employee_id'], unique=False)

    # --- demands (HRMS-0210/0211) ---
    op.add_column('demands', sa.Column('opportunity_id', sa.String(length=36), nullable=True))
    op.add_column(
        'demands',
        sa.Column('source_type', sa.String(length=15), nullable=False, server_default='DIRECT'),
    )
    op.add_column('demands', sa.Column('duration_hours', sa.Integer(), nullable=True))
    op.add_column('demands', sa.Column('revenue_potential_usd_cents', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_demands_opportunity_id'), 'demands', ['opportunity_id'], unique=False)
    op.create_foreign_key(None, 'demands', 'opportunities', ['opportunity_id'], ['id'])

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('demands', 'revenue_potential_usd_cents')
    op.drop_column('demands', 'duration_hours')
    op.drop_column('demands', 'source_type')
    op.drop_column('demands', 'opportunity_id')
    op.drop_table('opportunities')
    op.drop_column('clients', 'country')
