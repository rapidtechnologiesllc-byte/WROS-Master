#!/usr/bin/env python
"""Check existing users and candidates."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

load_dotenv(".env")
load_dotenv(".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
inspector = inspect(engine)

print("\n=== USER TABLE SCHEMA ===")
cols = inspector.get_columns("users")
for col in cols[:5]:  # First 5 columns
    print(f"  {col['name']}: {col['type']}")

print("\n=== EXISTING USERS ===")
with engine.connect() as conn:
    result = conn.execute(text("SELECT \"UserEmail\", \"UserName\", \"UserRole\" FROM users LIMIT 5"))
    for row in result:
        print(f"  {row[0]} | {row[1]} | {row[2]}")

print("\n=== CANDIDATES ===")
with engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM candidates"))
    count = result.fetchone()[0]
    print(f"  Total: {count}")
    if count > 0:
        result = conn.execute(text("SELECT \"candidateEmail\", \"candidateFirstName\", \"upload_status\" FROM candidates LIMIT 3"))
        for row in result:
            print(f"    {row[0]} | {row[1]} | {row[2]}")

print("\n")
