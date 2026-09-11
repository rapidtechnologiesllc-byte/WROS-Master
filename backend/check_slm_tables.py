#!/usr/bin/env python
"""Check SLM table status and schema."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

load_dotenv(".env")
load_dotenv(".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

print("\n=== SLM TABLE STATUS ===\n")

inspector = inspect(engine)
tables = inspector.get_table_names()

print(f"Total tables in DB: {len(tables)}")

# Check for SLM tables
slm_tables = [t for t in tables if "slm" in t.lower()]
if slm_tables:
    print(f"\n✓ SLM tables found:")
    for table in slm_tables:
        print(f"\n  Table: {table}")
        columns = inspector.get_columns(table)
        print(f"  Columns: {len(columns)}")
        for col in columns[:5]:  # Show first 5
            print(f"    - {col['name']}: {col['type']}")
else:
    print(f"\n✗ No SLM tables found in database")

# List all tables for reference
print(f"\nAll {len(tables)} tables in DB:")
for table in sorted(tables):
    print(f"  - {table}")

print("\n")
