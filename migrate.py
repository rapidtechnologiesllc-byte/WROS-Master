"""
Database migration utility that runs Alembic migrations programmatically.
This module is imported by main.py to automatically apply migrations on startup.
"""
import os
import sys
from alembic import command
from alembic.config import Config
from pathlib import Path


def run_migrations():
    """
    Run Alembic migrations to upgrade the database to the latest version.
    This function is called automatically when the application starts.
    """
    try:
        # Get the directory where this script is located
        base_dir = Path(__file__).parent
        
        # Path to alembic.ini
        alembic_ini_path = base_dir / "alembic.ini"
        
        if not alembic_ini_path.exists():
            print(f"Warning: alembic.ini not found at {alembic_ini_path}")
            return
        
        # Create Alembic configuration
        alembic_cfg = Config(str(alembic_ini_path))
        
        # Set the script location (alembic directory)
        alembic_cfg.set_main_option("script_location", str(base_dir / "alembic"))
        
        print("Running database migrations...")
        
        # Run the upgrade command to apply all pending migrations
        command.upgrade(alembic_cfg, "head")
        
        print("✓ Database migrations completed successfully")
        
    except Exception as e:
        error_msg = str(e)
        
        # Check if it's the foreign key constraint error
        if "is dependent on column" in error_msg or "FK__candidate" in error_msg:
            print("\n" + "="*60)
            print("⚠ Migration Error: Foreign Key Constraint Conflict")
            print("="*60)
            print("\nYour database has existing tables with old schema.")
            print("\nOptions to fix:")
            print("1. Reset database (DEVELOPMENT ONLY):")
            print("   python reset_database.py")
            print("\n2. Mark current schema as baseline:")
            print("   python stamp_baseline.py")
            print("\n3. Manually update your database schema")
            print("="*60)
        else:
            print(f"Error running migrations: {e}")
        
        print("\nThe application will continue, but database schema may be outdated.")
        # Don't exit - let the application start even if migrations fail


if __name__ == "__main__":
    # Allow running this script directly for testing
    run_migrations()
