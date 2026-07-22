"""add demands.confirmation_status/sow fields + demand_alignment_calls (S-372/HRMS-0528)

Revision ID: 73c1aca4119d
Revises: cf4c36d9b053
Create Date: 2026-07-22 00:00:00.000000

S-372/HRMS-0528 Confirmed vs Potential Demand Workflow. See
app.models.demand_confirmation and app.services.demand_confirmation_service
for the story rationale.

VERIFICATION NOTE: op.add_column() x3 on `demands` (new table, no existing
constraint to widen) and op.create_table() for `demand_alignment_calls`
verified end-to-end against a throwaway SQLite database. Run against a
staging SQL Server copy first, not production directly, same as every
migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '73c1aca4119d'
down_revision: Union[str, Sequence[str], None] = 'cf4c36d9b053'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'demands',
        sa.Column('confirmation_status', sa.String(length=20), nullable=False, server_default='POTENTIAL'),
    )
    with op.batch_alter_table('demands') as batch_op:
        batch_op.create_check_constraint(
            'ck_demands_confirmation_status', "confirmation_status IN ('POTENTIAL','CONFIRMED','CANCELLED')",
        )
    op.add_column('demands', sa.Column('sow_reference', sa.String(length=200), nullable=True))
    op.add_column('demands', sa.Column('sow_received_date', sa.Date(), nullable=True))

    op.create_table(
        'demand_alignment_calls',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('demand_id', sa.String(length=36), nullable=False),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('curtis_user_id', sa.String(length=50), nullable=True),
        sa.Column('bu_head_user_id', sa.String(length=50), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('employee_fit_confirmed', sa.Boolean(), nullable=True),
        sa.Column('employee_fit_confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('employee_fit_notes', sa.Text(), nullable=True),
        sa.Column('bu_head_fit_confirmed', sa.Boolean(), nullable=True),
        sa.Column('bu_head_fit_confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('bu_head_fit_notes', sa.Text(), nullable=True),
        sa.Column('specialty_client_release_triggered_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['demand_id'], ['demands.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['curtis_user_id'], ['users.UserID']),
        sa.ForeignKeyConstraint(['bu_head_user_id'], ['users.UserID']),
    )
    op.create_index(op.f('ix_demand_alignment_calls_tenant_id'), 'demand_alignment_calls', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_demand_alignment_calls_demand_id'), 'demand_alignment_calls', ['demand_id'], unique=False)
    op.create_index(op.f('ix_demand_alignment_calls_employee_id'), 'demand_alignment_calls', ['employee_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('demand_alignment_calls')
    with op.batch_alter_table('demands') as batch_op:
        batch_op.drop_constraint('ck_demands_confirmation_status', type_='check')
        batch_op.drop_column('confirmation_status')
        batch_op.drop_column('sow_reference')
        batch_op.drop_column('sow_received_date')
