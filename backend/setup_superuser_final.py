#!/usr/bin/env python3
"""Create superuser role template and user account."""
import sys, os, uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Users
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.core.security import get_password_hash

Base.metadata.create_all(bind=engine, checkfirst=True)
db = SessionLocal()

try:
    # Get tenant
    print("[1] Getting tenant...")
    tenant = db.query(Tenant).filter(Tenant.name == "BlitzenX").first()
    if not tenant:
        raise Exception("Tenant 'BlitzenX' not found")
    print(f"    ✅ Tenant found (id={tenant.id})")

    tenant_id = tenant.id

    # Create Super User role template
    print("\n[2] Creating Super User role template...")
    role = db.query(RoleTemplate).filter(
        RoleTemplate.name == "Super User",
        RoleTemplate.tenant_id == tenant_id
    ).first()

    if not role:
        print("    Creating new Super User role...")
        role = RoleTemplate(
            name="Super User",
            display_name="Super User",
            description="Full system access - can manage all features",
            tenant_id=tenant_id,
            hierarchy_level=17,
            specialization="System Administration",
            enabled=True,
            is_system=True,
            created_at=datetime.utcnow()
        )
        db.add(role)
        db.flush()

        # Grant all permissions to all resources
        print("    Adding permissions...")
        for resource in db.query(Resource).filter(Resource.tenant_id == tenant_id).all():
            perm = RoleTemplatePermission(
                role_template_id=role.id,
                resource_id=resource.id,
                can_view=True,
                can_create=True,
                can_edit=True,
                can_delete=True,
                created_at=datetime.utcnow()
            )
            db.add(perm)

        db.commit()
        print(f"    ✅ Super User role created (id={role.id})")
    else:
        print(f"    ✅ Super User role already exists (id={role.id})")

    # Create or update superuser account
    print("\n[3] Creating/updating superuser account...")
    user = db.query(Users).filter(Users.UserEmail == "superuser@blitzenx.com").first()

    if not user:
        print("    Creating superuser@blitzenx.com...")
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
        print("    ✅ Superuser account created")
    else:
        print("    Updating superuser role template...")
        user.role_template_id = role.id
        db.commit()
        print("    ✅ Superuser account updated")

    print("\n" + "="*60)
    print("✅ SETUP COMPLETE")
    print("="*60)
    print("\nYou can now login with:")
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
