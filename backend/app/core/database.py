import logging
"""Database connection and session management.

Uses PostgreSQL exclusively. Database URL must be provided via DATABASE_URL
environment variable in .env or .env.local file.

Format: DATABASE_URL=postgresql://username:password@host:port/database_name
Example: DATABASE_URL=postgresql://postgres:password@localhost:5432/wros_dev
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.core.database_safety import validate_database_url, ProductionDatabaseError

# Environment loading (.env, .env.local, and a test run's TEST_DATABASE_URL) lives in ONE
# place, app.core.config: importing it here is what loads it. A second copy of that logic
# here used to re-apply .env.local over a test run's database.
import app.core.config  # noqa: F401,E402

# Get and validate database URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable not set. "
        "Set it in .env or .env.local file. "
        "Format: postgresql://username:password@host:port/database_name"
    )

# Log which database we're connecting to (never the password: this lands
# in journald and CI logs)
import sys
from sqlalchemy.engine import make_url
SAFE_DATABASE_URL = make_url(DATABASE_URL).render_as_string(hide_password=True)
print(f"[STARTUP] DATABASE_URL={SAFE_DATABASE_URL}", file=sys.stderr)
print("[STARTUP] Connecting to database...", file=sys.stderr)

# 🚨 HARD RULE: PostgreSQL ONLY - Never allow SQLite
if not DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+psycopg2://"):
    raise ValueError(
        f"🚨 FATAL: Only PostgreSQL is supported. SQLite is NOT allowed in this codebase.\n"
        f"Invalid DATABASE_URL: '{DATABASE_URL[:50]}...'\n"
        f"Detected: {DATABASE_URL.split('://')[0] if '://' in DATABASE_URL else 'unknown'}\n"
        f"\n"
        f"REQUIRED FORMAT: postgresql://username:password@host:port/database_name\n"
        f"EXAMPLE: postgresql://postgres:password@localhost:5432/wros_dev\n"
        f"\n"
        f"SQLite causes data corruption and concurrency issues.\n"
        f"Use PostgreSQL exclusively for ALL environments (dev, test, prod).\n"
        f"\n"
        f"Fix: Set DATABASE_URL in .env or .env.local to a PostgreSQL connection string."
    )

# Additional safety check: reject file:// URLs (SQLite file paths)
if "sqlite://" in DATABASE_URL.lower() or "file://" in DATABASE_URL.lower():
    raise ValueError(
        f"🚨 FATAL: SQLite is NOT allowed in this codebase.\n"
        f"DATABASE_URL contains SQLite: {DATABASE_URL[:50]}...\n"
        f"\n"
        f"REQUIRED: Use PostgreSQL only\n"
        f"Format: postgresql://username:password@host:port/database_name"
    )

# 🚨 SAFETY CHECK: Prevent production database access from local development
try:
    validate_database_url(DATABASE_URL)
except ProductionDatabaseError as e:
    raise RuntimeError(str(e)) from e

# Pin the driver explicitly. A bare "postgresql://" leaves SQLAlchemy to pick
# a default dialect, and that default isn't stable across SQLAlchemy versions
# (2.1 resolves it to the psycopg v3 dialect, which isn't installed - only
# psycopg2-binary is, per requirements.txt). Without this, a fresh install on
# a new machine or in CI can fail to even start the app.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgresql://"):]

# PostgreSQL connection pool settings (FIX #15: Production-grade pooling)
# CRITICAL FIX (2026-09-21): Increased pool size to prevent stuck message monitor exhaustion
# Monitor runs every 10s and holds 8-10 connections. Old size (20) starved normal requests.
# New size (40) provides: 10 for normal requests + 10 for monitor + 10 buffer
_engine_kwargs = {
    "pool_pre_ping": True,      # Check connection health before use
    "echo": False,              # Set to True for SQL debugging
    "pool_size": 40,            # Keep 40 connections in pool (PRODUCTION) - increased from 20
    "max_overflow": 20,         # Allow 20 extra connections if pool full (PRODUCTION) - increased from 10
    "pool_recycle": 1800,       # Recycle connections after 30 minutes - changed from 3600 to detect stale faster
}

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, **_engine_kwargs)

# Configure schema, isolation level, and timeouts
# PostgreSQL: use app_schema (app_user has privileges there)
# SQLite: no schema support, skip configuration
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    if "sqlite" not in DATABASE_URL.lower():
        cursor = dbapi_conn.cursor()

        # Set schema search path - app_schema FIRST since all tables are there
        cursor.execute("SET search_path TO app_schema, public")

        # Every timestamp column is naive and the code compares against datetime.utcnow();
        # now() / server defaults follow the session time zone, so pin it to UTC. Without
        # this a non-UTC server (e.g. America/New_York) shifts every time window by its offset.
        cursor.execute("SET TIME ZONE 'UTC'")

        # Transaction isolation: READ COMMITTED (default PostgreSQL level)
        # Prevents dirty reads and lost updates while allowing more concurrency than SERIALIZABLE
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")

        # Statement timeout: 30 seconds (prevent runaway queries)
        cursor.execute("SET statement_timeout = '30s'")

        # Lock timeout: 5 seconds (fail fast if can't acquire lock)
        cursor.execute("SET lock_timeout = '5s'")

        cursor.close()

# SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# CRITICAL FIX #11: Verify database migrations applied at startup
def _verify_migrations():
    """Verify required columns exist (migration check) - database-agnostic using SQLAlchemy"""
    from app.core.logging import logger
    try:
        from sqlalchemy import inspect as sqlalchemy_inspect

        inspector = sqlalchemy_inspect(engine)
        if not inspector.has_table('channel_queue_item', schema='app_schema'):
            logger.warning("[MIGRATION] CRITICAL: channel_queue_item table not found")
            return False

        existing_columns = {col['name'] for col in inspector.get_columns('channel_queue_item', schema='app_schema')}
        required = {'handler_duration_ms', 'scheduled_for', 'idempotency_key'}
        missing = required - existing_columns

        if missing:
            logger.warning(f"[ALERT] MIGRATION MISSING: {missing}. Run migrations to add these columns")
            return False
        logger.info("[OK] Database migrations verified")
        return True
    except Exception as e:
        logger.warning(f"Migration verification failed (non-blocking): {e}")
        return True  # Don't fail startup

_verify_migrations()

def get_db():
    """
    Dependency for database session.

    Yields:
        Session: Database session for the request
    """
    from app.core.logging import logger

    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        # Log but re-raise - let FastAPI handle the error
        logger.error(f"Database error in endpoint: {str(e)}", exc_info=True)
        raise
    finally:
        # Always close the session, even if an error occurred
        try:
            db.close()
        except Exception as e:
            logger.warning(f"Error closing database session: {str(e)}")

def check_candidate(db: Session, email: str):
    # Import here to avoid circular import
    from app.models import Candidate
    from sqlalchemy import func
    return db.query(Candidate).filter(func.lower(Candidate.candidateEmail) == email.lower()).first()

def check_user(db: Session, email: str):
    # Import here to avoid circular import
    from app.models import Users
    from sqlalchemy import func
    return db.query(Users).filter(func.lower(Users.UserEmail) == email.lower()).first()

def get_user(db: Session, email: str):
    # Import here to avoid circular import
    from app.models import Users
    from sqlalchemy import func
    return db.query(Users).filter(func.lower(Users.UserEmail) == email.lower()).first()

def authenticate_user(db: Session, email: str, password: str):
    """The user for this email and password, or False. A deactivated user (terminated_at set)
    can't sign in. Never logs the password, a hash of it, or the stored hash."""
    from app.core.security import verify_password
    from app.core.logging import logger

    user = get_user(db, email)
    if not user:
        logger.info("[AUTH] Sign-in refused: unknown email")
        return False
    if not verify_password(password, user.UserPassword):
        logger.info(f"[AUTH] Sign-in refused: wrong password for {user.UserID}")
        return False
    if user.terminated_at is not None:
        logger.info(f"[AUTH] Sign-in refused: {user.UserID} is deactivated")
        return False
    return user

def get_candidate(db: Session, email: str):
    from app.models.candidate import Candidate
    return db.query(Candidate).filter(Candidate.candidateEmail == email).first()

def hash_candidate_password(password: str) -> str:
    """
    Hash a candidate password using bcrypt.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        str: Hashed password
    """
    from app.core.security import get_password_hash
    return get_password_hash(password)

def authenticate_candidate(db: Session, email: str, password: str):
    """
    Authenticate a candidate with email and password.
    
    Args:
        db: Database session
        email: Candidate email
        password: Plain text password
        
    Returns:
        Candidate object if authentication successful, False otherwise
    """
    from app.core.security import verify_password

    candidate = get_candidate(db, email)
    if not candidate:
        return False
    if not verify_password(password, candidate.candidatePassword):
        return False
    return candidate

def get_candidate_details_by_id(db: Session, candidate_id: str):
    """
    Get candidate details by candidate ID.
    
    Args:
        db: Database session
        candidate_id: Candidate ID (string)
        
    Returns:
        Candidate object if found, None otherwise
    """
    # Import here to avoid circular import
    from app.models.candidate import Candidate
    return db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    