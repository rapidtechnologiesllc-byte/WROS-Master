"""add projects.end_client/client_partner/business_type (delivery-engine-conditional fields)

Revision ID: d4e6f8a1c3b5
Revises: a8c3f1e6d9b2
Create Date: 2026-08-05 00:00:00.000000

Backlog item, 2026-08-05: Avinash -- "If Speciality then always = Staff
Augmentation so you don't need another field, but when it is core we
need to break down the subtype of revenue." end_client/client_partner
are free-text, both nullable, both optional even on the delivery
engine they conceptually belong to (end_client per Avinash's own
"where end client is not a mandatory field"). business_type
(T_AND_M/MANAGED_SERVICES/PROJECT/POD/PILOT) is CORE-only,
service-layer enforced -- see app.services.project_service /
app.api.v1.endpoints.projects, not a DB CHECK constraint.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e6f8a1c3b5'
down_revision: Union[str, Sequence[str], None] = 'a8c3f1e6d9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('end_client', sa.String(length=300), nullable=True))
    op.add_column('projects', sa.Column('client_partner', sa.String(length=300), nullable=True))
    op.add_column(
        'projects',
        sa.Column(
            'business_type',
            sa.Enum('T_AND_M', 'MANAGED_SERVICES', 'PROJECT', 'POD', 'PILOT', name='project_business_type', native_enum=False, create_constraint=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('projects', 'business_type')
    op.drop_column('projects', 'client_partner')
    op.drop_column('projects', 'end_client')
