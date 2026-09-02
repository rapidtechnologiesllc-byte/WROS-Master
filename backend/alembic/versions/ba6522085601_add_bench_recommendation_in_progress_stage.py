import logging
"""widen bench_allocation_recommendations.status to include IN_PROGRESS + pursued_by/pursued_at

Revision ID: ba6522085601
Revises: 73c1aca4119d
Create Date: 2026-07-22 00:00:00.000000

Avinash's explicit business call, 2026-07-22: a bench employee already
being actively pursued for one client ("in interview stage") must be hard-
blocked from being simultaneously pursued for a second. See
app.services.resource_management_agent_service.is_employee_actively_engaged()
/ start_pursuing_recommendation().

VERIFICATION NOTE: batch_alter_table's drop/recreate of the status CHECK
constraint plus two new nullable columns verified end-to-end against a
throwaway SQLite database. Run against a staging SQL Server copy first,
not production directly, same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba6522085601'
down_revision: Union[str, Sequence[str], None] = '73c1aca4119d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_STATUSES = "'PENDING_RM_REVIEW','APPROVED','REJECTED'"
_NEW_STATUSES = "'PENDING_RM_REVIEW','IN_PROGRESS','APPROVED','REJECTED'"


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('bench_allocation_recommendations') as batch_op:
        batch_op.drop_constraint('ck_bench_allocation_recommendations_status', type_='check')
        batch_op.create_check_constraint(
            'ck_bench_allocation_recommendations_status', f"status IN ({_NEW_STATUSES})",
        )
        batch_op.add_column(sa.Column(
            'pursued_by', sa.String(length=50),
            sa.ForeignKey('users.UserID', name='fk_bench_allocation_recommendations_pursued_by'),
            nullable=True,
        ))
        batch_op.add_column(sa.Column('pursued_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('bench_allocation_recommendations') as batch_op:
        batch_op.drop_column('pursued_at')
        batch_op.drop_column('pursued_by')
        batch_op.drop_constraint('ck_bench_allocation_recommendations_status', type_='check')
        batch_op.create_check_constraint(
            'ck_bench_allocation_recommendations_status', f"status IN ({_OLD_STATUSES})",
        )
