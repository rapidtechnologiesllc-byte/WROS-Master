#!/usr/bin/env python3
import logging
"""Setup superuser and role templates for development"""

import sys
import os
sys.path.insert(0, os.getcwd())

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.models.business_unit import BusinessUnit
from app.models.role_template import RoleTemplate, RoleTemplatePermission, Module, Resource
from app.models.user import Users
from uuid import uuid4
import datetime
import bcrypt

def hash_password(password):
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

db = SessionLocal()

try:
    print("=" * 80)
    print("SETUP: SUPERUSER AND ROLE TEMPLATES")
    print("=" * 80)

    # 1. Create Tenant
    print("\n[1] Setting up tenant...")
    tenant = db.query(Tenant).filter(Tenant.name == 'BlitzenX').first()
    if not tenant:
        tenant = Tenant(
            name='BlitzenX',
            is_active=True
        )
        db.add(tenant)
        db.commit()
        print(f"    Created Tenant: BlitzenX (ID: {tenant.id})")
    else:
        print(f"    Tenant exists: BlitzenX (ID: {tenant.id})")

    # 2. Create Business Units
    print("\n[2] Setting up business units...")
    bus_list = [
        ('NA', 'North America'),
        ('EU', 'Europe'),
        ('APAC', 'Asia Pacific')
    ]

    for code, display in bus_list:
        existing = db.query(BusinessUnit).filter(BusinessUnit.bu_code == code).first()
        if not existing:
            bu = BusinessUnit(
                name=code,
                display_name=display,
                bu_code=code,
                tenant_id=tenant.id,
                active=True
            )
            db.add(bu)
            db.commit()
            print(f"    Created: {code} - {display}")
        else:
            print(f"    Exists: {code} - {display}")

    # 3. Create Modules and Resources
    print("\n[3] Setting up modules and resources...")

    modules_config = [
        ('administration', 'Administration'),
        ('sales', 'Sales'),
        ('project_management', 'Project Management'),
        ('reporting', 'Reporting'),
        ('system', 'System'),
        ('executive_dashboards', 'Executive Dashboards'),
        ('engagement_communications', 'Engagement & Communications'),
    ]

    resource_names = ['view', 'create', 'edit', 'delete', 'manage']

    created_resources = {}

    for mod_code, mod_name in modules_config:
        # Create module
        existing_module = db.query(Module).filter(Module.name == mod_name).first()
        if not existing_module:
            module = Module(
                name=mod_name,
                display_name=mod_name,
                tenant_id=tenant.id,
                enabled=True
            )
            db.add(module)
            db.commit()
        else:
            module = existing_module

        print(f"    Module: {mod_name}")
        created_resources[mod_code] = []

        # Create resources
        for res_name in resource_names:
            existing_resource = db.query(Resource).filter(
                Resource.module_id == module.id,
                Resource.name == res_name
            ).first()

            if not existing_resource:
                resource = Resource(
                    module_id=module.id,
                    name=res_name,
                    display_name=res_name.capitalize(),
                    tenant_id=tenant.id,
                    enabled=True
                )
                db.add(resource)
                db.commit()
                created_resources[mod_code].append(resource.id)
            else:
                created_resources[mod_code].append(existing_resource.id)

    print(f"    Created {sum(len(r) for r in created_resources.values())} resources across {len(created_resources)} modules")

    # 4. Create SuperUser Role Template with ALL permissions
    print("\n[4] Creating SuperUser role template...")

    superuser_role = db.query(RoleTemplate).filter(
        RoleTemplate.name == 'SuperUser',
        RoleTemplate.tenant_id == tenant.id
    ).first()

    if not superuser_role:
        superuser_role = RoleTemplate(
            name='SuperUser',
            display_name='Super User',
            description='Full system access - all modules and resources enabled',
            tenant_id=tenant.id,
            is_system=True,
            enabled=True
        )
        db.add(superuser_role)
        db.commit()

        # Add all resource permissions to SuperUser role (all actions enabled)
        total_perms = 0
        for module_code, resource_ids in created_resources.items():
            for resource_id in resource_ids:
                perm = RoleTemplatePermission(
                    role_template_id=superuser_role.id,
                    resource_id=resource_id,
                    can_view=True,
                    can_create=True,
                    can_edit=True,
                    can_delete=True
                )
                db.add(perm)
                total_perms += 1
        db.commit()

        print(f"    Created SuperUser role template")
        print(f"    Assigned {total_perms} resource permissions (all actions enabled)")
    else:
        print(f"    SuperUser role template already exists")

    # 5. Create superuser@blitzenx.com user
    print("\n[5] Creating superuser@blitzenx.com user...")

    existing_user = db.query(Users).filter(Users.UserEmail == 'superuser@blitzenx.com').first()
    if not existing_user:
        password_hash = hash_password('SuperUser@123')

        # Get NA business unit
        na_bu = db.query(BusinessUnit).filter(
            BusinessUnit.bu_code == 'NA',
            BusinessUnit.tenant_id == tenant.id
        ).first()

        user = Users(
            UserID=str(uuid4()),
            UserName='Super User',
            UserEmail='superuser@blitzenx.com',
            UserPassword=password_hash,
            UserRole='SuperUser',
            role_template_id=superuser_role.id,
            business_unit_id=na_bu.id if na_bu else None,
            tenant_id=tenant.id
        )
        db.add(user)
        db.commit()
        print(f"    Created user: superuser@blitzenx.com")
        print(f"    Assigned role template: SuperUser")
    else:
        print(f"    User already exists: superuser@blitzenx.com")

    print("\n" + "=" * 80)
    print("SETUP COMPLETE!")
    print("=" * 80)
    print("\nSuperuser Credentials:")
    print("  Email: superuser@blitzenx.com")
    print("  Password: SuperUser@123")
    print("  Role Template: SuperUser (all modules/resources enabled)")
    print("\nYou can now login and create additional users/roles")

except Exception as e:
    logger.error(f"Error: {str(e)}", exc_info=True)
    logger.error(f"Error: {str(e)}", exc_info=True)
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
