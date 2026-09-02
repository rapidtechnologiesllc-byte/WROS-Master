import logging
"""add submission + interview pipeline entities (Phase 2 Domain 2)

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-07-21 00:00:00.000000

HRMS-0711 (Client Submission Pipeline) + HRMS-0706 (Interview Panel
Assignment) -- the piece connecting Demand -> Candidate -> Employee.
Same translation conventions as e7f8a9b0c1d2 (UUID as String(36),
Enum(native_enum=False, create_constraint=True) rendered as
VARCHAR + CHECK constraint, no native Postgres ENUM/JSONB/GIN).

Also extends the pre-existing `candidates` table with two nullable-
by-necessity columns needed for HRMS-P601/P606's compliance gates
(total_experience_months, employment_type) -- employment_type is
NOT NULL with server_default='UNKNOWN' so every existing row fails
closed immediately rather than silently passing an unset check.

VERIFICATION NOTE: every op.add_column() and all 4 op.create_table()
calls (including their inline FKs/UNIQUE/CHECK constraints) were
verified end-to-end against a throwaway SQLite database and apply
cleanly. The one op.create_check_constraint() that ADDS a constraint
to the PRE-EXISTING candidates table could NOT be verified the same
way -- identical SQLite limitation already documented in
e7f8a9b0c1d2's own docstring (SQLite has no ALTER-based constraint
support outside of Alembic's batch/copy-recreate mode). The real
production target, SQL Server, supports ALTER TABLE ADD CONSTRAINT
natively. Run this on a staging/dev SQL Server copy first, not
production directly, same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Extend candidates (HRMS-P601 / HRMS-P606) ---
    op.add_column('candidates', sa.Column('total_experience_months', sa.Integer(), nullable=True))
    op.add_column(
        'candidates',
        sa.Column(
            'employment_type', sa.String(length=20), nullable=False,
            server_default='UNKNOWN',
        ),
    )
    op.create_check_constraint(
        'ck_candidates_employment_type',
        'candidates',
        "employment_type IN ('W2_FULLTIME','C2C','1099','UNKNOWN')",
    )

    # --- submissions (HRMS-0711) ---
    op.create_table(
        'submissions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('demand_id', sa.String(length=36), nullable=False),
        sa.Column('client_id', sa.String(length=36), nullable=False),
        sa.Column('candidate_id', sa.String(length=50), nullable=False),
        sa.Column('submitted_by_user_id', sa.String(length=50), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('client_feedback', sa.Text(), nullable=True),
        sa.Column('client_response_at', sa.DateTime(), nullable=True),
        sa.Column('submission_rank', sa.Integer(), nullable=True),
        sa.Column('submitted_as_resume_url', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('subvendor_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['demand_id'], ['demands.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID']),
        sa.ForeignKeyConstraint(['submitted_by_user_id'], ['users.UserID']),
        sa.UniqueConstraint('tenant_id', 'demand_id', 'candidate_id', name='uq_submission_per_demand_candidate'),
        sa.CheckConstraint(
            "status IN ('SUBMITTED','SHORTLISTED','CLIENT_INTERVIEW_REQUESTED',"
            "'REJECTED_BY_CLIENT','OFFER_EXTENDED','PLACED','WITHDRAWN')",
            name='ck_submissions_status',
        ),
        sa.CheckConstraint("source IN ('INTERNAL','SUBVENDOR')", name='ck_submissions_source'),
    )
    op.create_index(op.f('ix_submissions_tenant_id'), 'submissions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_submissions_demand_id'), 'submissions', ['demand_id'], unique=False)
    op.create_index(op.f('ix_submissions_client_id'), 'submissions', ['client_id'], unique=False)
    op.create_index(op.f('ix_submissions_candidate_id'), 'submissions', ['candidate_id'], unique=False)

    # --- submission_violations (HRMS-P605 / HRMS-P606 audit log) ---
    op.create_table(
        'submission_violations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('recruiter_user_id', sa.String(length=50), nullable=True),
        sa.Column('candidate_id', sa.String(length=50), nullable=False),
        sa.Column('violation_type', sa.String(length=30), nullable=False),
        sa.Column('attempted_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('candidate_status_at_time', sa.String(length=100), nullable=True),
        sa.Column('blocked_message', sa.Text(), nullable=True),
        sa.Column('is_cleared', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['recruiter_user_id'], ['users.UserID']),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID']),
        sa.CheckConstraint(
            "violation_type IN ('NO_MARKET_PROFILE','EXPERIENCE_INELIGIBLE','C2C_NOT_ACCEPTED')",
            name='ck_submission_violations_type',
        ),
    )
    op.create_index(op.f('ix_submission_violations_tenant_id'), 'submission_violations', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_submission_violations_recruiter_user_id'), 'submission_violations', ['recruiter_user_id'], unique=False)

    # --- demand_interview_panels (HRMS-0706) ---
    op.create_table(
        'demand_interview_panels',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('demand_id', sa.String(length=36), nullable=False),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('interview_level', sa.String(length=10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('assigned_by', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['demand_id'], ['demands.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.UserID']),
        sa.UniqueConstraint(
            'tenant_id', 'demand_id', 'interview_level', 'employee_id',
            name='uq_panel_member_per_demand_level',
        ),
        sa.CheckConstraint("interview_level IN ('L1','L2')", name='ck_demand_interview_panels_level'),
    )
    op.create_index(op.f('ix_demand_interview_panels_tenant_id'), 'demand_interview_panels', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_demand_interview_panels_demand_id'), 'demand_interview_panels', ['demand_id'], unique=False)
    op.create_index(op.f('ix_demand_interview_panels_employee_id'), 'demand_interview_panels', ['employee_id'], unique=False)

    # --- submission_interviews (data model sketch's `interviews`) ---
    op.create_table(
        'submission_interviews',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('submission_id', sa.String(length=36), nullable=False),
        sa.Column('candidate_id', sa.String(length=50), nullable=False),
        sa.Column('level', sa.String(length=10), nullable=False),
        sa.Column('panel_id', sa.String(length=36), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('outcome', sa.String(length=10), nullable=False),
        sa.Column('outcome_set_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_via_graph_event_id', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['submission_id'], ['submissions.id']),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID']),
        sa.ForeignKeyConstraint(['panel_id'], ['demand_interview_panels.id']),
        sa.UniqueConstraint('submission_id', 'level', name='uq_one_interview_per_level_per_submission'),
        sa.CheckConstraint("level IN ('L1','L2')", name='ck_submission_interviews_level'),
        sa.CheckConstraint("outcome IN ('PENDING','PASS','FAIL')", name='ck_submission_interviews_outcome'),
    )
    op.create_index(op.f('ix_submission_interviews_tenant_id'), 'submission_interviews', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_submission_interviews_submission_id'), 'submission_interviews', ['submission_id'], unique=False)
    op.create_index(op.f('ix_submission_interviews_candidate_id'), 'submission_interviews', ['candidate_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('submission_interviews')
    op.drop_table('demand_interview_panels')
    op.drop_table('submission_violations')
    op.drop_table('submissions')
    op.drop_constraint('ck_candidates_employment_type', 'candidates', type_='check')
    op.drop_column('candidates', 'employment_type')
    op.drop_column('candidates', 'total_experience_months')
