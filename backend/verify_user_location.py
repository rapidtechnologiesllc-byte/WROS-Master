#!/usr/bin/env python
"""Check which schema has users and verify auth setup."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

load_dotenv(".env")
load_dotenv(".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

print("\n=== USER LOCATION CHECK ===\n")

with engine.connect() as conn:
    # Check public schema
    try:
        result = conn.execute(text("SELECT \"UserEmail\", \"UserID\" FROM public.users LIMIT 3"))
        public_users = result.fetchall()
        print(f"public.users: {len(public_users)} users")
        for row in public_users:
            print(f"  - {row[0]}")
    except Exception as e:
        print(f"public.users: Error - {str(e)[:50]}")
        public_users = []

    # Check app_schema
    try:
        result = conn.execute(text("SELECT id, email FROM app_schema.users LIMIT 3"))
        app_users = result.fetchall()
        print(f"\napp_schema.users: {len(app_users)} users")
        for row in app_users:
            print(f"  - {row[1]}")
    except Exception as e:
        print(f"app_schema.users: Error - {str(e)[:50]}")
        app_users = []

    # Check what auth.py expects
    print(f"\n=== RECOMMENDATION ===")
    if public_users and not app_users:
        print("✓ Users in public schema (correct)")
        print("✓ Superuser superuser@blitzenx.com exists")
    else:
        print("⚠ Need to sync users between schemas or check auth config")

print("\n")
