"""add employee, client, demand entities (Phase 2 Domain 2/3/4 foundation)

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-07-20 06:00:00.000000

HRMS-0101 (+ 0101-REV), HRMS-0102, HRMS-0103 -- see
docs/build-package/REQUIREMENTS-CATALOG.md and the corresponding model
files' docstrings for the full translation-from-spec notes (UUID as
String(36), Enum(native_enum=False, create_constraint=True) instead of
Postgres-native ENUM, Text instead of JSONB, no GIN index).

VERIFICATION NOTE: the 9 new CREATE TABLE operations (employees +
history/documents/engine-history, clients + contacts/history, demands +
history), including every inline FK and CHECK constraint, were verified
end-to-end against a throwaway SQLite database and apply cleanly. The
3 op.create_foreign_key() calls that ADD a constraint to the
PRE-EXISTING business_units table could NOT be verified the same way --
SQLite has no ALTER-based constraint support at all (Alembic requires
"batch mode", a copy-and-recreate strategy, for this on SQLite
specifically). This is a SQLite tooling limitation, not a defect in
this migration: the real production target is SQL Server, which
supports ALTER TABLE ADD CONSTRAINT natively, and this same
create_foreign_key(None, 'existing_table', ...) pattern was already
used successfully in earlier Phase 1 migrations against real business
tables. Still: run this on a staging/dev SQL Server copy first, not
production directly, same as every migration in this package.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Extend existing business_units table (HRMS-0101 step 2) ---
    op.add_column('business_units', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.add_column('business_units', sa.Column('bu_code', sa.String(length=50), nullable=True))
    op.add_column('business_units', sa.Column('parent_bu_id', sa.Integer(), nullable=True))
    op.add_column('business_units', sa.Column('bu_head_employee_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_business_units_tenant_id'), 'business_units', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_business_units_parent_bu_id'), 'business_units', ['parent_bu_id'], unique=False)
    op.create_index(op.f('ix_business_units_bu_head_employee_id'), 'business_units', ['bu_head_employee_id'], unique=False)
    op.create_foreign_key(None, 'business_units', 'tenants', ['tenant_id'], ['id'])
    op.create_foreign_key(None, 'business_units', 'business_units', ['parent_bu_id'], ['id'])

    # --- employees (HRMS-0101 + 0101-REV) ---
    op.create_table(
        'employees',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('candidate_id', sa.String(length=50), nullable=True),
        sa.Column('employee_number', sa.String(length=50), nullable=True),
        sa.Column('tenant_employee_id', sa.String(length=100), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('legal_name', sa.String(length=300), nullable=True),
        sa.Column('email', sa.String(length=300), nullable=False),
        sa.Column('personal_email', sa.String(length=300), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('gender', sa.String(length=50), nullable=True),
        sa.Column('nationality', sa.String(length=100), nullable=True),
        sa.Column('current_address', sa.Text(), nullable=True),
        sa.Column('permanent_address', sa.Text(), nullable=True),
        sa.Column('emergency_contact_name', sa.String(length=200), nullable=True),
        sa.Column('emergency_contact_phone', sa.String(length=50), nullable=True),
        sa.Column('joining_date', sa.Date(), nullable=False),
        sa.Column('confirmation_date', sa.Date(), nullable=True),
        sa.Column('exit_date', sa.Date(), nullable=True),
        sa.Column('employment_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('bu_id', sa.Integer(), nullable=True),
        sa.Column('manager_id', sa.String(length=36), nullable=True),
        sa.Column('current_title', sa.String(length=200), nullable=True),
        sa.Column('current_skills', sa.Text(), nullable=True),
        sa.Column('total_experience_months', sa.Integer(), nullable=True),
        sa.Column('blitzenx_experience_months', sa.Integer(), nullable=False),
        sa.Column('base_salary_usd_cents', sa.Integer(), nullable=True),
        sa.Column('billing_rate_usd_cents', sa.Integer(), nullable=True),
        sa.Column('billing_classification', sa.String(length=20), nullable=False),
        sa.Column('work_location', sa.String(length=20), nullable=False),
        sa.Column('visa_status', sa.String(length=100), nullable=True),
        sa.Column('pan_number', sa.String(length=50), nullable=True),
        sa.Column('tax_id', sa.String(length=100), nullable=True),
        sa.Column('bank_account_number_encrypted', sa.Text(), nullable=True),
        sa.Column('bank_routing_encrypted', sa.Text(), nullable=True),
        sa.Column('wros_user_id', sa.String(length=50), nullable=True),
        sa.Column('delivery_engine', sa.String(length=20), nullable=False),
        sa.Column('engine_entry_date', sa.Date(), nullable=False),
        sa.Column('core_eligible_from', sa.Date(), nullable=True),
        sa.Column('core_certified', sa.Boolean(), nullable=False),
        sa.Column('core_certified_date', sa.Date(), nullable=True),
        sa.Column('buddy_program_status', sa.String(length=20), nullable=False),
        sa.Column('buddy_program_start_date', sa.Date(), nullable=True),
        sa.Column('buddy_program_graduation_date', sa.Date(), nullable=True),
        sa.Column('htd_track', sa.Boolean(), nullable=False),
        sa.Column('htd_start_date', sa.Date(), nullable=True),
        sa.Column('htd_phase', sa.String(length=30), nullable=True),
        sa.Column('reporting_manager_user_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.candidateID']),
        sa.ForeignKeyConstraint(['bu_id'], ['business_units.id']),
        sa.ForeignKeyConstraint(['manager_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['wros_user_id'], ['users.UserID']),
        sa.ForeignKeyConstraint(['reporting_manager_user_id'], ['users.UserID']),
        sa.UniqueConstraint('candidate_id'),
        sa.UniqueConstraint('tenant_id', 'employee_number', name='uq_employee_number_per_tenant'),
        sa.CheckConstraint(
            "employment_type IN ('PERMANENT','CONTRACT','FIXED_TERM')", name='ck_employees_employment_type'
        ),
        sa.CheckConstraint(
            "status IN ('PRE_JOINING','ACTIVE','ON_LEAVE','BENCH','ALLOCATED','NOTICE_PERIOD','EXITED')",
            name='ck_employees_status',
        ),
        sa.CheckConstraint(
            "billing_classification IN ('BENCH','ALLOCATED','NON_BILLABLE')", name='ck_employees_billing_classification'
        ),
        sa.CheckConstraint("work_location IN ('REMOTE','ONSITE','HYBRID')", name='ck_employees_work_location'),
        sa.CheckConstraint("delivery_engine IN ('SPECIALITY','CORE')", name='ck_employees_delivery_engine'),
        sa.CheckConstraint(
            "buddy_program_status IN ('NOT_STARTED','IN_PROGRESS','GRADUATED','EXTENDED','EXITED')",
            name='ck_employees_buddy_program_status',
        ),
        sa.CheckConstraint(
            "htd_phase IS NULL OR htd_phase IN "
            "('INDUCTION','SHADOW_DELIVERY','CONTROLLED_OWNERSHIP','CORE_ELIGIBILITY_REVIEW','COMPLETED','EXITED')",
            name='ck_employees_htd_phase',
        ),
        # HRMS-0101-REV BR -- DB-level guard, independent of application
        # code: no code path (including direct DB access) can set an
        # employee to CORE without core_certified=TRUE.
        sa.CheckConstraint(
            "delivery_engine != 'CORE' OR core_certified = 1", name='ck_employees_core_requires_certified'
        ),
    )
    op.create_index(op.f('ix_employees_tenant_id'), 'employees', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_employees_email'), 'employees', ['email'], unique=False)
    op.create_index(op.f('ix_employees_bu_id'), 'employees', ['bu_id'], unique=False)
    op.create_index(op.f('ix_employees_manager_id'), 'employees', ['manager_id'], unique=False)

    op.create_table(
        'employee_employment_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('change_type', sa.String(length=20), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('changed_by', sa.String(length=50), nullable=True),
        sa.Column('changed_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.CheckConstraint(
            "change_type IN ('TITLE','SALARY','BILLING_RATE','STATUS','BU','MANAGER','LOCATION')",
            name='ck_employment_history_change_type',
        ),
    )
    op.create_index(op.f('ix_employee_employment_history_tenant_id'), 'employee_employment_history', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_employee_employment_history_employee_id'), 'employee_employment_history', ['employee_id'], unique=False)

    op.create_table(
        'employee_documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('document_type', sa.String(length=20), nullable=False),
        sa.Column('document_url', sa.Text(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('verified_by', sa.String(length=50), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.CheckConstraint(
            "document_type IN ('OFFER_LETTER','CONTRACT','ID_PROOF','ADDRESS_PROOF','PAN','TAX_FORM','VISA','NDA','OTHER')",
            name='ck_employee_documents_type',
        ),
    )
    op.create_index(op.f('ix_employee_documents_tenant_id'), 'employee_documents', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_employee_documents_employee_id'), 'employee_documents', ['employee_id'], unique=False)

    op.create_table(
        'employee_engine_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('employee_id', sa.String(length=36), nullable=False),
        sa.Column('from_engine', sa.String(length=20), nullable=True),
        sa.Column('to_engine', sa.String(length=20), nullable=False),
        sa.Column('changed_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('changed_by', sa.String(length=50), nullable=True),
        sa.Column('approval_reference', sa.String(length=200), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.CheckConstraint("from_engine IS NULL OR from_engine IN ('SPECIALITY','CORE')", name='ck_engine_history_from'),
        sa.CheckConstraint("to_engine IN ('SPECIALITY','CORE')", name='ck_engine_history_to'),
    )
    op.create_index(op.f('ix_employee_engine_history_tenant_id'), 'employee_engine_history', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_employee_engine_history_employee_id'), 'employee_engine_history', ['employee_id'], unique=False)

    # Now that employees exists, add the FK from business_units.bu_head_employee_id
    op.create_foreign_key(None, 'business_units', 'employees', ['bu_head_employee_id'], ['id'])

    # --- clients (HRMS-0102) ---
    op.create_table(
        'clients',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('company_name', sa.String(length=300), nullable=False),
        sa.Column('company_short_name', sa.String(length=50), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('client_type', sa.String(length=20), nullable=False),
        sa.Column('tier', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('account_manager_employee_id', sa.String(length=36), nullable=True),
        sa.Column('billing_address', sa.Text(), nullable=True),
        sa.Column('billing_currency', sa.String(length=10), nullable=False),
        sa.Column('payment_terms_days', sa.Integer(), nullable=False),
        sa.Column('credit_limit_usd_cents', sa.Integer(), nullable=True),
        sa.Column('tax_id_client', sa.String(length=100), nullable=True),
        sa.Column('contract_start_date', sa.Date(), nullable=True),
        sa.Column('contract_end_date', sa.Date(), nullable=True),
        sa.Column('contract_url', sa.Text(), nullable=True),
        sa.Column('markup_rate_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('nda_signed', sa.Boolean(), nullable=False),
        sa.Column('nda_url', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['account_manager_employee_id'], ['employees.id']),
        sa.UniqueConstraint('tenant_id', 'company_name', name='uq_client_company_name_per_tenant'),
        sa.CheckConstraint("client_type IN ('DIRECT','MSP','VMS')", name='ck_clients_client_type'),
        sa.CheckConstraint("tier IN ('PLATINUM','GOLD','SILVER','STANDARD')", name='ck_clients_tier'),
        sa.CheckConstraint("status IN ('PROSPECT','ACTIVE','ON_HOLD','INACTIVE')", name='ck_clients_status'),
        sa.CheckConstraint("billing_currency IN ('USD','INR','GBP','EUR','CAD','AUD')", name='ck_clients_billing_currency'),
    )
    op.create_index(op.f('ix_clients_tenant_id'), 'clients', ['tenant_id'], unique=False)

    op.create_table(
        'client_contacts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('client_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('email', sa.String(length=300), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('role_type', sa.String(length=20), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('linkedin_url', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.UniqueConstraint('client_id', 'email', name='uq_client_contact_email_per_client'),
        sa.CheckConstraint(
            "role_type IN ('HIRING_MANAGER','TECHNICAL_PANEL','PROCUREMENT','ACCOUNTS','PRIMARY')",
            name='ck_client_contacts_role_type',
        ),
    )
    op.create_index(op.f('ix_client_contacts_tenant_id'), 'client_contacts', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_client_contacts_client_id'), 'client_contacts', ['client_id'], unique=False)

    op.create_table(
        'client_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('client_id', sa.String(length=36), nullable=False),
        sa.Column('change_type', sa.String(length=20), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('changed_by', sa.String(length=50), nullable=True),
        sa.Column('changed_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.CheckConstraint(
            "change_type IN ('STATUS','ACCOUNT_MANAGER','TIER','CONTRACT_TERMS')", name='ck_client_history_change_type'
        ),
    )
    op.create_index(op.f('ix_client_history_tenant_id'), 'client_history', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_client_history_client_id'), 'client_history', ['client_id'], unique=False)

    # --- demands (HRMS-0103) ---
    op.create_table(
        'demands',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('client_id', sa.String(length=36), nullable=False),
        sa.Column('job_title', sa.String(length=300), nullable=False),
        sa.Column('job_description', sa.Text(), nullable=True),
        sa.Column('required_skills', sa.Text(), nullable=False),
        sa.Column('nice_to_have_skills', sa.Text(), nullable=True),
        sa.Column('min_experience_years', sa.Numeric(4, 1), nullable=False),
        sa.Column('max_experience_years', sa.Numeric(4, 1), nullable=True),
        sa.Column('work_location', sa.String(length=20), nullable=False),
        sa.Column('job_location', sa.String(length=200), nullable=True),
        sa.Column('domain', sa.String(length=100), nullable=True),
        sa.Column('employment_type', sa.String(length=20), nullable=False),
        sa.Column('interview_type_required', sa.String(length=20), nullable=False),
        sa.Column('headcount', sa.Integer(), nullable=False),
        sa.Column('positions_filled', sa.Integer(), nullable=False),
        sa.Column('billing_rate_usd_cents', sa.Integer(), nullable=True),
        sa.Column('budget_min_usd_cents', sa.Integer(), nullable=True),
        sa.Column('budget_max_usd_cents', sa.Integer(), nullable=True),
        sa.Column('required_start_date', sa.Date(), nullable=True),
        sa.Column('urgency', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('sourcing_enabled', sa.Boolean(), nullable=False),
        sa.Column('bench_first_checked', sa.Boolean(), nullable=False),
        sa.Column('assigned_recruiter_employee_id', sa.String(length=36), nullable=True),
        sa.Column('assigned_bu_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['assigned_recruiter_employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['assigned_bu_id'], ['business_units.id']),
        sa.CheckConstraint("employment_type = 'W2_FULLTIME'", name='ck_demands_employment_type'),
        sa.CheckConstraint("interview_type_required IN ('L1_ONLY','L1_AND_L2')", name='ck_demands_interview_type'),
        sa.CheckConstraint("work_location IN ('REMOTE','ONSITE','HYBRID')", name='ck_demands_work_location'),
        sa.CheckConstraint("urgency IN ('IMMEDIATE','HIGH','NORMAL','FLEXIBLE')", name='ck_demands_urgency'),
        sa.CheckConstraint(
            "status IN ('DRAFT','OPEN','IN_PROGRESS','FILLED','CANCELLED','ON_HOLD')", name='ck_demands_status'
        ),
    )
    op.create_index(op.f('ix_demands_tenant_id'), 'demands', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_demands_client_id'), 'demands', ['client_id'], unique=False)
    op.create_index(op.f('ix_demands_assigned_recruiter_employee_id'), 'demands', ['assigned_recruiter_employee_id'], unique=False)
    op.create_index(op.f('ix_demands_assigned_bu_id'), 'demands', ['assigned_bu_id'], unique=False)

    op.create_table(
        'demand_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('demand_id', sa.String(length=36), nullable=False),
        sa.Column('change_type', sa.String(length=20), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('changed_by', sa.String(length=50), nullable=True),
        sa.Column('changed_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['demand_id'], ['demands.id']),
        sa.CheckConstraint(
            "change_type IN ('STATUS','RECRUITER','URGENCY','HEADCOUNT')", name='ck_demand_history_change_type'
        ),
    )
    op.create_index(op.f('ix_demand_history_tenant_id'), 'demand_history', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_demand_history_demand_id'), 'demand_history', ['demand_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('demand_history')
    op.drop_table('demands')
    op.drop_table('client_history')
    op.drop_table('client_contacts')
    op.drop_table('clients')
    op.drop_constraint(None, 'business_units', type_='foreignkey')  # bu_head_employee_id -> employees
    op.drop_table('employee_engine_history')
    op.drop_table('employee_documents')
    op.drop_table('employee_employment_history')
    op.drop_table('employees')
    op.drop_constraint(None, 'business_units', type_='foreignkey')  # parent_bu_id
    op.drop_constraint(None, 'business_units', type_='foreignkey')  # tenant_id
    op.drop_index(op.f('ix_business_units_bu_head_employee_id'), table_name='business_units')
    op.drop_index(op.f('ix_business_units_parent_bu_id'), table_name='business_units')
    op.drop_index(op.f('ix_business_units_tenant_id'), table_name='business_units')
    op.drop_column('business_units', 'bu_head_employee_id')
    op.drop_column('business_units', 'parent_bu_id')
    op.drop_column('business_units', 'bu_code')
    op.drop_column('business_units', 'tenant_id')
