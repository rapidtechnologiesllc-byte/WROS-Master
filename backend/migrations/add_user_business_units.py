import logging
"""Migration to add user_business_units junction table for multi-BU assignment.

NOTE: This migration uses Alembic and PostgreSQL. SQLite is no longer supported.
Use Alembic for all database migrations: alembic upgrade head
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def upgrade():
    """Create the user_business_units table via Alembic.

    This script is deprecated. Use Alembic for migrations:
    $ alembic upgrade head
    """
    raise NotImplementedError(
        "This migration script is deprecated. "
        "Please use Alembic migrations instead: alembic upgrade head"
    )

def downgrade():
    """Drop the user_business_units table via Alembic.

    This script is deprecated. Use Alembic for migrations:
    $ alembic downgrade -1
    """
    raise NotImplementedError(
        "This migration script is deprecated. "
        "Please use Alembic migrations instead: alembic downgrade -1"
    )

if __name__ == "__main__":
    print("ERROR: This migration script is deprecated.")
    print("Use Alembic instead:")
    print("  $ alembic upgrade head")
    print("  $ alembic downgrade -1")
    sys.exit(1)
