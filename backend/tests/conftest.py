"""
Pytest configuration and shared fixtures for regression test suite.

POSTGRESQL ONLY - No SQLite fallback
"""

import pytest
import os
import logging
from sqlalchemy import create_engine, text, event, inspect
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# PostgreSQL ONLY configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:123@localhost:5432/wros_test"
)

# Enforce PostgreSQL
if "postgresql" not in DATABASE_URL:
    raise ValueError(
        "ERROR: Only PostgreSQL is supported for testing.\n"
        "Set DATABASE_URL=postgresql://postgres:PASSWORD@localhost:5432/wros_test\n"
        "SQLite testing is no longer permitted."
    )


def create_test_database():
    """Create fresh PostgreSQL test database"""
    try:
        # Connect to postgres default database with autocommit
        admin_url = "postgresql://postgres:123@localhost:5432/postgres"
        admin_engine = create_engine(admin_url)

        @event.listens_for(admin_engine, 'connect')
        def on_connect(dbapi_conn, connection_record):
            dbapi_conn.set_isolation_level(0)  # autocommit mode

        with admin_engine.connect() as conn:
            # Terminate any existing connections to wros_test
            try:
                conn.execute(text("""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = 'wros_test'
                    AND pid <> pg_backend_pid()
                """))
            except Exception:
                pass

            # Drop existing database
            try:
                conn.execute(text("DROP DATABASE IF EXISTS wros_test"))
            except Exception:
                pass

            # Create fresh database
            conn.execute(text("CREATE DATABASE wros_test"))
            print("✓ PostgreSQL: Created fresh wros_test database")

        admin_engine.dispose()
        return True

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"✗ FATAL: Cannot create PostgreSQL test database")
        print(f"  Error: {e}")
        print(f"  Ensure PostgreSQL is running on localhost:5432")
        print(f"  Set POSTGRES_PASSWORD environment variable if needed")
        raise


def verify_database_empty():
    """Verify test database has no tables before schema creation"""
    test_engine = create_engine(DATABASE_URL)
    inspector = inspect(test_engine)
    tables = inspector.get_table_names()
    test_engine.dispose()

    if tables:
        print(f"✗ ERROR: wros_test database has {len(tables)} tables before setup")
        print(f"  Tables: {tables[:5]}{'...' if len(tables) > 5 else ''}")
        raise RuntimeError("Test database not clean - schema already exists")

    print("✓ PostgreSQL: Verified wros_test database is empty")


def verify_models_loaded():
    """Verify all models are loaded into SQLAlchemy metadata"""
    from app.models.base import Base
    from app import models  # This triggers all model imports

    table_count = len(Base.metadata.tables)
    if table_count == 0:
        raise RuntimeError("No models registered in SQLAlchemy metadata!")

    print(f"✓ Verified {table_count} models loaded in SQLAlchemy metadata")


# Create test engine with PostgreSQL-specific settings
engine = create_engine(
    DATABASE_URL,
    # PostgreSQL connection pooling
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    echo=False,
    connect_args={
        "application_name": "wros_test_suite",
    }
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Setup PostgreSQL test database before any tests run"""
    from app.models.base import Base

    print("\n" + "="*70)
    print("REGRESSION TEST DATABASE SETUP (PostgreSQL Only)")
    print("="*70)

    # Step 1: Create fresh test database
    create_test_database()

    # Step 2: Verify it's empty
    verify_database_empty()

    # Step 3: Verify all models are loaded into Base.metadata
    verify_models_loaded()

    # Step 4: Create all tables from models
    print("Creating schema from SQLAlchemy models...")
    try:
        # Use checkfirst=True to check if tables already exist
        # This prevents errors when indexes already exist
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("✓ PostgreSQL: Schema created successfully")
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        # If schema creation still fails, try forcing a complete cleanup
        print(f"  Warning: create_all failed: {type(e).__name__}")
        print(f"  Attempting forced cleanup and retry...")
        try:
            # Drop all tables with CASCADE
            with engine.connect() as conn:
                conn.connection.set_isolation_level(0)
                conn.execute(text("DROP SCHEMA public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
                conn.connection.set_isolation_level(1)
            print("  Dropped and recreated public schema")

            # Try create_all again
            Base.metadata.create_all(bind=engine)
            print("✓ PostgreSQL: Schema created successfully (after cleanup)")
        except Exception as e2:
            logger.error(f"Error: {str(e2)}", exc_info=True)
            print(f"✗ FATAL: Cannot create schema: {e2}")
            raise

    # Step 5: Verify tables were created
    inspector = inspect(engine)
    table_count = len(inspector.get_table_names())
    if table_count == 0:
        raise RuntimeError("Schema creation reported success but no tables exist in database!")
    print(f"✓ PostgreSQL: {table_count} tables created")

    yield

    # Cleanup after all tests
    print("\nCleaning up test database...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("✓ PostgreSQL: Test tables dropped")
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        print(f"⚠ Warning during cleanup: {e}")

    engine.dispose()
    print("="*70 + "\n")


@pytest.fixture(scope="session")
def test_db_engine():
    """Return the PostgreSQL engine for tests"""
    return engine


@pytest.fixture
def db(test_db_engine) -> Session:
    """Get a PostgreSQL database session for a single test"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session):
    """Get a test client for FastAPI with PostgreSQL backend"""
    from app.core.database import get_db
    from app.main import app

    def override_get_db():
        return db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
