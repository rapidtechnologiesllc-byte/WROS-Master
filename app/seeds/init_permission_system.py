"""Initialize comprehensive permission system with 8 roles and permissions"""
import sys
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.models import Base
from app.models.permission import (
    JobTitle, JobTitleRole, DetailedPermission, DetailedRolePermission, FieldPermission, DataScopePermission
)
from app.models.rbac import Role


# 8 Role definitions
ROLES_CONFIG = {
    "CEO": {"name": "CEO", "description": "Chief Executive Officer - Full org-wide access"},
    "CFO": {"name": "CFO", "description": "Chief Financial Officer - Financial & strategic access"},
    "Admin": {"name": "Admin", "description": "System Admin - All configuration management"},
    "Partner": {"name": "Partner", "description": "Partner - Multi-BU oversight"},
    "BU Head": {"name": "BU Head", "description": "Business Unit Head - Single BU management"},
    "Manager": {"name": "Manager", "description": "Manager - Team management only"},
    "Recruiter": {"name": "Recruiter", "description": "Recruiter - Recruitment operations"},
    "HR Manager": {"name": "HR Manager", "description": "HR Manager - Human resources operations"},
    "Finance": {"name": "Finance", "description": "Finance - Financial operations"},
}

# Permission definitions
PERMISSIONS_CONFIG = {
    # Module Access Permissions
    "recruitment.view": {"category": "module", "layer": "module", "description": "View recruitment modules"},
    "recruitment.manage": {"category": "module", "layer": "module", "description": "Manage recruitment"},
    "employee.view": {"category": "module", "layer": "module", "description": "View employee data"},
    "employee.manage": {"category": "module", "layer": "module", "description": "Manage employees"},
    "invoice.view": {"category": "module", "layer": "module", "description": "View invoices"},
    "invoice.approve": {"category": "module", "layer": "module", "description": "Approve invoices"},
    "payroll.manage": {"category": "module", "layer": "module", "description": "Manage payroll"},
    "reports.view": {"category": "module", "layer": "module", "description": "View reports"},
    "reports.financial": {"category": "module", "layer": "module", "description": "View financial reports"},
    "user.manage": {"category": "module", "layer": "module", "description": "Manage users"},
    "role.manage": {"category": "module", "layer": "module", "description": "Manage roles"},
    "job_title.manage": {"category": "module", "layer": "module", "description": "Manage job titles"},
    "system.manage": {"category": "module", "layer": "module", "description": "Manage system config"},
    "system.view": {"category": "module", "layer": "module", "description": "View system info"},
    "business_unit.manage": {"category": "module", "layer": "module", "description": "Manage business units"},
    "business_unit.view": {"category": "module", "layer": "module", "description": "View business units"},
    "revenue.view_pnl": {"category": "module", "layer": "module", "description": "View P&L reports"},

    # Action Permissions
    "candidate.view": {"category": "candidate", "layer": "action", "description": "View candidates"},
    "candidate.create": {"category": "candidate", "layer": "action", "description": "Create candidates"},
    "candidate.edit": {"category": "candidate", "layer": "action", "description": "Edit candidates"},
    "candidate.delete": {"category": "candidate", "layer": "action", "description": "Delete candidates"},
    "interview.manage": {"category": "candidate", "layer": "action", "description": "Manage interviews"},
    "timesheet.view": {"category": "employee", "layer": "action", "description": "View timesheets"},
    "timesheet.approve": {"category": "employee", "layer": "action", "description": "Approve timesheets"},
    "leave.approve": {"category": "employee", "layer": "action", "description": "Approve leave requests"},
}

# Role-Permission mappings
ROLE_PERMISSIONS = {
    "CEO": [
        # All permissions (superuser)
        "recruitment.view", "recruitment.manage", "employee.view", "employee.manage",
        "invoice.view", "invoice.approve", "payroll.manage", "reports.view", "reports.financial",
        "user.manage", "role.manage", "job_title.manage", "system.manage", "system.view",
        "business_unit.manage", "business_unit.view", "revenue.view_pnl",
        "candidate.view", "candidate.create", "candidate.edit", "candidate.delete",
        "interview.manage", "timesheet.view", "timesheet.approve", "leave.approve",
    ],
    "CFO": [
        "invoice.view", "invoice.approve", "payroll.manage", "reports.financial",
        "revenue.view_pnl", "timesheet.view", "system.view",
    ],
    "Admin": [
        # All permissions (superuser for system config)
        "recruitment.view", "recruitment.manage", "employee.view", "employee.manage",
        "invoice.view", "invoice.approve", "payroll.manage", "reports.view", "reports.financial",
        "user.manage", "role.manage", "job_title.manage", "system.manage", "system.view",
        "business_unit.manage", "business_unit.view",
        "candidate.view", "candidate.create", "candidate.edit", "candidate.delete",
        "interview.manage", "timesheet.view", "timesheet.approve", "leave.approve",
    ],
    "Partner": [
        "recruitment.view", "recruitment.manage", "employee.view", "employee.manage",
        "invoice.view", "invoice.approve", "reports.view", "reports.financial",
        "business_unit.view", "candidate.view", "candidate.create", "candidate.edit",
        "interview.manage", "timesheet.view", "timesheet.approve",
    ],
    "BU Head": [
        "recruitment.view", "recruitment.manage", "employee.view", "employee.manage",
        "reports.view", "business_unit.view", "candidate.view", "candidate.create",
        "candidate.edit", "interview.manage", "timesheet.view", "timesheet.approve",
    ],
    "Manager": [
        "employee.view", "employee.manage", "timesheet.view", "timesheet.approve",
        "reports.view", "candidate.view", "interview.manage", "leave.approve",
    ],
    "Recruiter": [
        "recruitment.view", "recruitment.manage", "candidate.view", "candidate.create",
        "candidate.edit", "interview.manage", "reports.view",
    ],
    "HR Manager": [
        "employee.view", "employee.manage", "reports.view", "candidate.view",
        "candidate.edit", "timesheet.view", "timesheet.approve", "leave.approve",
        "recruitment.view",
    ],
    "Finance": [
        "invoice.view", "invoice.approve", "payroll.manage", "reports.financial",
        "timesheet.view", "revenue.view_pnl",
    ],
}

# Field-Level Permissions (PII masking/hiding)
FIELD_PERMISSIONS = {
    # (role_name, table_name, field_name): access_level
    # CEO/CFO/Admin see everything unmasked
    # HR sees masked SSN
    # Finance sees some data
    # Others see limited/no PII

    # Recruiter - cannot see employee data
    ("Recruiter", "employees", "salary"): "hidden",
    ("Recruiter", "employees", "ssn"): "hidden",
    ("Recruiter", "employees", "bank_account"): "hidden",

    # HR Manager - can see masked SSN
    ("HR Manager", "employees", "ssn"): "masked",
    ("HR Manager", "employees", "salary"): "readonly",

    # Manager - can see own team salary
    ("Manager", "employees", "salary"): "readonly",
    ("Manager", "employees", "ssn"): "hidden",

    # Finance - can see salary, not employee names
    ("Finance", "employees", "salary"): "readonly",
    ("Finance", "employees", "ssn"): "readonly",
    ("Finance", "candidates", "phone"): "hidden",

    # Partner - full PII access
    ("Partner", "employees", "salary"): "editable",
    ("Partner", "employees", "ssn"): "editable",

    # BU Head - full PII access
    ("BU Head", "employees", "salary"): "editable",
    ("BU Head", "employees", "ssn"): "masked",
}

# Data Scope Permissions
DATA_SCOPE_PERMISSIONS = {
    # (role_name, module): scope_type
    # CEO/CFO/Admin: ORG_WIDE
    # Partner: MULTI_BU
    # BU Head/Recruiter/HR Manager: BU_ONLY
    # Manager: TEAM_ONLY
    # Finance: ORG_WIDE for financial data

    ("CEO", "candidates"): "ORG_WIDE",
    ("CEO", "employees"): "ORG_WIDE",
    ("CEO", "invoices"): "ORG_WIDE",

    ("CFO", "invoices"): "ORG_WIDE",
    ("CFO", "payroll"): "ORG_WIDE",

    ("Admin", "candidates"): "ORG_WIDE",
    ("Admin", "employees"): "ORG_WIDE",
    ("Admin", "invoices"): "ORG_WIDE",

    ("Partner", "candidates"): "MULTI_BU",
    ("Partner", "employees"): "MULTI_BU",
    ("Partner", "invoices"): "MULTI_BU",

    ("BU Head", "candidates"): "BU_ONLY",
    ("BU Head", "employees"): "BU_ONLY",
    ("BU Head", "invoices"): "BU_ONLY",

    ("Manager", "employees"): "TEAM_ONLY",
    ("Manager", "timesheets"): "TEAM_ONLY",

    ("Recruiter", "candidates"): "BU_ONLY",
    ("Recruiter", "jobs"): "BU_ONLY",
    ("Recruiter", "interviews"): "BU_ONLY",

    ("HR Manager", "candidates"): "BU_ONLY",
    ("HR Manager", "employees"): "BU_ONLY",
    ("HR Manager", "timesheets"): "BU_ONLY",

    ("Finance", "invoices"): "ORG_WIDE",
    ("Finance", "payroll"): "ORG_WIDE",
}


def init_permission_system(tenant_id: int = 1) -> None:
    """Initialize permission system tables and seed data"""
    db = SessionLocal()

    try:
        # Create tables (skip if already exist)
        print("Ensuring permission system tables exist...")
        try:
            Base.metadata.create_all(engine)
            print("✅ Tables created/verified")
        except Exception as e:
            print(f"⚠️  Table creation: {e}")
            print("⚠️  Continuing with data seeding (tables may already exist)")

        # Create permissions
        print("\nCreating permissions...")
        permissions_map = {}
        for perm_name, perm_config in PERMISSIONS_CONFIG.items():
            perm = DetailedPermission(
                tenant_id=tenant_id,
                name=perm_name,
                description=perm_config.get("description"),
                category=perm_config.get("category"),
                layer=perm_config.get("layer"),
                active=True
            )
            db.add(perm)
            db.flush()
            permissions_map[perm_name] = perm
        db.commit()
        print(f"✅ Created {len(permissions_map)} permissions")

        # Create job titles
        print("\nCreating job titles...")
        job_titles_map = {}
        job_titles_list = [
            {"name": "CEO", "description": "Chief Executive Officer"},
            {"name": "CFO", "description": "Chief Financial Officer"},
            {"name": "Partner", "description": "Partner"},
            {"name": "BU Head", "description": "Business Unit Head"},
            {"name": "Senior Manager", "description": "Senior Manager"},
            {"name": "Manager", "description": "Manager"},
            {"name": "Senior Recruiter", "description": "Senior Recruiter"},
            {"name": "Recruiter", "description": "Recruiter"},
            {"name": "HR Manager", "description": "HR Manager"},
            {"name": "Finance Manager", "description": "Finance Manager"},
        ]

        for job_title_config in job_titles_list:
            job_title = JobTitle(
                tenant_id=tenant_id,
                name=job_title_config["name"],
                description=job_title_config["description"],
                active=True
            )
            db.add(job_title)
            db.flush()
            job_titles_map[job_title_config["name"]] = job_title
        db.commit()
        print(f"✅ Created {len(job_titles_map)} job titles")

        # Assign permissions to roles
        print("\nAssigning permissions to roles...")
        for role_name, perm_names in ROLE_PERMISSIONS.items():
            # Find or create role
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                print(f"  ⚠️  Role '{role_name}' not found in database, skipping")
                continue

            # Assign permissions
            for perm_name in perm_names:
                if perm_name not in permissions_map:
                    print(f"  ⚠️  Permission '{perm_name}' not found, skipping")
                    continue

                role_perm = DetailedRolePermission(
                    role_id=role.id,
                    permission_id=permissions_map[perm_name].id
                )
                db.add(role_perm)

            db.commit()
            print(f"  ✅ {role_name}: Assigned {len(perm_names)} permissions")

        # Add field-level permissions
        print("\nAdding field-level permissions...")
        field_count = 0
        for (role_name, table_name, field_name), access_level in FIELD_PERMISSIONS.items():
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                continue

            field_perm = FieldPermission(
                tenant_id=tenant_id,
                role_id=role.id,
                table_name=table_name,
                field_name=field_name,
                access_level=access_level
            )
            db.add(field_perm)
            field_count += 1
        db.commit()
        print(f"✅ Added {field_count} field-level permission rules")

        # Add data scope permissions
        print("\nAdding data scope permissions...")
        scope_count = 0
        for (role_name, module), scope_type in DATA_SCOPE_PERMISSIONS.items():
            role = db.query(Role).filter(Role.name == role_name).first()
            if not role:
                continue

            scope_perm = DataScopePermission(
                tenant_id=tenant_id,
                role_id=role.id,
                module=module,
                scope_type=scope_type
            )
            db.add(scope_perm)
            scope_count += 1
        db.commit()
        print(f"✅ Added {scope_count} data scope permission rules")

        print("\n" + "="*60)
        print("✅ PERMISSION SYSTEM INITIALIZATION COMPLETE")
        print("="*60)
        print(f"✅ Created {len(permissions_map)} permissions")
        print(f"✅ Created {len(job_titles_map)} job titles")
        print(f"✅ Assigned permissions to {len(ROLE_PERMISSIONS)} roles")
        print(f"✅ Created {field_count} field-level rules")
        print(f"✅ Created {scope_count} data scope rules")

    except Exception as e:
        print(f"❌ Error initializing permission system: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    tenant_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    init_permission_system(tenant_id)
