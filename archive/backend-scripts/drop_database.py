#!/usr/bin/env python3
"""Drop the wros_dev database"""

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

try:
    # Connect to postgres database (not wros_dev)
    conn = psycopg2.connect(
        host='localhost',
        user='app_user',
        password='<local-db-password>',
        database='postgres'
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # Terminate all connections to wros_dev
    cur.execute("""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = 'wros_dev'
        AND pid != pg_backend_pid()
    """)

    # Drop the database
    cur.execute("DROP DATABASE IF EXISTS wros_dev")
    print("✅ Database wros_dev dropped successfully")

    conn.close()
except Exception as e:
    print(f"❌ Error: {e}")
