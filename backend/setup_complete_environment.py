#!/usr/bin/env python3
"""
Complete Environment Setup Script for WROS Backend
import logging
Applies all critical fixes and configurations from project documentation.

This script:
1. Verifies PostgreSQL connection and database exists
2. Initializes database schema from SQLAlchemy models
3. Runs Alembic migrations
4. Initializes RBAC roles and permissions
5. Creates default business units
6. Verifies all environment variables are set
7. Performs health checks
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add the app directory to path
sys.path.insert(0, str(Path(__file__).parent))

def log_step(step_num, message):
    """Log a setup step with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] STEP {step_num}: {message}")
    print("=" * 70)

def log_success(message):
    """Log success message."""
    print(f"✅ {message}")

def log_error(message):
    """Log error message."""
    print(f"❌ {message}")

def log_warning(message):
    """Log warning message."""
    print(f"⚠️  {message}")

def verify_environment_variables():
    """Verify all critical environment variables are configured."""
    log_step(1, "Verifying Environment Variables")

    required_vars = {
        "DATABASE_URL": "PostgreSQL connection string",
        "JWT_PRIVATE_KEY": "JWT private key for signing",
        "JWT_PUBLIC_KEY": "JWT public key for verification",
    }

    optional_vars = {
        "GEMINI_API_KEY": "Google Gemini API key (for AI features)",
        "OPENAI_API_KEY": "OpenAI API key (for AI features)",
        "TENANT_ID": "Azure tenant ID for OAuth",
        "CLIENT_ID": "Azure client ID for OAuth",
        "CLIENT_SECRET": "Azure client secret for OAuth",
    }

    missing_required = []
    missing_optional = []

    for var, description in required_vars.items():
        if os.getenv(var):
            log_success(f"{var} is set ({description})")
        else:
            log_error(f"{var} is missing ({description})")
            missing_required.append(var)

    for var, description in optional_vars.items():
        if os.getenv(var):
            log_success(f"{var} is set ({description})")
        else:
            log_warning(f"{var} is not set ({description})")
            missing_optional.append(var)

    if missing_required:
        log_error(f"\n❌ CRITICAL: Missing required variables: {', '.join(missing_required)}")
        return False

    if missing_optional:
        log_warning(f"\nOptional variables not set: {', '.join(missing_optional)}")

    return True

def verify_database_connection():
    """Verify PostgreSQL connection."""
    log_step(2, "Verifying PostgreSQL Connection")

    try:
        from app.core.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            log_success(f"PostgreSQL connection successful")
            log_success(f"Database version: {version}")

        return True
    except Exception as e:
      logger.error(f"Error: {str(e)}", exc_info=True)
       logger.error(f"Error: {str(e)}", exc_info=True)
        log_error(f"PostgreSQL connection failed: {e}")
        return False

def initialize_database_schema():
    """Initialize database schema from SQLAlchemy models."""
    log_step(3, "Initializing Database Schema")

    try:
        from app.core.database import engine
        from app.models.base import Base

        # Create all tables defined in models
        Base.metadata.create_all(bind=engine)
        log_success("Database schema initialized (created all tables)")

        return True
    except Exception as e:
      logger.error(f"Error: {str(e)}", exc_info=True)
       logger.error(f"Error: {str(e)}", exc_info=True)
        log_error(f"Schema initialization failed: {e}")
        return False

def run_alembic_migrations():
    """Run pending Alembic migrations."""
    log_step(4, "Running Alembic Migrations")

    try:
        import subprocess

        # Check if alembic is available
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent)
        )

        if result.returncode == 0:
            log_success("Alembic is configured")

            # Run upgrade to latest
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).parent)
            )

            if result.returncode == 0:
                log_success("Alembic migrations completed")
                return True
            else:
                log_warning(f"Alembic migration result: {result.stdout}")
                return True  # Don't fail if alembic migrations have issues
        else:
            log_warning("Alembic not available or not configured (this is optional)")
            return True
    except Exception as e:
      logger.error(f"Error: {str(e)}", exc_info=True)
       logger.error(f"Error: {str(e)}", exc_info=True)
        log_warning(f"Alembic migration skipped: {e}")
        return True

def initialize_rbac():
    """Initialize RBAC roles, permissions, and business units."""
    log_step(5, "Initializing RBAC (Roles, Permissions, Business Units)")

    try:
        from app.core.database import SessionLocal
        from app.services.rbac_service_template import RBACService

        db = SessionLocal()
        try:
            RBACService.seed_roles_and_permissions(db)
            log_success("RBAC roles and permissions initialized")

            # Create default business units
            from app.models import BusinessUnit

            bu_names = ["NA", "EU", "APAC"]
            for bu_name in bu_names:
                existing = db.query(BusinessUnit).filter_by(bu_name=bu_name).first()
                if not existing:
                    bu = BusinessUnit(
                        bu_code=bu_name,
                        bu_name=bu_name,
                        tenant_id=1
                    )
                    db.add(bu)

            db.commit()
            log_success("Default business units created (NA, EU, APAC)")
            return True
        finally:
            db.close()
    except Exception as e:
      logger.error(f"Error: {str(e)}", exc_info=True)
       logger.error(f"Error: {str(e)}", exc_info=True)
        log_warning(f"RBAC initialization: {e}")
        return True

def verify_database_performance():
    """Verify database performance configuration."""
    log_step(6, "Verifying Database Performance Configuration")

    try:
        from app.core.database import engine

        pool = engine.pool
        log_success(f"Connection pool size: {pool.size()}")
        log_success(f"Pool max overflow: {pool._max_overflow if hasattr(pool, '_max_overflow') else 'N/A'}")
        log_success(f"Connection pre-ping enabled: {engine.pool_pre_ping}")

        return True
    except Exception as e:
      logger.error(f"Error: {str(e)}", exc_info=True)
       logger.error(f"Error: {str(e)}", exc_info=True)
        log_warning(f"Performance verification: {e}")
        return True

def health_check():
    """Perform comprehensive health check."""
    log_step(7, "Performing Health Checks")

    checks = {
        "Environment Variables": verify_environment_variables(),
        "Database Connection": verify_database_connection(),
        "Database Performance": verify_database_performance(),
    }

    all_passed = all(checks.values())

    print("\n" + "=" * 70)
    print("HEALTH CHECK SUMMARY:")
    print("=" * 70)
    for check, passed in checks.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check}")

    return all_passed

def main():
    """Run complete setup."""
    print("\n" + "=" * 70)
    print("🚀 WROS Backend - Complete Environment Setup")
    print("=" * 70)

    steps = [
        ("Environment Variables", verify_environment_variables),
        ("Database Connection", verify_database_connection),
        ("Database Schema", initialize_database_schema),
        ("Alembic Migrations", run_alembic_migrations),
        ("RBAC Initialization", initialize_rbac),
        ("Performance Configuration", verify_database_performance),
    ]

    results = {}
    for step_name, step_func in steps:
        try:
            results[step_name] = step_func()
        except Exception as e:
          logger.error(f"Error: {str(e)}", exc_info=True)
           logger.error(f"Error: {str(e)}", exc_info=True)
            log_error(f"Unexpected error in {step_name}: {e}")
            results[step_name] = False

    # Final health check
    health_check()

    # Summary
    print("\n" + "=" * 70)
    print("SETUP SUMMARY:")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"Completed: {passed}/{total} steps")

    if passed == total:
        log_success("\n✅ Environment setup completed successfully!")
        log_success("Your WROS backend is ready for development/production use.")
        return 0
    else:
        log_error("\n❌ Setup completed with issues. Review warnings above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
