"""Add expense manager approval chain (PRIORITY-3: DEFECT-2026-08-12T6)

Revision ID: a7b9c1d3e5f7
Revises: a3c5e7f9b1d3
Create Date: 2026-08-12 00:00:00.000000

PRIORITY 3: Expense Approval Chain
- Make receipt_ref NOT NULL (required for all expenses)
- Add manager_approval_status column (PENDING → APPROVED → rejected to Finance)
- Add manager_approved_by, manager_approved_at for audit trail
- Approval flow: Employee logs → Manager approves (via Task) → Finance reviews → marks paid
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b9c1d3e5f7'
down_revision: Union[str, Sequence[str], None] = 'a3c5e7f9b1d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Make receipt_ref NOT NULL
    op.alter_column('expense_records', 'receipt_ref', existing_type=sa.String(length=300), nullable=False)

    # Add manager approval tracking columns
    op.add_column('expense_records', sa.Column('manager_approval_status', sa.String(length=20), nullable=False, server_default='PENDING'))
    op.add_column('expense_records', sa.Column('manager_approved_by', sa.String(length=50), nullable=True, onupdate=None))
    op.add_column('expense_records', sa.Column('manager_approved_at', sa.DateTime(), nullable=True))

    # Create foreign key for manager approval
    op.create_foreign_key('fk_expense_records_manager_approved_by', 'expense_records', 'users', ['manager_approved_by'], ['UserID'])

    # Add check constraint for manager_approval_status
    op.create_check_constraint(
        'ck_expense_records_manager_approval_status',
        'expense_records',
        "manager_approval_status IN ('PENDING','APPROVED','REJECTED')",
    )

    # Add index for querying pending manager approvals
    op.create_index(op.f('ix_expense_records_manager_approval_status'), 'expense_records', ['manager_approval_status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop index
    op.drop_index(op.f('ix_expense_records_manager_approval_status'), table_name='expense_records')

    # Drop check constraint
    op.drop_constraint('ck_expense_records_manager_approval_status', 'expense_records', type_='check')

    # Drop foreign key
    op.drop_constraint('fk_expense_records_manager_approved_by', 'expense_records', type_='foreignkey')

    # Remove columns
    op.drop_column('expense_records', 'manager_approved_at')
    op.drop_column('expense_records', 'manager_approved_by')
    op.drop_column('expense_records', 'manager_approval_status')

    # Make receipt_ref nullable again
    op.alter_column('expense_records', 'receipt_ref', existing_type=sa.String(length=300), nullable=True)
