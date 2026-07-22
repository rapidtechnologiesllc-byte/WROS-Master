"""add timesheet_anomaly_flags + projects.allow_weekend_billing (HRMS-0910)

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-07-21 00:00:00.000011

HRMS-0910 -- AI Time Entry Anomaly Detection (S-229). BR-0910-02 needs
`projects.allow_weekend_billing` to know when a weekend entry is
expected rather than anomalous; the flags table itself is brand new.
HRMS-0909 (Client Revenue Dashboard) needed no schema at all -- pure
aggregation over Invoice/Opportunity/Timesheet, per its own Data
Mapping note ("target table: N/A -- computed on view load").

VERIFICATION NOTE: op.add_column() on the existing `projects` table and
op.create_table() for the new `timesheet_anomaly_flags` table (plus its
index) verified end-to-end against a throwaway SQLite database and
apply cleanly. Run against a staging SQL Server copy first, not
production directly, same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'projects',
        sa.Column('allow_weekend_billing', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        'timesheet_anomaly_flags',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('timesheet_entry_id', sa.String(length=36), nullable=False),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=True),
        sa.Column('anomaly_type', sa.Enum('WEEKEND', 'OVER_12H', 'COMPLETED_PROJECT', 'DUPLICATE', name='timesheet_anomaly_type', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('detected_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['timesheet_entry_id'], ['timesheet_entries.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
    )
    op.create_index(op.f('ix_timesheet_anomaly_flags_tenant_id'), 'timesheet_anomaly_flags', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_timesheet_anomaly_flags_timesheet_entry_id'), 'timesheet_anomaly_flags', ['timesheet_entry_id'], unique=False)
    op.create_index(op.f('ix_timesheet_anomaly_flags_employee_id'), 'timesheet_anomaly_flags', ['employee_id'], unique=False)
    op.create_index(op.f('ix_timesheet_anomaly_flags_project_id'), 'timesheet_anomaly_flags', ['project_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('timesheet_anomaly_flags')
    op.drop_column('projects', 'allow_weekend_billing')
