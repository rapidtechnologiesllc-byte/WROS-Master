import logging
"""Add modules and module_permissions tables - Phase 2B database-driven configuration.

Revision ID: 2026_08_16_add_modules
Revises:
Create Date: 2026-08-16 00:00:00.000000

Migration creates:
1. modules table - system modules (Candidates, Jobs, etc.)
2. module_permissions table - verbs per module (view, create, edit, delete, etc.)

Populates from rbac_expanded_permissions.MODULES and VERB_MATRIX.
"""
from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = '2026_08_16_add_modules'
down_revision = None
branch_labels = None
depends_on = None

# Module data from rbac_expanded_permissions.MODULES
MODULES_DATA = [
    # Recruitment
    {"name": "candidates", "display_name": "Candidates", "category": "Recruitment", "description": "Candidate Management"},
    {"name": "jobs", "display_name": "Jobs", "category": "Recruitment", "description": "Job Postings"},
    {"name": "interviews", "display_name": "Interviews", "category": "Recruitment", "description": "Interview Scheduling"},
    {"name": "offers", "display_name": "Offers", "category": "Recruitment", "description": "Offer Management"},
    {"name": "submissions", "display_name": "Submissions", "category": "Recruitment", "description": "Candidate Submissions"},
    {"name": "offer_readiness", "display_name": "Offer Readiness", "category": "Recruitment", "description": "Offer Readiness"},
    {"name": "candidate_review", "display_name": "Candidate Review", "category": "Recruitment", "description": "Candidate Review"},
    {"name": "bulk_launch", "display_name": "Bulk Launch", "category": "Recruitment", "description": "Bulk Operations"},
    {"name": "thunder_analytics", "display_name": "Thunder Analytics", "category": "Recruitment", "description": "Thunder Analytics"},

    # Sales
    {"name": "clients", "display_name": "Clients", "category": "Sales", "description": "Client Management"},
    {"name": "demand", "display_name": "Demand", "category": "Sales", "description": "Demand Planning"},
    {"name": "opportunities", "display_name": "Opportunities", "category": "Sales", "description": "Sales Opportunities"},
    {"name": "opportunity_pipeline", "display_name": "Pipeline", "category": "Sales", "description": "Opportunity Pipeline"},
    {"name": "partner_roi", "display_name": "Partner ROI", "category": "Sales", "description": "Partner ROI"},

    # Project Management / Delivery
    {"name": "employees", "display_name": "Employees", "category": "Delivery", "description": "Employee Management"},
    {"name": "projects", "display_name": "Projects", "category": "Delivery", "description": "Projects"},
    {"name": "allocations", "display_name": "Allocations", "category": "Delivery", "description": "Resource Allocations"},
    {"name": "resource_management", "display_name": "Resource Mgmt", "category": "Delivery", "description": "Resource Management"},
    {"name": "core_pull", "display_name": "Core-Pull", "category": "Delivery", "description": "Core-Pull Decision"},
    {"name": "utilization", "display_name": "Utilization", "category": "Delivery", "description": "Utilization Tracking"},
    {"name": "forecast", "display_name": "Forecast", "category": "Delivery", "description": "Forecasting"},
    {"name": "buddy_program", "display_name": "Buddy Program", "category": "Delivery", "description": "Buddy Program"},
    {"name": "htd_intake", "display_name": "HTD Intake", "category": "Delivery", "description": "HTD Intake"},

    # Finance & Operations
    {"name": "invoices", "display_name": "Invoices", "category": "Finance", "description": "Invoicing"},
    {"name": "timesheets", "display_name": "Timesheets", "category": "Finance", "description": "Timesheets"},
    {"name": "expenses", "display_name": "Expenses", "category": "Finance", "description": "Expenses"},
    {"name": "revenue", "display_name": "Revenue", "category": "Finance", "description": "Revenue Tracking"},
    {"name": "forecasting", "display_name": "Forecasting", "category": "Finance", "description": "Forecasting"},
    {"name": "finance_operations", "display_name": "Finance Ops", "category": "Finance", "description": "Finance Operations"},

    # Admin & Configuration
    {"name": "rbac", "display_name": "RBAC", "category": "Admin", "description": "RBAC Management"},
    {"name": "users", "display_name": "Users", "category": "Admin", "description": "User Management"},
    {"name": "tenant_config", "display_name": "Tenant Config", "category": "Admin", "description": "Tenant Configuration"},
    {"name": "locale", "display_name": "Locale", "category": "Admin", "description": "Localization"},
    {"name": "ai_config", "display_name": "AI Config", "category": "Admin", "description": "AI Configuration"},
    {"name": "message_templates", "display_name": "Templates", "category": "Admin", "description": "Message Templates"},
    {"name": "ticket_routing", "display_name": "Routing", "category": "Admin", "description": "Ticket Routing"},
    {"name": "documents", "display_name": "Documents", "category": "Admin", "description": "Document Management"},
    {"name": "reports", "display_name": "Reports", "category": "Admin", "description": "Reports"},
    {"name": "tasks", "display_name": "Tasks", "category": "Admin", "description": "Task Management"},
    {"name": "notifications", "display_name": "Notifications", "category": "Admin", "description": "Notifications"},
    {"name": "error_log", "display_name": "Error Logs", "category": "Admin", "description": "Error Logs"},
    {"name": "admin_settings", "display_name": "Settings", "category": "Admin", "description": "Admin Settings"},
    {"name": "executive_signal", "display_name": "Executive", "category": "Admin", "description": "Executive Dashboard"},
]

# Verb matrix from rbac_expanded_permissions.VERB_MATRIX
VERB_MATRIX_DATA = {
    "candidates": ["view", "create", "edit", "delete", "merge"],
    "jobs": ["view", "create", "edit", "delete"],
    "interviews": ["view", "create", "edit", "delete"],
    "offers": ["view", "create", "edit", "delete", "approve"],
    "submissions": ["view", "create", "edit", "delete"],
    "offer_readiness": ["view"],
    "candidate_review": ["view", "edit"],
    "bulk_launch": ["view", "create"],
    "thunder_analytics": ["view"],
    "clients": ["view", "create", "edit", "delete"],
    "demand": ["view", "create", "edit", "delete"],
    "opportunities": ["view", "create", "edit", "delete"],
    "opportunity_pipeline": ["view", "edit"],
    "partner_roi": ["view"],
    "employees": ["view", "create", "edit", "delete"],
    "projects": ["view", "create", "edit", "delete"],
    "allocations": ["view", "create", "edit", "delete"],
    "resource_management": ["view", "edit"],
    "core_pull": ["view", "edit"],
    "utilization": ["view"],
    "forecast": ["view", "create", "edit"],
    "buddy_program": ["view", "edit"],
    "htd_intake": ["view", "create"],
    "invoices": ["view", "create", "edit", "approve"],
    "timesheets": ["view", "create", "edit", "approve"],
    "expenses": ["view", "create", "edit", "approve"],
    "revenue": ["view", "view_pnl", "edit"],
    "forecasting": ["view", "create", "edit"],
    "finance_operations": ["view", "edit"],
    "rbac": ["view", "manage"],
    "users": ["view", "create", "edit", "delete"],
    "tenant_config": ["view", "edit"],
    "locale": ["view", "edit"],
    "ai_config": ["view", "edit"],
    "message_templates": ["view", "create", "edit", "delete"],
    "ticket_routing": ["view", "edit"],
    "documents": ["view", "upload", "verify", "delete"],
    "reports": ["view", "create", "edit", "delete"],
    "tasks": ["view", "create", "edit"],
    "notifications": ["view", "edit"],
    "error_log": ["view"],
    "admin_settings": ["view", "edit"],
    "executive_signal": ["view"],
}

def upgrade() -> None:
    # Create system_modules table
    op.create_table(
        'system_modules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='_system_module_name_uc'),
    )
    op.create_index('ix_system_modules_name', 'system_modules', ['name'])

    # Create system_module_permissions table
    op.create_table(
        'system_module_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('module_id', sa.Integer(), nullable=False),
        sa.Column('verb', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tenant_id', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['module_id'], ['system_modules.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('module_id', 'verb', name='_system_module_verb_uc'),
    )
    op.create_index('ix_system_module_permissions_module_id', 'system_module_permissions', ['module_id'])

    # Populate system_modules
    modules_table = sa.table('system_modules',
        sa.column('name', sa.String),
        sa.column('display_name', sa.String),
        sa.column('description', sa.Text),
        sa.column('category', sa.String),
        sa.column('is_active', sa.Boolean),
        sa.column('tenant_id', sa.Integer),
    )

    for module_data in MODULES_DATA:
        op.execute(modules_table.insert().values(
            name=module_data['name'],
            display_name=module_data['display_name'],
            description=module_data['description'],
            category=module_data['category'],
            is_active=True,
            tenant_id=1,
        ))

    # Populate system_module_permissions by querying module IDs
    connection = op.get_bind()
    for module_name, verbs in VERB_MATRIX_DATA.items():
        # Get module ID
        result = connection.execute(sa.text(
            "SELECT id FROM system_modules WHERE name = :name"
        ), {"name": module_name})
        module_row = result.fetchone()

        if module_row:
            module_id = module_row[0]
            for verb in verbs:
                connection.execute(sa.text(
                    "INSERT INTO system_module_permissions (module_id, verb, is_active, tenant_id) "
                    "VALUES (:module_id, :verb, true, 1)"
                ), {"module_id": module_id, "verb": verb})

    connection.commit()

def downgrade() -> None:
    # Drop foreign key constraint first
    op.drop_table('system_module_permissions')
    op.drop_table('system_modules')
