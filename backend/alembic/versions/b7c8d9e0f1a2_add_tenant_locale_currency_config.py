"""add tenant locale/currency config columns (S-219/HRMS-0121)

Revision ID: b7c8d9e0f1a2
Revises: c1d2e3f4a5b6
Create Date: 2026-07-22 00:00:00.000000

Per-tenant timezone, date-format, and default-display-currency, per the
canonical sheet's own spec ("Per-tenant: timezone, date format, currency
display (USD/GBP/EUR/INR/CAD). Monetary fields store in USD base with
local display."). The requirement doc filed under S-219's own name
(S-219_HRMS-1212.docx, "Analytics Performance Optimization & Caching")
is unrelated content -- same doc-corpus drift pattern already documented
elsewhere this session -- so this migration follows the canonical
sheet's one-line spec directly rather than a mismatched doc.

VERIFICATION NOTE: three op.add_column() calls on the existing `tenants`
table, verified end-to-end against a throwaway SQLite database.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('default_timezone', sa.String(length=50), nullable=False, server_default='UTC'))
    op.add_column(
        'tenants',
        sa.Column(
            'default_date_format',
            sa.Enum('MM/DD/YYYY', 'DD/MM/YYYY', 'YYYY-MM-DD', name='tenant_date_format', native_enum=False, create_constraint=True),
            nullable=False, server_default='MM/DD/YYYY',
        ),
    )
    op.add_column(
        'tenants',
        sa.Column(
            'default_currency',
            sa.Enum('USD', 'INR', 'GBP', 'EUR', 'CAD', 'AUD', name='tenant_default_currency', native_enum=False, create_constraint=True),
            nullable=False, server_default='USD',
        ),
    )


def downgrade() -> None:
    op.drop_column('tenants', 'default_currency')
    op.drop_column('tenants', 'default_date_format')
    op.drop_column('tenants', 'default_timezone')
