#!/usr/bin/env python
import logging
"""Create Recruiter role template with Recruitment module permissions."""

from app.core.database import SessionLocal
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission

db = SessionLocal()

try:
    # Get Recruitment module
    recruitment_module = db.query(Module).filter(
        Module.name == "Recruitment"
    ).first()

    if not recruitment_module:
        print("[ERROR] Recruitment module not found. Run init_role_template_system() first.")
        exit(1)

    # Get all Recruitment resources
    recruitment_resources = db.query(Resource).filter(
        Resource.module_id == recruitment_module.id
    ).all()

    if not recruitment_resources:
        print("[ERROR] No resources found in Recruitment module.")
        exit(1)

    print("[OK] Found {} Recruitment resources".format(len(recruitment_resources)))

    # Check if Recruiter template already exists
    existing = db.query(RoleTemplate).filter(
        RoleTemplate.name == "Recruiter"
    ).first()

    if existing:
        print("[INFO] Recruiter template already exists. Skipping creation.")
        print("\nExisting permissions:")
        perms = db.query(RoleTemplatePermission).filter(
            RoleTemplatePermission.role_template_id == existing.id
        ).all()
        for perm in perms:
            resource = db.query(Resource).filter(Resource.id == perm.resource_id).first()
            print("  - {}: V={} C={} E={} D={}".format(
                resource.display_name, perm.can_view, perm.can_create, perm.can_edit, perm.can_delete
            ))
        exit(0)

    # Create Recruiter role template
    recruiter_template = RoleTemplate(
        name="Recruiter",
        display_name="Recruiter",
        description="Recruiter role with full Recruitment module access",
        is_system=False,
        tenant_id=1,
        created_by="system"
    )
    db.add(recruiter_template)
    db.flush()

    print("[OK] Created Recruiter role template (ID: {})".format(recruiter_template.id))

    # Add permissions for all Recruitment resources (View, Create, Edit, Delete for all)
    for resource in recruitment_resources:
        perm = RoleTemplatePermission(
            role_template_id=recruiter_template.id,
            resource_id=resource.id,
            can_view=True,
            can_create=True,
            can_edit=True,
            can_delete=True
        )
        db.add(perm)
        print("  [OK] Added full permissions for: {}".format(resource.display_name))

    db.commit()
    print("\n[SUCCESS] Created Recruiter template with {} Recruitment resources".format(len(recruitment_resources)))
    print("\nPermissions summary:")
    print("  - All Recruitment screens: View=YES, Create=YES, Edit=YES, Delete=YES")

except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    db.rollback()
    print("[ERROR] Error: {}".format(str(e)))
    import traceback
    traceback.print_exc()
finally:
    db.close()
