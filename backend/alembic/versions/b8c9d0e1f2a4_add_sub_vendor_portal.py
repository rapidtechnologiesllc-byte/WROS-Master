import logging
"""add Sub-Vendor Portal core entities (HRMS-P801/P804/P806/P807/P808/P816)

Revision ID: b8c9d0e1f2a4
Revises: a7b8c9d0e1f3
Create Date: 2026-07-21 00:00:00.000008

First build round of EPIC-P8 Sub-Vendor Portal, Phase 2 Domain 5.
Genuinely new schema (nothing existing to extend), plus two small
additive pieces on existing tables: candidates.source_channel/vendor_id
(HRMS-P816 sourcing attribution) and completing the previously-deferred
submissions.subvendor_id FK now that sub_vendor_accounts exists.

VERIFICATION NOTE: all 5 op.create_table() calls (with inline FK/CHECK
constraints) and the op.add_column() batch on candidates were verified
end-to-end against a throwaway SQLite database and apply cleanly. The
op.create_foreign_key() completing submissions.subvendor_id could NOT
be verified the same way -- identical SQLite ALTER-on-existing-table
limitation already documented in several prior migrations in this
package (SQLite has no ALTER-based constraint support outside of
Alembic's batch/copy-recreate mode). The real production target, SQL
Server, supports ALTER TABLE ADD CONSTRAINT natively. Run this on a
staging/dev SQL Server copy first, not production directly, same as
every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a4'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    # --- sub_vendor_accounts (HRMS-P801 + HRMS-P811's compliance_status) ---
    op.create_table(
        'sub_vendor_accounts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('company_name', sa.String(length=300), nullable=False),
        sa.Column('tax_id', sa.String(length=100), nullable=True),
        sa.Column('contact_email', sa.String(length=300), nullable=False),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('compliance_status', sa.String(length=20), nullable=False),
        sa.Column('approved_by', sa.String(length=50), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.UserID']),
        sa.CheckConstraint(
            "status IN ('PENDING_APPROVAL','APPROVED','SUSPENDED','REJECTED')",
            name='ck_sub_vendor_accounts_status',
        ),
        sa.CheckConstraint(
            "compliance_status IN ('GOOD_STANDING','UNDER_REVIEW','SUSPENSION_PENDING','SUSPENDED')",
            name='ck_sub_vendor_accounts_compliance_status',
        ),
    )
    op.create_index(op.f('ix_sub_vendor_accounts_tenant_id'), 'sub_vendor_accounts', ['tenant_id'], unique=False)

    # --- sub_vendor_users (HRMS-P801) ---
    op.create_table(
        'sub_vendor_users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('sub_vendor_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=300), nullable=False),
        sa.Column('password_hash', sa.String(length=300), nullable=False),
        sa.Column('role', sa.String(length=10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sub_vendor_id'], ['sub_vendor_accounts.id']),
        sa.UniqueConstraint('email', name='uq_sub_vendor_users_email'),
        sa.CheckConstraint("role IN ('ADMIN','SUBMITTER')", name='ck_sub_vendor_users_role'),
    )
    op.create_index(op.f('ix_sub_vendor_users_sub_vendor_id'), 'sub_vendor_users', ['sub_vendor_id'], unique=False)

    # --- sub_vendor_requests (HRMS-P804, merged with the richer request concept) ---
    op.create_table(
        'sub_vendor_requests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('demand_id', sa.String(length=36), nullable=False),
        sa.Column('sub_vendor_id', sa.String(length=36), nullable=False),
        sa.Column('assigned_by', sa.String(length=50), nullable=True),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('deadline', sa.DateTime(), nullable=True),
        sa.Column('max_candidates', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['demand_id'], ['demands.id']),
        sa.ForeignKeyConstraint(['sub_vendor_id'], ['sub_vendor_accounts.id']),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.UserID']),
        sa.CheckConstraint("status IN ('OPEN','CLOSED')", name='ck_sub_vendor_requests_status'),
    )
    op.create_index(op.f('ix_sub_vendor_requests_tenant_id'), 'sub_vendor_requests', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_sub_vendor_requests_demand_id'), 'sub_vendor_requests', ['demand_id'], unique=False)
    op.create_index(op.f('ix_sub_vendor_requests_sub_vendor_id'), 'sub_vendor_requests', ['sub_vendor_id'], unique=False)

    # --- sub_vendor_submissions (HRMS-P802/P806/P807/P808) ---
    op.create_table(
        'sub_vendor_submissions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('request_id', sa.String(length=36), nullable=False),
        sa.Column('sub_vendor_id', sa.String(length=36), nullable=False),
        sa.Column('candidate_name', sa.String(length=300), nullable=False),
        sa.Column('candidate_email', sa.String(length=300), nullable=False),
        sa.Column('candidate_phone', sa.String(length=50), nullable=True),
        sa.Column('current_employer', sa.String(length=300), nullable=True),
        sa.Column('total_experience_years', sa.Numeric(precision=4, scale=1), nullable=True),
        sa.Column('expected_salary', sa.String(length=50), nullable=True),
        sa.Column('notice_period', sa.String(length=100), nullable=True),
        sa.Column('resume_url', sa.Text(), nullable=True),
        sa.Column('employment_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('feedback_note', sa.Text(), nullable=True),
        sa.Column('created_candidate_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['request_id'], ['sub_vendor_requests.id']),
        sa.ForeignKeyConstraint(['sub_vendor_id'], ['sub_vendor_accounts.id']),
        sa.ForeignKeyConstraint(['created_candidate_id'], ['candidates.candidateID']),
        sa.CheckConstraint(
            "employment_type IN ('W2_FULLTIME','C2C','1099','UNKNOWN')",
            name='ck_sub_vendor_submissions_employment_type',
        ),
        sa.CheckConstraint(
            "status IN ('PENDING_REVIEW','ACCEPTED','REJECTED','MORE_INFO_REQUESTED')",
            name='ck_sub_vendor_submissions_status',
        ),
    )
    op.create_index(op.f('ix_sub_vendor_submissions_request_id'), 'sub_vendor_submissions', ['request_id'], unique=False)
    op.create_index(op.f('ix_sub_vendor_submissions_sub_vendor_id'), 'sub_vendor_submissions', ['sub_vendor_id'], unique=False)

    # --- sub_vendor_violations (HRMS-P806) ---
    op.create_table(
        'sub_vendor_violations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('sub_vendor_id', sa.String(length=36), nullable=False),
        sa.Column('submission_id', sa.String(length=36), nullable=True),
        sa.Column('violation_type', sa.String(length=20), nullable=False),
        sa.Column('employment_type', sa.String(length=20), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('is_cleared', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['sub_vendor_id'], ['sub_vendor_accounts.id']),
        sa.ForeignKeyConstraint(['submission_id'], ['sub_vendor_submissions.id']),
        sa.CheckConstraint("violation_type IN ('C2C_NOT_ACCEPTED')", name='ck_sub_vendor_violations_type'),
    )
    op.create_index(op.f('ix_sub_vendor_violations_sub_vendor_id'), 'sub_vendor_violations', ['sub_vendor_id'], unique=False)

    # --- sub_vendor_dedup_rejections (HRMS-P807) ---
    op.create_table(
        'sub_vendor_dedup_rejections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('submission_id', sa.String(length=36), nullable=False),
        sa.Column('matched_candidate_id', sa.String(length=50), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['submission_id'], ['sub_vendor_submissions.id']),
        sa.ForeignKeyConstraint(['matched_candidate_id'], ['candidates.candidateID']),
    )
    op.create_index(op.f('ix_sub_vendor_dedup_rejections_submission_id'), 'sub_vendor_dedup_rejections', ['submission_id'], unique=False)

    # --- candidates (HRMS-P816 sourcing attribution) ---
    op.add_column(
        'candidates',
        sa.Column('source_channel', sa.String(length=15), nullable=False, server_default='DIRECT'),
    )
    op.add_column('candidates', sa.Column('vendor_id', sa.String(length=36), nullable=True))

    # --- submissions: complete the previously-deferred FK now that sub_vendor_accounts exists ---
    op.create_foreign_key(None, 'submissions', 'sub_vendor_accounts', ['subvendor_id'], ['id'])

def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('candidates', 'vendor_id')
    op.drop_column('candidates', 'source_channel')
    op.drop_table('sub_vendor_dedup_rejections')
    op.drop_table('sub_vendor_violations')
    op.drop_table('sub_vendor_submissions')
    op.drop_table('sub_vendor_requests')
    op.drop_table('sub_vendor_users')
    op.drop_table('sub_vendor_accounts')
