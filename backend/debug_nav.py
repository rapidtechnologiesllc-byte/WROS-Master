#!/usr/bin/env python3
import sys
sys.path.insert(0, "/dev/OnboardingModule-Backend")

from app.core.database import SessionLocal
from app.models.role_template import RoleTemplate, Resource, Module
from app.models.user import Users
from app.services.role_template_permission_service import RoleTemplatePermissionService

db = SessionLocal()

# Get Finance Manager user
fm_user = db.query(Users).filter(Users.UserEmail == "finance_mgr@test.com").first()
print(f"Finance Manager: {fm_user.UserID} ({fm_user.UserName})")

# Get all resources
resources = db.query(Resource).filter(Resource.enabled == True, Resource.tenant_id == 1).all()
print(f"\nTotal resources in database: {len(resources)}")

# Get resources by module
modules_seen = {}
for resource in resources:
    can_view = RoleTemplatePermissionService.can_view(db, fm_user.UserID, resource.name, 1)
    if can_view:
        mod = db.query(Module).filter(Module.id == resource.module_id).first()
        if mod.name not in modules_seen:
            modules_seen[mod.name] = []
        modules_seen[mod.name].append(resource.name)

print(f"\nModules FM can see (via can_view):")
for mod_name in sorted(modules_seen.keys()):
    print(f"  {mod_name}: {len(modules_seen[mod_name])} resources")
    if len(modules_seen[mod_name]) <= 3:
        for res in modules_seen[mod_name][:3]:
            print(f"    - {res}")

# Check specific recruitment resources
print(f"\nCan FM view 'candidates'? {RoleTemplatePermissionService.can_view(db, fm_user.UserID, 'candidates', 1)}")
print(f"Can FM view 'invoices'? {RoleTemplatePermissionService.can_view(db, fm_user.UserID, 'invoices', 1)}")
print(f"Can FM view 'users'? {RoleTemplatePermissionService.can_view(db, fm_user.UserID, 'users', 1)}")

db.close()
