"""Initialize base database schema with core tables

Revision ID: 0_init_base
Revises: None
Create Date: 2026-09-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '0_init_base'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create base schema tables that other migrations depend on"""

    # Create users table
    op.create_table(
        'users',
        sa.Column('UserID', sa.String(length=512), nullable=False),
        sa.Column('UserEmail', sa.String(length=512), nullable=True),
        sa.Column('UserName', sa.String(length=512), nullable=True),
        sa.Column('UserRole', sa.String(length=512), nullable=True),
        sa.Column('UserPassword', sa.String(length=512), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('UserID'),
        sa.Index('ix_users_UserID', 'UserID'),
    )

    # Create candidates table
    op.create_table(
        'candidates',
        sa.Column('candidateID', sa.String(length=512), nullable=False),
        sa.Column('candidateEmail', sa.String(length=512), nullable=False),
        sa.Column('candidatePassword', sa.String(length=512), nullable=False),
        sa.Column('candidateFirstName', sa.String(length=150), nullable=True),
        sa.Column('candidateMiddleName', sa.String(length=150), nullable=True),
        sa.Column('candidateLastName', sa.String(length=150), nullable=True),
        sa.Column('candidateRole', sa.String(length=512), nullable=True, server_default='Candidate'),
        sa.Column('candidateJobTitle', sa.String(length=512), nullable=True),
        sa.Column('candidateEmployeeType', sa.String(length=512), nullable=True),
        sa.Column('candidateMobile', sa.String(length=20), nullable=True),
        sa.Column('linkedin_url', sa.String(length=512), nullable=True),
        sa.Column('candidateGender', sa.String(length=100), nullable=True),
        sa.Column('candidateDateOfBirth', sa.Date(), nullable=True),
        sa.Column('candidateSource', sa.String(length=512), nullable=True),
        sa.Column('candidateExperience', sa.String(length=512), nullable=True),
        sa.Column('candidateSkills', sa.Text(), nullable=True),
        sa.Column('candidateJoiningDate', sa.Date(), nullable=True),
        sa.Column('candidateExpectedSalary', sa.String(length=512), nullable=True),
        sa.Column('candidateCurrentSalary', sa.String(length=512), nullable=True),
        sa.Column('candidateCurrentLocation', sa.String(length=512), nullable=True),
        sa.Column('candidateTempPassword', sa.String(length=512), nullable=True),
        sa.Column('candidateIsVerified', sa.Boolean(), nullable=True),
        sa.Column('candidateCreatedAt', sa.DateTime(timezone=False), server_default=sa.func.now()),
        sa.Column('total_experience_months', sa.Integer(), nullable=True),
        sa.Column('resume_completeness_score', sa.Integer(), nullable=True),
        sa.Column('employment_type', sa.String(length=50), nullable=False, server_default='UNKNOWN'),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='Asia/Kolkata'),
        sa.Column('source_channel', sa.String(length=50), nullable=False, server_default='DIRECT'),
        sa.Column('vendor_id', sa.String(length=512), nullable=True),
        sa.Column('job_id', sa.String(length=512), nullable=True),
        sa.Column('email_2fa_opted_in', sa.Boolean(), nullable=True),
        sa.Column('email_otp_code_hash', sa.String(length=64), nullable=True),
        sa.Column('email_otp_expires_at', sa.DateTime(), nullable=True),
        sa.Column('submission_bu_id', sa.Integer(), nullable=True),
        sa.Column('associated_bu_id', sa.Integer(), nullable=True),
        sa.Column('submission_timestamp', sa.DateTime(), nullable=True),
        sa.Column('thunder_enabled', sa.Boolean(), nullable=False, server_default='1', default=True),
        sa.Column('status_changed_at', sa.DateTime(), nullable=True),
        sa.Column('previous_status', sa.String(length=100), nullable=True),
        sa.Column('status_change_reason', sa.String(length=500), nullable=True),
        sa.Column('upload_status', sa.String(length=50), nullable=True, server_default='uploading'),
        sa.Column('expected_document_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('actual_document_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('upload_started_at', sa.DateTime(), nullable=True),
        sa.Column('last_document_uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('queued_at', sa.DateTime(), nullable=True),
        sa.Column('processing_started_at', sa.DateTime(), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(), nullable=True),
        sa.Column('upload_error', sa.Text(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=512), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True, index=True),
        sa.PrimaryKeyConstraint('candidateID'),
        sa.Index('ix_candidates_candidateEmail', 'candidateEmail'),
        sa.Index('ix_candidates_job_id', 'job_id'),
        sa.Index('ix_candidates_submission_bu_id', 'submission_bu_id'),
    )

    # Create business_units table
    op.create_table(
        'business_units',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('name', sa.String(length=512), nullable=False),
        sa.Column('region', sa.String(length=256), nullable=True),
        sa.Column('continent', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )

    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('jobID', sa.String(length=50), nullable=False),
        sa.Column('jobTitle', sa.String(length=512), nullable=True),
        sa.Column('jobDescription', sa.Text(), nullable=True),
        sa.Column('createdAt', sa.DateTime(timezone=False), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('jobID'),
    )


def downgrade() -> None:
    """Drop base schema tables"""
    op.drop_table('jobs')
    op.drop_table('business_units')
    op.drop_table('candidates')
    op.drop_table('users')
