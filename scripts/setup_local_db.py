"""DEPRECATED: SQLite local database setup is no longer supported.

This script was used to build local SQLite databases for development.
SQLite has been completely replaced with PostgreSQL as the production
database engine.

For local development setup:

1. Ensure PostgreSQL is running:
   $ psql -U postgres

2. Ensure DATABASE_URL is set in .env.local:
   DATABASE_URL=postgresql://postgres:123@localhost:5432/wros_dev

3. Run database migrations:
   $ alembic upgrade head

4. (Optional) Seed test data via API:
   $ python -m app.api.v1 --seed-test-data

For details, see:
- DEVELOPER_ONBOARDING.md - Local dev environment setup
- DEPLOYMENT_NOTES.md - Production deployment
- POSTGRESQL_MIGRATION.md - Database migration guide
"""

import sys

if __name__ == "__main__":
    print("ERROR: This script is deprecated.")
    print()
    print("SQLite is no longer supported. Use PostgreSQL instead.")
    print()
    print("Setup:")
    print("  1. Ensure DATABASE_URL=postgresql://... in .env.local")
    print("  2. Run: alembic upgrade head")
    print()
    sys.exit(1)
