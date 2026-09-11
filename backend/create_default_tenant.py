#!/usr/bin/env python
"""Create default tenant in app_schema."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(".env")
load_dotenv(".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    try:
        # Create tenant in app_schema
        conn.execute(text("""
            INSERT INTO app_schema.tenants (name, is_active)
            VALUES ('Default Tenant', true)
            ON CONFLICT DO NOTHING
        """))
        conn.commit()
        print("✓ Default tenant created in app_schema")

        # Verify
        result = conn.execute(text("SELECT id, name FROM app_schema.tenants"))
        for row in result:
            print(f"  Tenant {row[0]}: {row[1]}")
    except Exception as e:
        print(f"⚠ {str(e)[:100]}")
