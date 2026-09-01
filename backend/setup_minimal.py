#!/usr/bin/env python3
"""Minimal setup: Create tenant, modules, resources, and superuser."""
import sys, os, uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Users
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.core.security import get_password_hash

# Create all tables
print("[1] Creating database tables...")
Base.metadata.create_all(bind=engine, checkfirst=True)
print("    ✅ Tables created")

db = SessionLocal()

try:
    # Create or get tenant
    print("\n[2] Setting up tenant...")
    tenant = db.query(Tenant).filter(Tenant.name == "BlitzenX").first()
    if not tenant:
        tenant = Tenant(
            name="BlitzenX",
            is_active=True,
            default_timezone="Asia/Kolkata",
            default_date_format="MM/DD/YYYY",
            default_currency="USD"
        )
        db.add(tenant)
        db.commit()
        print("    ✅ Tenant created")
    else:
        print("    ✅ Tenant exists")

    tenant_id = tenant.id

    # Create modules
    print("\n[3] Creating modules...")
    modules_list = [
        "recruitment_management", "finance_revenue", "workforce_employees",
        "administration", "sales", "project_management", "reporting", "system",
        "executive_dashboards", "engagement_communications"
    ]

    for mod_name in modules_list:
        mod = db.query(Module).filter(Module.name == mod_name, Module.tenant_id == tenant_id).first()
        if not mod:
            mod = Module(
                name=mod_name,
                display_name=mod_name.replace("_", " ").title(),
                tenant_id=tenant_id
            )
            db.add(mod)
    db.commit()
    print(f"    ✅ Modules ready ({len(modules_list)} total)")

    # Create key resources
    print("\n[4] Creating resources...")
    resources_list = [
        ("recruitment_management", "candidates", "Candidates"),
        ("recruitment_management", "jobs", "Jobs"),
        ("recruitment_management", "interviews", "Interviews"),
        ("recruitment_management", "offers", "Offers"),
        ("administration", "users", "Users"),
        ("administration", "roles", "Roles"),
        ("administration", "business_units", "Business Units"),
        ("workforce_employees", "employees", "Employees"),
        ("finance_revenue", "invoices", "Invoices"),
        ("project_management", "projects", "Projects"),
    ]

    for mod_name, res_name, display_name in resources_list:
        res = db.query(Resource).filter(
            Resource.name == res_name,
            Resource.tenant_id == tenant_id
        ).first()
        if not res:
            mod = db.query(Module).filter(Module.name == mod_name, Module.tenant_id == tenant_id).first()
            if mod:
                res = Resource(
                    module_id=mod.id,
                    name=res_name,
                    display_name=display_name,
                    tenant_id=tenant_id
                )
                db.add(res)
    db.commit()
    print(f"    ✅ Resources ready ({len(resources_list)} created)")

    # Create Super User role template
    print("\n[5] Creating Super User role template...")
    role = db.query(RoleTemplate).filter(
        RoleTemplate.name == "Super User",
        RoleTemplate.tenant_id == tenant_id
    ).first()

    if not role:
        role = RoleTemplate(
            name="Super User",
            display_name="Super User",
            description="Full system access",
            tenant_id=tenant_id,
            enabled=True,
            created_at=datetime.utcnow()
        )
        db.add(role)
        db.flush()

        # Grant all permissions to all resources (view, create, edit, delete)
        # Note: RoleTemplatePermission uses can_view, can_create, can_edit, can_delete columns
        for resource in db.query(Resource).filter(Resource.tenant_id == tenant_id).all():
            perm = RoleTemplatePermission(
                role_template_id=role.id,
                resource_id=resource.id,
                can_view=True,
                can_create=True,
                can_edit=True,
                can_delete=True
            )
            db.add(perm)
        db.commit()
        print("    ✅ Super User role created with all permissions")
    else:
        print("    ✅ Super User role exists")

    # Create superuser
    print("\n[6] Creating superuser account...")
    user = db.query(Users).filter(Users.UserEmail == "superuser@blitzenx.com").first()

    if not user:
        user = Users(
            UserID=str(uuid.uuid4()),
            UserEmail="superuser@blitzenx.com",
            UserPassword=get_password_hash("Superuser!123"),
            UserName="Super User",
            UserRole="Super User",
            job_title="Super User",
            role_template_id=role.id,
            tenant_id=tenant_id,
            mfa_enabled=False,
            digest_enabled=True,
            thunder_enabled=True,
            CreatedAt=datetime.utcnow()
        )
        db.add(user)
        db.commit()
        print("    ✅ Superuser created")
    else:
        user.role_template_id = role.id
        db.commit()
        print("    ✅ Superuser role assigned")

    print("\n" + "="*60)
    print("✅ SETUP COMPLETE - Ready to login")
    print("="*60)
    print("\nCredentials:")
    print("  Email:    superuser@blitzenx.com")
    print("  Password: Superuser!123")
    print("  Role:     Super User (Full Access)")
    print("="*60 + "\n")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
    sys.exit(1)
finally:
    db.close()
