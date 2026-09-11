#!/usr/bin/env python
"""Check database state for candidates and SLM data."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment configuration
load_dotenv(".env")
load_dotenv(".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

print("\n=== CANDIDATE DATABASE STATE ===\n")

with engine.connect() as conn:
    # Check candidate counts
    result = conn.execute(text("SELECT COUNT(*) as total FROM candidates"))
    total = result.fetchone()[0]
    print(f"Total candidates in DB: {total}")

    if total > 0:
        result = conn.execute(text("""
            SELECT upload_status, COUNT(*) as count
            FROM candidates
            GROUP BY upload_status
        """))
        statuses = result.fetchall()

        print(f"\nBy status:")
        for status, count in statuses:
            print(f"  {status}: {count}")

        # Check for data integrity
        result = conn.execute(text("""
            SELECT candidateID, candidateEmail, upload_status,
                   processing_completed_at, thunder_enabled
            FROM candidates
            ORDER BY candidateCreatedAt DESC
            LIMIT 5
        """))
        samples = result.fetchall()

        print(f"\nLatest 5 candidates:")
        for row in samples:
            print(f"  ID: {row[0][:8]}..., Email: {row[1]}")
            print(f"    Status: {row[2]}, Thunder: {row[4]}")
    else:
        print("\n⚠️ WARNING: No candidates in database!")

    # Check SLM data
    try:
        result = conn.execute(text("SELECT COUNT(*) FROM slm_decisions"))
        slm_count = result.fetchone()[0]
        print(f"\n=== SLM DATA ===")
        print(f"SLM decision records: {slm_count}")
    except Exception as e:
        print(f"\nSLM table check skipped: {str(e)[:50]}")

print("\n")
