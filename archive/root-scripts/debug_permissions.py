#!/usr/bin/env python3
import sys
sys.path.insert(0, "/dev/OnboardingModule-Backend")

from app.core.database import SessionLocal
from app.models.role_template import RoleTemplate, RoleTemplatePermission, Resource, Module
from app.models.user import Users, UserRole

db = SessionLocal()

# Get Finance Manager role
fm_role = db.query(RoleTemplate).filter(RoleTemplate.name == "Finance Manager").first()
print(f"Finance Manager Role ID: {fm_role.id if fm_role else 'NOT FOUND'}")

if fm_role:
    # Get all permissions for Finance Manager
    perms = db.query(RoleTemplatePermission).filter(
        RoleTemplatePermission.role_template_id == fm_role.id
    ).all()

    print(f"\nTotal Finance Manager Permissions: {len(perms)}")

    # Group by module
    modules = {}
    for perm in perms:
        res = db.query(Resource).filter(Resource.id == perm.resource_id).first()
        if res:
            mod = db.query(Module).filter(Module.id == res.module_id).first()
            if mod.name not in modules:
                modules[mod.name] = []
            modules[mod.name].append(res.name)

    print(f"\nModules with permissions:")
    for mod_name in sorted(modules.keys()):
        print(f"  {mod_name}: {len(modules[mod_name])} resources")

# Check Finance Manager test user
fm_user = db.query(Users).filter(Users.UserEmail == "finance_mgr@test.com").first()
if fm_user:
    print(f"\nFinance Manager User: {fm_user.UserID} ({fm_user.UserName})")

    # Get user roles
    user_roles = db.query(UserRole).filter(UserRole.user_id == fm_user.UserID).all()
    print(f"User Roles: {len(user_roles)}")
    for ur in user_roles:
        role = db.query(RoleTemplate).filter(RoleTemplate.id == ur.role_template_id).first()
        print(f"  - {role.name if role else 'UNKNOWN'}")

db.close()
