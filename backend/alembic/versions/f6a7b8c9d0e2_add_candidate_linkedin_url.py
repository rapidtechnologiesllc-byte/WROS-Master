import logging
"""add candidates.linkedin_url for R-07 dedup

Revision ID: f6a7b8c9d0e2
Revises: e5f6a7b8c9d1
Create Date: 2026-07-21 00:00:00.000006

R-07 -- the Development & Review Standard's own worked example of the
dedup gap: "missing phone/LinkedIn." app.services.candidate_service.
create_candidate_safe() checks this field independently from email and
phone; every existing candidate row backfills to NULL (no LinkedIn on
file), which is correct -- it simply means LinkedIn dedup can't fire
for a candidate whose profile was never captured.

VERIFICATION NOTE: a plain nullable ADD COLUMN, verified end-to-end
against a throwaway SQLite database. Run against a staging SQL Server
copy first, not production directly, same as every migration in this
package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e2'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('candidates', sa.Column('linkedin_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('candidates', 'linkedin_url')
