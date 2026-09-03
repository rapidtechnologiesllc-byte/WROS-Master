#!/usr/bin/env python3
"""
Complete database initialization script.
Properly initializes PostgreSQL schema and seed data.
"""
import os
import sys

os.environ['DATABASE_URL'] = os.getenv(
    'DATABASE_URL',
    'postgresql://postgres:123@localhost:5432/wros_dev'
)

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from app.core.security import get_password_hash

# Import all models to register them with Base
print("Importing models...")
try:
    from app.models.base import Base
    from app.models import *
    print("[OK] All models imported successfully")
except Exception as e:
    print(f"[ERROR] Failed to import models: {e}")
    sys.exit(1)

database_url = os.getenv('DATABASE_URL')
print(f"Connecting to: {database_url[:60]}...")

try:
    engine = create_engine(database_url)

    # Test connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("[OK] Database connection successful")

    # Create all tables
    print("Creating database schema from models...")
    Base.metadata.create_all(bind=engine)

    # Verify tables were created
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"[OK] Created {len(tables)} tables")

    if len(tables) == 0:
        print("[ERROR] ERROR: No tables were created. Models may not be properly defined.")
        sys.exit(1)

    # Create session for adding test data
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("\nCreating test users...")

        # Check if users already exist
        admin_exists = session.execute(
            text('SELECT 1 FROM "users" WHERE "UserEmail" = :email LIMIT 1'),
            {"email": "admin@blitzenx.com"}
        ).scalar()

        if not admin_exists:
            # Create test users
            admin_pwd = get_password_hash("Admin@123")
            super_pwd = get_password_hash("Superuser!123")

            session.execute(text('''
                INSERT INTO "users" ("UserID", "UserEmail", "UserName", "UserPassword", "UserRole", "role_template_id")
                VALUES (:id1, :email1, :name1, :pwd1, :role1, NULL),
                       (:id2, :email2, :name2, :pwd2, :role2, NULL)
            '''), {
                "id1": "uuid-admin-001",
                "email1": "admin@blitzenx.com",
                "name1": "Admin User",
                "pwd1": admin_pwd,
                "role1": "Admin",
                "id2": "uuid-super-001",
                "email2": "superuser@blitzenx.com",
                "name2": "SuperUser",
                "pwd2": super_pwd,
                "role2": "SuperUser"
            })
            session.commit()
            print("[OK] Test users created")
        else:
            print("[OK] Test users already exist")

        # Verify users
        users = session.execute(
            text('SELECT "UserEmail", "UserName" FROM "users" LIMIT 10')
        ).fetchall()

        print(f"\nUsers in database ({len(users)}):")
        for user in users:
            print(f"  - {user[0]}: {user[1]}")

        print("\n[OK] Database initialization complete!")
        print(f"[OK] Ready to login with:")
        print(f"  Email: admin@blitzenx.com")
        print(f"  Password: Admin@123")

    finally:
        session.close()

except Exception as e:
    print(f"[ERROR] Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    engine.dispose()
