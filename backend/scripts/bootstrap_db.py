#!/usr/bin/env python3
"""
Bootstrap database on fresh production deployment.

This script initializes a brand new database with:
1. All tables from SQLAlchemy models
2. Required tenants, modules, resources, roles, and users

Usage:
    python scripts/bootstrap_db.py

This is the ONLY way to initialize the database. Do NOT use Alembic migrations.
Alembic is deprecated and creates incomplete schema.
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.base import Base
from app.core.database import engine, SessionLocal
from app.core.db_contract import initialize_database
from app.core.logging import logger


def bootstrap_database():
    """Initialize database from scratch."""
    try:
        logger.info("[BOOTSTRAP] Starting database initialization...")

        # Step 1: Create all tables from models
        logger.info("[BOOTSTRAP] Step 1: Creating all tables from SQLAlchemy models...")
        from app import models  # Import all models to register with Base
        Base.metadata.create_all(bind=engine)
        logger.info("[BOOTSTRAP] OK: All tables created")

        # Step 2: Run database contract (tenant, RBAC, admin users)
        logger.info("[BOOTSTRAP] Step 2: Running database contract initialization...")
        initialize_database()
        logger.info("[BOOTSTRAP] OK: Database contract complete")

        logger.info("[BOOTSTRAP] SUCCESS: Database fully initialized and ready")
        return True

    except Exception as e:
        logger.error(f"[BOOTSTRAP] FAILED: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = bootstrap_database()
    sys.exit(0 if success else 1)
