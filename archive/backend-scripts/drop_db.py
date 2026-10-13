#!/usr/bin/env python3
"""Drop and recreate wros_dev database."""

import os
os.chdir(os.path.dirname(__file__))

from sqlalchemy import create_engine, text, event
from sqlalchemy.pool import StaticPool

# Connect to postgres (default database)
engine = create_engine(
    "postgresql://app_user:<local-db-password>@localhost:5432/postgres",
    poolclass=StaticPool,
    isolation_level="AUTOCOMMIT"
)

try:
    print("[DROP] Connecting to postgres...")
    with engine.connect() as conn:
        # First, terminate all connections to wros_dev
        print("[DROP] Terminating existing connections...")
        conn.execute(text("""
            SELECT pg_terminate_backend(pid) FROM pg_stat_activity
            WHERE datname = 'wros_dev' AND pid <> pg_backend_pid()
        """))
        # Give it a moment
        import time
        time.sleep(1)

        print("[DROP] Dropping wros_dev database if exists...")
        conn.execute(text("DROP DATABASE IF EXISTS wros_dev"))
        print("[DROP] Database dropped successfully")
except Exception as e:
    print(f"[DROP] Error: {e}")
    raise
finally:
    engine.dispose()

print("[DROP] Done - database ready for recreation on next backend startup")
