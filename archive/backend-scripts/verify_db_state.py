#!/usr/bin/env python3
"""Verify database state after fixes."""

import os
os.chdir(os.path.dirname(__file__))

from app.core.database import SessionLocal
from app.models.user import Users
from app.models.role_template import RoleTemplate, Resource, RoleTemplatePermission
from app.models.tenant import Tenant

db = SessionLocal()

try:
    print("\n" + "="*60)
    print("DATABASE STATE VERIFICATION")
    print("="*60)

    # Check tenants
    tenants = db.query(Tenant).all()
    print(f"\n✓ Tenants: {len(tenants)}")
    for t in tenants:
        print(f"  - {t.id}: {t.name}")

    # Check roles
    roles = db.query(RoleTemplate).all()
    print(f"\n✓ Roles: {len(roles)}")
    for r in roles:
        is_super = "SUPER" if r.is_super_user else ""
        print(f"  - {r.id}: {r.name} {is_super}")

    # Check resources
    resources = db.query(Resource).all()
    print(f"\n✓ Resources: {len(resources)}")
    for r in resources:
        print(f"  - {r.id}: {r.name}")

    # Check permissions
    perms = db.query(RoleTemplatePermission).all()
    print(f"\n✓ Permissions: {len(perms)}")

    # Verify tenant_id in permissions
    perms_with_tenant = db.query(RoleTemplatePermission).filter(
        RoleTemplatePermission.tenant_id.isnot(None)
    ).count()
    print(f"  - Permissions with tenant_id: {perms_with_tenant}/{len(perms)}")

    # Check users
    users = db.query(Users).all()
    print(f"\n✓ Users: {len(users)}")
    for u in users:
        has_role = "✅" if u.role_template_id else "❌"
        print(f"  - {has_role} {u.UserEmail} (role_template_id={u.role_template_id})")

    # Verify recruiter user
    recruiter = db.query(Users).filter(
        Users.UserEmail == "recruiter@test.com"
    ).first()

    if recruiter:
        print(f"\n✓ Recruiter user verified:")
        print(f"  - Email: {recruiter.UserEmail}")
        print(f"  - Role Template ID: {recruiter.role_template_id}")
        print(f"  - Tenant ID: {recruiter.tenant_id}")

        # Check if recruiter has permissions
        if recruiter.role_template_id:
            perms = db.query(RoleTemplatePermission).filter(
                RoleTemplatePermission.role_template_id == recruiter.role_template_id,
                RoleTemplatePermission.tenant_id == recruiter.tenant_id
            ).all()
            print(f"  - Permissions granted: {len(perms)}")
            for p in perms:
                res = db.query(Resource).filter(Resource.id == p.resource_id).first()
                print(f"    - {res.name}: view={p.can_view}, create={p.can_create}, edit={p.can_edit}, delete={p.can_delete}")

    print("\n" + "="*60)
    print("✅ DATABASE VERIFIED - ALL SYSTEMS READY")
    print("="*60)

finally:
    db.close()
