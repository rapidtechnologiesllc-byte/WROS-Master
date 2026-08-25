#!/usr/bin/env python3
"""Initialize RBAC system for super user with full permissions"""

import os
os.environ['DATABASE_URL'] = 'postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/onboarding_prod?options=-csearch_path%3Dapp_schema'

from sqlalchemy import event, create_engine
from sqlalchemy.orm import sessionmaker
from app.models.role_template import RoleTemplate, Resource, RoleTemplatePermission, Module
from app.models.user import Users
from app.models.tenant import Tenant

engine = create_engine('postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/onboarding_prod')

@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("SET search_path TO app_schema")
    cursor.close()

SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    print("[RBAC] Initializing role templates and permissions for super user...")

    # Ensure tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == 1).first()
    if not tenant:
        tenant = Tenant(id=1, name="BlitzenX", is_active=True)
        db.add(tenant)
        db.commit()
        print("[OK] Tenant created")

    # Create Super Admin role template
    print("\n[1] Creating Super User role template...")
    super_admin_role = RoleTemplate(
        name="Super User",
        display_name="Super User",
        description="Full system access - all permissions on all resources",
        is_system=True,
        enabled=True,
        tenant_id=1,
        created_by="system"
    )
    db.add(super_admin_role)
    db.flush()
    super_admin_role_id = super_admin_role.id
    print(f"[OK] Super User role created (ID: {super_admin_role_id})")

    # Create Recruiter role template
    print("\n[2] Creating Recruiter role template...")
    recruiter_role = RoleTemplate(
        name="Recruiter",
        display_name="Recruiter",
        description="Recruitment staff - manage candidates and jobs",
        is_system=True,
        enabled=True,
        tenant_id=1,
        created_by="system"
    )
    db.add(recruiter_role)
    db.flush()
    recruiter_role_id = recruiter_role.id
    print(f"[OK] Recruiter role created (ID: {recruiter_role_id})")

    # Get or create modules
    print("\n[3] Getting or creating modules...")
    modules_data = [
        ("recruitment", "Recruitment", "Recruitment and hiring management"),
        ("hr", "Human Resources", "HR management and employee records"),
        ("admin", "Administration", "System administration and settings"),
    ]

    modules = {}
    for mod_code, mod_name, mod_desc in modules_data:
        m = db.query(Module).filter(Module.name == mod_code).first()
        if not m:
            m = Module(
                name=mod_code,
                display_name=mod_name,
                description=mod_desc,
                tenant_id=1
            )
            db.add(m)
            db.flush()
        modules[mod_code] = m

    db.commit()
    print(f"[OK] Got or created {len(modules)} modules")

    # Create resources under modules
    print("\n[4] Creating resources...")
    resources_data = [
        ("dashboard", "Dashboard", "Dashboard access", "admin"),
        ("candidate", "Candidates", "Candidate management", "recruitment"),
        ("job", "Jobs", "Job posting management", "recruitment"),
        ("interview", "Interviews", "Interview scheduling", "recruitment"),
        ("offer-letters", "Offer Letters", "Offer management", "recruitment"),
        ("employee", "Employees", "Employee records", "hr"),
        ("recruitment", "Recruitment", "Recruitment pipeline", "recruitment"),
        ("reports", "Reports", "Analytics and reports", "admin"),
        ("settings", "Settings", "System settings", "admin"),
        ("users", "Users", "User management", "admin"),
    ]

    resources = {}
    for res_code, res_name, res_desc, module_code in resources_data:
        r = Resource(
            name=res_code,
            display_name=res_name,
            description=res_desc,
            module_id=modules[module_code].id,
            tenant_id=1
        )
        db.add(r)
        resources[res_code] = r

    db.commit()
    print(f"[OK] Created {len(resources)} resources")

    # Assign ALL permissions to Super Admin role
    print("\n[5] Assigning all permissions to Super User role...")
    for resource in resources.values():
        perm = RoleTemplatePermission(
            role_template_id=super_admin_role_id,
            resource_id=resource.id,
            can_view=True,
            can_create=True,
            can_edit=True,
            can_delete=True
        )
        db.add(perm)

    # Assign recruiter permissions (view, create, edit on main resources)
    print("\n[6] Assigning permissions to Recruiter role...")
    for res_code in ["candidate", "job", "interview", "dashboard", "recruitment"]:
        resource = resources[res_code]
        perm = RoleTemplatePermission(
            role_template_id=recruiter_role_id,
            resource_id=resource.id,
            can_view=True,
            can_create=True,
            can_edit=True,
            can_delete=False
        )
        db.add(perm)

    db.commit()
    print("[OK] Permissions assigned")

    # Assign super user to Super Admin role
    print("\n[7] Assigning super user to Super User role...")
    super_user = db.query(Users).filter(Users.UserEmail == 'superuser@blitzenx.com').first()
    if super_user:
        if super_user.role_template_id == super_admin_role_id:
            print("[OK] Super user already assigned to Super User role")
        else:
            super_user.role_template_id = super_admin_role_id
            db.commit()
            print("[OK] Super user assigned to Super User role")
    else:
        print("[WARNING] Super user not found in database")

    # Assign recruiter to Recruiter role
    print("\n[8] Assigning recruiter to Recruiter role...")
    recruiter = db.query(Users).filter(Users.UserEmail == 'recruiter@test.com').first()
    if recruiter:
        if recruiter.role_template_id == recruiter_role_id:
            print("[OK] Recruiter already assigned to Recruiter role")
        else:
            recruiter.role_template_id = recruiter_role_id
            db.commit()
            print("[OK] Recruiter assigned to Recruiter role")
    else:
        print("[WARNING] Recruiter not found in database")

    print("\n" + "="*50)
    print("SUCCESS: RBAC system initialized!")
    print("="*50)
    print("\nTest credentials:")
    print("  Super User:  superuser@blitzenx.com / Superuser!123")
    print("  Recruiter:   recruiter@test.com / TestRecruiter@123")
    print("\nBoth users now have full navigation menu access!")

except Exception as e:
    print(f"\n[ERROR] {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
