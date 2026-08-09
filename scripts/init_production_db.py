#!/usr/bin/env python
"""
Production Database Initialization Script

Initialize BlitzenX WROS database schema in production SQL Server.

Usage:
    # Set production DATABASE_URL in .env or environment
    python scripts/init_production_db.py

    # Or with explicit database URL
    DATABASE_URL="mssql+pyodbc://user:password@server/database?driver=ODBC+Driver+17+for+SQL+Server" \
    python scripts/init_production_db.py

WARNING: This script creates all tables from SQLAlchemy models.
For existing databases with data, use Alembic migrations instead:
    alembic upgrade head
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

# Load environment variables
load_dotenv()

def init_production_db():
    """Initialize production database with all tables from models."""

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set in environment or .env")
        sys.exit(1)

    print(f"Initializing database: {database_url.split('@')[0]}...")

    try:
        # Import all models to register them with Base
        from app.models.base import Base
        from app import models  # This imports all model modules

        # Create engine based on database type
        if "sqlite" in database_url:
            # SQLite: use StaticPool to avoid threading issues
            engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        elif "mssql" in database_url:
            # SQL Server: use QueuePool
            engine = create_engine(
                database_url,
                echo=False,
                pool_pre_ping=True,  # Test connections before using
            )
        elif "postgresql" in database_url:
            # PostgreSQL: use QueuePool with connection pooling
            engine = create_engine(
                database_url,
                echo=False,
                pool_pre_ping=True,
            )
        else:
            # Generic database
            engine = create_engine(database_url, echo=False)

        # Create all tables
        print("Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("[OK] Database initialized successfully")

        # Verify tables were created
        with engine.connect() as conn:
            inspector_query = "SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = 'dbo'" if "mssql" in database_url else "SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema != 'information_schema'"

            if "sqlite" in database_url:
                # SQLite: check master table
                result = conn.execute(text("SELECT COUNT(*) as table_count FROM sqlite_master WHERE type='table'"))
            else:
                result = conn.execute(text(inspector_query))

            row = result.fetchone()
            table_count = row[0] if row else 0
            print(f"[OK] {table_count} tables created")

        engine.dispose()
        print("\n[SUCCESS] Database initialization complete!")
        print("\nNext steps:")
        print("1. Verify database connectivity from your application")
        print("2. Run migrations if adding new schema: alembic upgrade head")
        print("3. Seed initial data if needed")

    except Exception as e:
        print(f"\n❌ Database initialization failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    init_production_db()
