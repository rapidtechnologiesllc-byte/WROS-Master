#!/usr/bin/env python3
"""Initialize RBAC permissions, roles, and role assignments for all user types."""

import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from sqlalchemy import text

def init_rbac():
    """Initialize RBAC system with permissions and roles."""
    db = SessionLocal()

    try:
        print("[RBAC] Initializing permissions, roles, and assignments...")

        # Get or create tenant
        print("\n[1] Setting up tenant...")
        result = db.execute(text("SELECT id FROM tenants WHERE name = 'BlitzenX' LIMIT 1"))
        tenant = result.scalar()
        if not tenant:
            db.execute(text("INSERT INTO tenants (name, is_active) VALUES ('BlitzenX', 1)"))
            db.commit()
            result = db.execute(text("SELECT id FROM tenants WHERE name = 'BlitzenX' LIMIT 1"))
            tenant = result.scalar()
        print(f"    [OK] Tenant ID: {tenant}")

        # Create permissions
        print("\n[2] Creating permissions...")
        permissions_map = {
            "revenue.view_pnl": "View P&L and revenue reports",
            "revenue.view": "View revenue data",
            "candidate.view": "View candidates",
            "candidate.create": "Create candidates",
            "candidate.edit": "Edit candidates",
            "candidate.delete": "Delete candidates",
            "employee.view": "View employees",
            "employee.manage": "Manage employees",
            "recruitment.view": "View recruitment pipeline",
            "interview.manage": "Manage interviews",
            "business_unit.view": "View business unit",
            "business_unit.manage": "Manage business unit",
            "user.manage": "Manage users",
            "role.manage": "Manage roles",
            "reports.view": "View reports",
            "reports.financial": "View financial reports",
            "job.view": "View jobs",
            "job.create": "Create jobs",
            "project.manage": "Manage projects",
            "invoices.view": "View invoices",
            "invoices.manage": "Manage invoices",
            "system.manage": "System administration",
            "*.* ": "Super user - all permissions"
        }

        created_perms = 0
        for perm_name, perm_desc in permissions_map.items():
            result = db.execute(text("SELECT id FROM permissions WHERE name = :name"), {"name": perm_name})
            if not result.scalar():
                db.execute(
                    text("INSERT INTO permissions (name, description) VALUES (:name, :desc)"),
                    {"name": perm_name, "desc": perm_desc}
                )
                created_perms += 1
        db.commit()
        print(f"    [OK] Created {created_perms} permissions")

        # Create roles
        print("\n[3] Creating roles...")
        roles_map = {
            "Super User": "Full system access",
            "CEO": "CEO dashboard and FY progress",
            "CFO": "Finance and reporting",
            "Partner": "Partner management",
            "BU Head": "Business unit head",
            "HR Manager": "Human resources management",
            "HR": "HR support",
            "Recruitment Manager": "Recruitment pipeline",
            "Recruiter": "Candidate sourcing and interviews",
            "Hiring Manager": "Hiring decisions",
            "Employee": "Employee access",
            "Admin": "Administrative functions"
        }

        role_perms = {
            "Super User": ["*.*"],
            "CEO": ["revenue.view_pnl", "revenue.view", "reports.view", "reports.financial"],
            "CFO": ["revenue.view_pnl", "invoices.view", "invoices.manage", "reports.financial"],
            "Partner": ["business_unit.manage", "employee.manage", "candidate.view"],
            "BU Head": ["business_unit.view", "employee.manage", "recruitment.view", "reports.view"],
            "HR Manager": ["candidate.view", "candidate.edit", "employee.manage", "employee.view", "reports.view"],
            "HR": ["candidate.view", "candidate.edit", "candidate.create"],
            "Recruitment Manager": ["candidate.view", "candidate.create", "candidate.edit", "recruitment.view", "interview.manage"],
            "Recruiter": ["candidate.view", "candidate.create", "candidate.edit", "candidate.delete", "recruitment.view", "interview.manage", "job.view"],
            "Hiring Manager": ["candidate.view", "interview.manage", "recruitment.view", "reports.view"],
            "Employee": ["candidate.view"],
            "Admin": ["user.manage", "role.manage", "candidate.view", "candidate.create", "candidate.edit", "employee.manage", "employee.view", "business_unit.manage", "system.manage"],
        }

        created_roles = 0
        role_ids = {}
        for role_name, role_desc in roles_map.items():
            result = db.execute(text("SELECT id FROM roles WHERE name = :name"), {"name": role_name})
            role_id = result.scalar()
            if not role_id:
                db.execute(
                    text("INSERT INTO roles (name, description) VALUES (:name, :desc)"),
                    {"name": role_name, "desc": role_desc}
                )
                db.commit()
                result = db.execute(text("SELECT id FROM roles WHERE name = :name"), {"name": role_name})
                role_id = result.scalar()
                created_roles += 1
            role_ids[role_name] = role_id
        print(f"    [OK] Created {created_roles} roles")

        # Assign permissions to roles
        print("\n[4] Assigning permissions to roles...")
        assigned = 0
        for role_name, perm_names in role_perms.items():
            role_id = role_ids[role_name]
            for perm_name in perm_names:
                # Get permission ID
                result = db.execute(text("SELECT id FROM permissions WHERE name = :name"), {"name": perm_name})
                perm_id = result.scalar()
                if perm_id:
                    # Check if assignment already exists
                    result = db.execute(
                        text("SELECT id FROM role_permissions WHERE role_id = :role_id AND permission_id = :perm_id"),
                        {"role_id": role_id, "perm_id": perm_id}
                    )
                    if not result.scalar():
                        db.execute(
                            text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :perm_id)"),
                            {"role_id": role_id, "perm_id": perm_id}
                        )
                        assigned += 1
        db.commit()
        print(f"    [OK] Assigned {assigned} permissions to roles")

        # Assign CEO role to test users
        print("\n[5] Assigning CEO role to test users...")
        test_emails = ["am@blitzenx.com", "admin@blitzenx.com"]
        ceo_role_id = role_ids["CEO"]

        # Get or create default business unit
        result = db.execute(text("SELECT id FROM business_units WHERE bu_code = 'NA' AND tenant_id = :tenant_id"), {"tenant_id": tenant})
        bu_id = result.scalar()
        if not bu_id:
            db.execute(
                text("INSERT INTO business_units (name, bu_code, tenant_id, is_active) VALUES ('North America', 'NA', :tenant_id, 1)"),
                {"tenant_id": tenant}
            )
            db.commit()
            result = db.execute(text("SELECT id FROM business_units WHERE bu_code = 'NA' AND tenant_id = :tenant_id"), {"tenant_id": tenant})
            bu_id = result.scalar()

        assigned_users = 0
        for email in test_emails:
            # Get user ID
            result = db.execute(text("SELECT UserID FROM users WHERE UserEmail = :email"), {"email": email})
            user_id = result.scalar()
            if user_id:
                # Check if already assigned
                result = db.execute(
                    text("SELECT id FROM user_roles WHERE user_id = :user_id AND role_id = :role_id"),
                    {"user_id": user_id, "role_id": ceo_role_id}
                )
                if not result.scalar():
                    # Create UUID for user_roles.id
                    import uuid
                    db.execute(
                        text("INSERT INTO user_roles (id, user_id, role_id, business_unit_id) VALUES (:id, :user_id, :role_id, :bu_id)"),
                        {
                            "id": str(uuid.uuid4()),
                            "user_id": user_id,
                            "role_id": ceo_role_id,
                            "bu_id": bu_id
                        }
                    )
                    assigned_users += 1
                    print(f"    [OK] Assigned CEO role to {email}")
        db.commit()
        print(f"    [SUMMARY] {assigned_users} users assigned CEO role")

        print("\n[SUCCESS] RBAC initialization complete!")
        print(f"  Permissions created: {len(permissions_map)}")
        print(f"  Roles created: {len(roles_map)}")
        print(f"  Role-permission assignments: {assigned}")
        print(f"  Users assigned CEO role: {assigned_users}")
        print("\nYou can now test with CEO user:")
        for email in test_emails:
            print(f"  - {email} / Am@123 (or Admin@123)")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_rbac()
