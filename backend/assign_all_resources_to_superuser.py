#!/usr/bin/env python
"""Assign all 84 resources to superuser with full permissions."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(".env")
load_dotenv(".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Get superuser role
    result = conn.execute(text("""
        SELECT id FROM role_templates WHERE name = 'Super User' AND tenant_id = 1
    """))
    row = result.fetchone()
    if not row:
        print("⚠ Superuser role not found. Creating...")
        conn.execute(text("""
            INSERT INTO role_templates
            (name, display_name, hierarchy_level, specialization, is_system, enabled, org_level_access, tenant_id)
            VALUES ('Super User', 'Super User (Full Access)', 17, 'Executive', true, true, true, 1)
        """))
        conn.commit()
        result = conn.execute(text("""
            SELECT id FROM role_templates WHERE name = 'Super User' AND tenant_id = 1
        """))
        row = result.fetchone()

    superuser_role_id = row[0]
    print(f"Superuser role ID: {superuser_role_id}\n")

    # Get all resources for tenant 1
    result = conn.execute(text("""
        SELECT id, name FROM resources WHERE tenant_id = 1
    """))
    resources = result.fetchall()
    print(f"Found {len(resources)} resources\n")

    # Assign all resources to superuser with full permissions
    assigned = 0
    for resource_id, resource_name in resources:
        try:
            conn.execute(text("""
                INSERT INTO role_template_permissions
                (role_template_id, resource_id, can_view, can_create, can_edit, can_delete)
                VALUES (:role_id, :resource_id, true, true, true, true)
                ON CONFLICT DO NOTHING
            """), {
                "role_id": superuser_role_id,
                "resource_id": resource_id,
            })
            conn.commit()
            assigned += 1
            if assigned % 10 == 0:
                print(f"  Assigned {assigned}/{len(resources)}...")
        except Exception as e:
            print(f"  ⚠ Error on {resource_name}: {str(e)[:50]}")

    print(f"\n✓ Assigned all {assigned} resources to superuser with full permissions")
