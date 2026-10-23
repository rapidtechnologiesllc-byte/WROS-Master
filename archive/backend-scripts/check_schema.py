#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect('postgresql://app_user:<local-db-password>@localhost:5432/wros_dev')
cur = conn.cursor()

# Check tables in app_schema
cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='app_schema'")
count = cur.fetchone()[0]
print(f'Tables in app_schema: {count}')

# List some tables
if count > 0:
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='app_schema' ORDER BY table_name LIMIT 20")
    tables = cur.fetchall()
    for t in tables:
        print(f'  - {t[0]}')

# Check if role_template table exists
cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='role_template' AND table_schema='app_schema'")
exists = cur.fetchone()[0]
print(f'\nRole Template Table Exists: {"YES" if exists else "NO"}')

# If tables exist, query them
if count > 0:
    try:
        cur.execute("SELECT COUNT(*) FROM app_schema.role_template")
        role_count = cur.fetchone()[0]
        print(f"Roles in database: {role_count}")
    except Exception as e:
        print(f"Error querying roles: {e}")

conn.close()
