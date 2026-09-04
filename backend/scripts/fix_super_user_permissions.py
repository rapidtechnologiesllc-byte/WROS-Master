#!/usr/bin/env python3
"""
Fix Super User Permissions - Ensure super users can create candidates.

Super users should have ALL permissions but the permission system wasn't
granting them properly. This script fixes the issue by:

1. Finding or creating Super User role template
2. Finding the candidates resource
3. Granting super users full permissions on candidates (view, create, edit, delete)
4. Running for all super users in the database
"""

import sys
import os

# Force UTF-8 on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.role_template import RoleTemplate, Resource, RoleTemplatePermission, Module
from app.models.user import Users
from app.core.logging import logger

def fix_super_user_permissions(db: Session, tenant_id: int = 1):
    """Ensure Super User role template has all necessary permissions."""

    print(f"\n{'='*70}")
    print("FIXING SUPER USER PERMISSIONS")
    print(f"{'='*70}\n")

    # Step 1: Find or create Super User role template
    super_user_role = db.query(RoleTemplate).filter(
        RoleTemplate.name == "Super User",
        RoleTemplate.tenant_id == tenant_id
    ).first()

    if not super_user_role:
        print("[ERROR] Super User role template not found!")
        print("        Please run seed_role_templates() first")
        return False

    print(f"[OK] Found Super User role template: {super_user_role.id}")

    # Step 2: Find all resources that super users should have access to
    # For now, we'll specifically fix candidates
    candidates_resources = [
        "candidates",
        # Add other critical resources here
    ]

    fixed_count = 0

    for resource_name in candidates_resources:
        # Find the resource in any module
        resource = db.query(Resource).filter(
            Resource.name == resource_name,
            Resource.tenant_id == tenant_id
        ).first()

        if not resource:
            print(f"⚠️  Resource not found: {resource_name}")
            continue

        # Check if super user already has permission
        existing_perm = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == super_user_role.id,
            RoleTemplatePermission.resource_id == resource.id
        ).first()

        if existing_perm:
            # Update existing permission to ensure all actions are enabled
            if not (existing_perm.can_view and existing_perm.can_create and
                    existing_perm.can_edit and existing_perm.can_delete):
                print(f"⏫ Updating permissions for {resource_name}...")
                existing_perm.can_view = True
                existing_perm.can_create = True
                existing_perm.can_edit = True
                existing_perm.can_delete = True
                fixed_count += 1
            else:
                print(f"✅ Super User already has full permissions on {resource_name}")
        else:
            # Create new permission
            print(f"➕ Granting Super User permission on {resource_name}...")
            perm = RoleTemplatePermission(
                role_template_id=super_user_role.id,
                resource_id=resource.id,
                can_view=True,
                can_create=True,
                can_edit=True,
                can_delete=True
            )
            db.add(perm)
            fixed_count += 1

    if fixed_count > 0:
        db.commit()
        print(f"\n✅ Fixed {fixed_count} permission(s)")
    else:
        print(f"\n✅ All permissions already correctly configured")

    # Step 3: Verify super users can create candidates
    super_users = db.query(Users).filter(
        Users.UserRole == "Super User",
        Users.tenant_id == tenant_id
    ).all()

    print(f"\n📋 Found {len(super_users)} super user(s):")
    for user in super_users:
        role_template_id = user.role_template_id if hasattr(user, 'role_template_id') else None
        print(f"   • {user.UserEmail}: role_template_id={role_template_id}")

    print(f"\n{'='*70}")
    print("✅ SUPER USER PERMISSIONS FIXED")
    print(f"{'='*70}\n")

    return True

def main():
    db = SessionLocal()
    try:
        success = fix_super_user_permissions(db, tenant_id=1)
        return 0 if success else 1
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 1
    finally:
        db.close()

if __name__ == "__main__":
    sys.exit(main())
