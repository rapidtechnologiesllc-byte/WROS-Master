#!/usr/bin/env python
"""Assign all 84 resources to superuser - using correct schema."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(".env")
load_dotenv(".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Check which schema has resources
    print("Checking schemas...")
    try:
        result = conn.execute(text("SELECT COUNT(*) FROM public.resources"))
        public_count = result.fetchone()[0]
        print(f"  public.resources: {public_count}")
    except:
        public_count = 0
        print(f"  public.resources: 0 (or doesn't exist)")

    try:
        result = conn.execute(text("SELECT COUNT(*) FROM app_schema.resources"))
        app_count = result.fetchone()[0]
        print(f"  app_schema.resources: {app_count}")
    except:
        app_count = 0
        print(f"  app_schema.resources: 0 (or doesn't exist)")

    # Use whichever has more resources
    schema = "app_schema" if app_count > public_count else "public"
    print(f"\n✓ Using schema: {schema}\n")

    # Get superuser role from correct schema
    result = conn.execute(text(f"""
        SELECT id FROM {schema}.role_templates WHERE name = 'Super User' AND tenant_id = 1
    """))
    row = result.fetchone()

    if not row:
        print("⚠ Creating superuser role...")
        conn.execute(text(f"""
            INSERT INTO {schema}.role_templates
            (name, display_name, hierarchy_level, specialization, is_system, enabled, org_level_access, tenant_id)
            VALUES ('Super User', 'Super User (Full Access)', 17, 'Executive', true, true, true, 1)
        """))
        conn.commit()
        result = conn.execute(text(f"""
            SELECT id FROM {schema}.role_templates WHERE name = 'Super User' AND tenant_id = 1
        """))
        row = result.fetchone()

    superuser_role_id = row[0]
    print(f"Superuser role ID: {superuser_role_id}\n")

    # Get all resources
    result = conn.execute(text(f"""
        SELECT id, name FROM {schema}.resources WHERE tenant_id = 1
    """))
    resources = result.fetchall()
    print(f"Found {len(resources)} resources\n")

    # Assign all to superuser
    for resource_id, resource_name in resources:
        try:
            conn.execute(text(f"""
                INSERT INTO {schema}.role_template_permissions
                (role_template_id, resource_id, can_view, can_create, can_edit, can_delete)
                VALUES (:role_id, :resource_id, true, true, true, true)
                ON CONFLICT DO NOTHING
            """), {
                "role_id": superuser_role_id,
                "resource_id": resource_id,
            })
            conn.commit()
        except Exception as e:
            print(f"⚠ {resource_name}: {str(e)[:50]}")

    print(f"✓ Superuser now has full access to all {len(resources)} resources!")
