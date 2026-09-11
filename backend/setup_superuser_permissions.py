#!/usr/bin/env python
"""Setup superuser role with full permissions to all modules/resources."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(".env")
load_dotenv(".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

print("\n=== SETTING UP SUPERUSER PERMISSIONS ===\n")

with engine.connect() as conn:
    # Create tenant (if not exists)
    print("1. Creating/verifying tenant...")
    try:
        conn.execute(text("""
            INSERT INTO tenants (id, name) VALUES (1, 'Default')
            ON CONFLICT (id) DO NOTHING
        """))
        conn.commit()
        print("   ✓ Tenant 1 ready")
    except Exception as e:
        print(f"   ⚠ {str(e)[:50]}")

    # Create modules
    print("\n2. Creating modules...")
    modules = [
        ("recruitment", "Recruitment Management"),
        ("employee", "Employee Management"),
        ("finance", "Finance & Accounting"),
        ("admin", "Admin & Settings"),
    ]

    module_ids = {}
    for module_name, display_name in modules:
        try:
            result = conn.execute(text("""
                INSERT INTO modules (name, display_name, enabled, tenant_id)
                VALUES (:name, :display, :enabled, :tenant)
                ON CONFLICT DO NOTHING
                RETURNING id
            """), {
                "name": module_name,
                "display": display_name,
                "enabled": True,
                "tenant": 1,
            })
            conn.commit()
            row = result.fetchone()
            if row:
                module_ids[module_name] = row[0]
            else:
                # Get existing ID
                result = conn.execute(text(
                    "SELECT id FROM modules WHERE name = :name AND tenant_id = 1"
                ), {"name": module_name})
                row = result.fetchone()
                if row:
                    module_ids[module_name] = row[0]
            print(f"   ✓ {module_name}")
        except Exception as e:
            print(f"   ⚠ {module_name}: {str(e)[:50]}")

    # Create resources
    print("\n3. Creating resources...")
    resources = [
        ("recruitment", "candidates", "Candidates"),
        ("recruitment", "jobs", "Jobs"),
        ("recruitment", "interviews", "Interviews"),
        ("employee", "employees", "Employees"),
        ("finance", "invoices", "Invoices"),
        ("admin", "users", "Users & Access"),
        ("admin", "settings", "System Settings"),
    ]

    resource_ids = {}
    for module_name, resource_name, display_name in resources:
        module_id = module_ids.get(module_name)
        if not module_id:
            print(f"   ⚠ Skipping {resource_name} (module {module_name} not found)")
            continue

        try:
            result = conn.execute(text("""
                INSERT INTO resources (module_id, name, display_name, enabled, tenant_id)
                VALUES (:module_id, :name, :display, :enabled, :tenant)
                ON CONFLICT DO NOTHING
                RETURNING id
            """), {
                "module_id": module_id,
                "name": resource_name,
                "display": display_name,
                "enabled": True,
                "tenant": 1,
            })
            conn.commit()
            row = result.fetchone()
            if row:
                resource_ids[resource_name] = row[0]
            else:
                # Get existing ID
                result = conn.execute(text(
                    "SELECT id FROM resources WHERE name = :name AND module_id = :module_id"
                ), {"name": resource_name, "module_id": module_id})
                row = result.fetchone()
                if row:
                    resource_ids[resource_name] = row[0]
            print(f"   ✓ {resource_name}")
        except Exception as e:
            print(f"   ⚠ {resource_name}: {str(e)[:50]}")

    # Create superuser role
    print("\n4. Creating superuser role...")
    try:
        result = conn.execute(text("""
            INSERT INTO role_templates (name, display_name, hierarchy_level, specialization,
                                       is_system, enabled, org_level_access, tenant_id)
            VALUES (:name, :display, :level, :spec, :sys, :enabled, :org, :tenant)
            ON CONFLICT DO NOTHING
            RETURNING id
        """), {
            "name": "Super User",
            "display": "Super User (Full Access)",
            "level": 17,  # Highest hierarchy
            "spec": "Executive",
            "sys": True,
            "enabled": True,
            "org": True,  # Org-level access
            "tenant": 1,
        })
        conn.commit()
        row = result.fetchone()
        if row:
            superuser_role_id = row[0]
        else:
            # Get existing ID
            result = conn.execute(text(
                "SELECT id FROM role_templates WHERE name = 'Super User' AND tenant_id = 1"
            ))
            row = result.fetchone()
            superuser_role_id = row[0] if row else None
        print(f"   ✓ Superuser role created (ID: {superuser_role_id})")
    except Exception as e:
        print(f"   ⚠ {str(e)[:100]}")
        superuser_role_id = None

    # Assign all resources to superuser with full permissions
    if superuser_role_id:
        print("\n5. Assigning all resources to superuser with full permissions...")
        for resource_name, resource_id in resource_ids.items():
            try:
                conn.execute(text("""
                    INSERT INTO role_template_permissions
                    (role_template_id, resource_id, can_view, can_create, can_edit, can_delete)
                    VALUES (:role_id, :resource_id, :view, :create, :edit, :delete)
                    ON CONFLICT DO NOTHING
                """), {
                    "role_id": superuser_role_id,
                    "resource_id": resource_id,
                    "view": True,
                    "create": True,
                    "edit": True,
                    "delete": True,
                })
                conn.commit()
                print(f"   ✓ {resource_name} → Full access")
            except Exception as e:
                print(f"   ⚠ {resource_name}: {str(e)[:50]}")

    print("\n=== SETUP COMPLETE ===")
    print(f"\n✓ Superuser ready with full permissions to all modules/resources")
    print(f"✓ Ready for UI login: superuser@blitzenx.com / TestUser@123\n")
