#!/usr/bin/env python
"""Emergency fix: Migrate all tables to app_schema and fix user."""

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os, bcrypt

load_dotenv('.env')
load_dotenv('.env.local', override=True)

engine = create_engine(os.getenv('DATABASE_URL'))

print("\n=== MIGRATING TABLES TO app_schema ===\n")

tables = ['users', 'candidates', 'jobs', 'business_units', 'tenants', 'modules', 'resources', 'role_templates', 'role_template_permissions', 'clients']

with engine.connect() as conn:
    for table in tables:
        try:
            conn.execute(text(f'ALTER TABLE IF EXISTS public."{table}" SET SCHEMA app_schema'))
            conn.commit()
            print(f"  ✓ {table}")
        except Exception as e:
            print(f"  ⚠ {table}: {str(e)[:50]}")

print("\n=== FIXING USER PASSWORD ===\n")

pwd = bcrypt.hashpw(b'TestUser@123', bcrypt.gensalt()).decode()

with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO app_schema.users ("UserID", "UserEmail", "UserPassword", "UserName", "UserRole", "tenant_id")
        VALUES ('superuser@blitzenx.com', 'superuser@blitzenx.com', :pwd, 'Super User', 'SuperUser', 1)
        ON CONFLICT ("UserID") DO UPDATE SET "UserPassword" = :pwd
    """), {'pwd': pwd})
    conn.commit()
    print("✓ User ready in app_schema")

print("\n=== VERIFICATION ===\n")

with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM app_schema.users'))
    count = result.fetchone()[0]
    print(f"Users in app_schema: {count}")

    result = conn.execute(text('SELECT "UserEmail" FROM app_schema.users LIMIT 1'))
    row = result.fetchone()
    if row:
        print(f"Test user: {row[0]}")

print("\n✓ READY FOR LOGIN\n")
print("Email: superuser@blitzenx.com")
print("Password: TestUser@123\n")
