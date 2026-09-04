#!/usr/bin/env python3
from sqlalchemy import text
from app.core.database import engine
import logging
from app.models.base import Base

# Check database state
with engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"))
    table_count = result.scalar()
    print(f"Tables in database: {table_count}")

    if table_count > 0:
        print("Dropping all existing objects...")
        # Terminate connections
        conn.execute(text("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = current_database()
            AND pid <> pg_backend_pid()
        """))

        # Drop schema
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
        print("Schema dropped and recreated!")

print("Creating fresh schema from models...")
Base.metadata.create_all(bind=engine)
print("Schema created successfully!")
