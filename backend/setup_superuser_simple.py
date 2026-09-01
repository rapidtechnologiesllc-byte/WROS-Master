#!/usr/bin/env python3
"""Create superuser role template and user."""
import sys, os, uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from app.core.database import SessionLocal, engine
from app.models.base import Base
from app.models.user import Users
from app.models.tenant import Tenant
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.core.security import get_password_hash

Base.metadata.create_all(bind=engine, checkfirst=True)
db = SessionLocal()

try:
    tenant = db.query(Tenant).filter(Tenant.name == "BlitzenX").first()
    if not tenant:
        print("ERROR: Tenant not found. Run init_wros_db.py first.")
        sys.exit(1)

    # Get or create Super User role
    role = db.query(RoleTemplate).filter(
        RoleTemplate.name == "Super User",
        RoleTemplate.tenant_id == tenant.id
    ).first()

    if not role:
        print("Creating Super User role template...")
        role = RoleTemplate(
            id=str(uuid.uuid4()),
            name="Super User",
            description="Full system access",
            tenant_id=tenant.id,
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(role)
        db.flush()

        # Grant all permissions
        for resource in db.query(Resource).filter(Resource.tenant_id == tenant.id).all():
            for action in ['view', 'create', 'edit', 'delete']:
                perm = RoleTemplatePermission(
                    id=str(uuid.uuid4()),
                    role_template_id=role.id,
                    resource_id=resource.id,
                    action=action,
                    tenant_id=tenant.id
                )
                db.add(perm)
        print("✅ Super User role created")
    else:
        print("✅ Super User role exists")

    # Get or create superuser
    user = db.query(Users).filter(Users.UserEmail == "superuser@blitzenx.com").first()
    if not user:
        print("Creating superuser@blitzenx.com...")
        user = Users(
            UserID=str(uuid.uuid4()),
            UserEmail="superuser@blitzenx.com",
            UserPassword=get_password_hash("Superuser!123"),
            UserName="Super User",
            UserRole="Super User",
            job_title="Super User",
            role_template_id=role.id,
            tenant_id=tenant.id,
            mfa_enabled=False,
            CreatedAt=datetime.utcnow()
        )
        db.add(user)
        print("✅ Superuser created")
    else:
        user.role_template_id = role.id
        print("✅ Superuser role assigned")

    db.commit()
    print("\nSUCCESS!")
    print("Email:    superuser@blitzenx.com")
    print("Password: Superuser!123")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
    sys.exit(1)
finally:
    db.close()
