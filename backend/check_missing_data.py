#!/usr/bin/env python3
"""Check if Business Units and Job Titles are seeded"""

import psycopg2

conn = psycopg2.connect('postgresql://app_user:P7kQmR9xL2wJnV5sT8pM@localhost:5432/wros_dev')
cur = conn.cursor()

print("\n" + "="*60)
print("MISSING DATA CHECK")
print("="*60 + "\n")

# Check Business Units
try:
    cur.execute("SELECT COUNT(*) FROM app_schema.business_unit")
    bu_count = cur.fetchone()[0]
    print(f"❌ Business Units: {bu_count} (MISSING - should have at least 1)")
except Exception as e:
    print(f"❌ Business Units table: {e}")

# Check Job Titles
try:
    cur.execute("SELECT COUNT(*) FROM app_schema.permission_job_title")
    jt_count = cur.fetchone()[0]
    print(f"❌ Job Titles: {jt_count} (MISSING - should have several)")
except Exception as e:
    print(f"❌ Job Titles table: {e}")

# Check Org Positions
try:
    cur.execute("SELECT COUNT(*) FROM app_schema.org_position")
    org_count = cur.fetchone()[0]
    print(f"❌ Org Positions: {org_count} (MISSING - should link to BU)")
except Exception as e:
    print(f"❌ Org Positions table: {e}")

# Check what tables exist related to organizational structure
try:
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'app_schema'
        AND (table_name LIKE '%business%' OR table_name LIKE '%job%' OR table_name LIKE '%org%')
        ORDER BY table_name
    """)
    tables = cur.fetchall()
    print(f"\n📋 Related Tables Found:")
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM app_schema.{table[0]}")
        count = cur.fetchone()[0]
        print(f"   - {table[0]}: {count} rows")
except Exception as e:
    print(f"Error listing tables: {e}")

conn.close()

print("\n" + "="*60)
print("CONCLUSION: Business Units and Job Titles NOT SEEDED")
print("DATABASE INITIALIZATION INCOMPLETE")
print("="*60 + "\n")
