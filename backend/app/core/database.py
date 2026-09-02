"""Database connection and session management.

Uses PostgreSQL exclusively. Database URL must be provided via DATABASE_URL
environment variable in .env or .env.local file.

Format: DATABASE_URL=postgresql://username:password@host:port/database_name
Example: DATABASE_URL=postgresql://postgres:password@localhost:5432/wros_dev
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.core.database_safety import validate_database_url, ProductionDatabaseError

# Load environment configuration
# Resolve .env relative to this file to handle different CWD scenarios
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(_REPO_ROOT, ".env"))
load_dotenv(os.path.join(_REPO_ROOT, ".env.local"), override=True)

# Get and validate database URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable not set. "
        "Set it in .env or .env.local file. "
        "Format: postgresql://username:password@host:port/database_name"
    )

# Log which database we're connecting to
import sys
print(f"[STARTUP] DATABASE_URL={DATABASE_URL[:70]}...", file=sys.stderr)
print(f"[STARTUP] Connecting to database...", file=sys.stderr)

# Allow SQLite for local development, PostgreSQL for production
if not (DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("sqlite://")):
    raise ValueError(
        f"Invalid DATABASE_URL: '{DATABASE_URL[:30]}...'. "
        "Only PostgreSQL (production) and SQLite (local dev) are supported. "
        "Format: postgresql://user:pass@host:port/db or sqlite:///path/to/db.sqlite3"
    )

# 🚨 SAFETY CHECK: Prevent production database access from local development
try:
    validate_database_url(DATABASE_URL)
except ProductionDatabaseError as e:
    raise RuntimeError(str(e)) from e

# PostgreSQL connection pool settings
_engine_kwargs = {
    "pool_pre_ping": True,      # Check connection health before use
    "echo": False,              # Set to True for SQL debugging
    "pool_size": 10,            # Keep 10 connections in pool
    "max_overflow": 20,         # Allow 20 extra connections if pool full
    "pool_recycle": 3600,       # Recycle connections after 1 hour
}

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, **_engine_kwargs)

# Configure schema for database
# PostgreSQL: use app_schema (app_user has privileges there)
# SQLite: no schema support, skip configuration
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    if "sqlite" not in DATABASE_URL.lower():
        # PostgreSQL only — tables are in public schema, use public first
        cursor = dbapi_conn.cursor()
        cursor.execute("SET search_path TO public, app_schema")
        cursor.close()

# SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    from app.core.security import verify_password
    from app.core.logging import logger
    import hashlib
    import bcrypt

    logger.warning(f"[AUTH] === START authenticate_user for email='{email}' ===")

    user = get_user(db, email)
    if not user:
        logger.warning(f"[AUTH] USER NOT FOUND: email='{email}'")
        return False

    logger.warning(f"[AUTH] USER FOUND: {user.UserEmail}, role={user.UserRole}")
    logger.warning(f"[AUTH] STORED HASH: {user.UserPassword}")

    # Log password metadata
    pwd_input_len = len(password)
    pwd_input_hash = hashlib.sha256(password.encode()).hexdigest()[:8]
    logger.warning(f"[AUTH] INPUT PASSWORD: len={pwd_input_len}, sha256_prefix={pwd_input_hash}")

    # Test bcrypt directly
    try:
        pwd_bytes = password.encode('utf-8')
        hash_bytes = user.UserPassword.encode('utf-8') if isinstance(user.UserPassword, str) else user.UserPassword
        bcrypt_result = bcrypt.checkpw(pwd_bytes, hash_bytes)
        logger.warning(f"[AUTH] BCRYPT DIRECT TEST: {bcrypt_result}")
    except Exception as e:
        logger.error(f"[AUTH] BCRYPT DIRECT TEST FAILED: {e}")

    # Test via verify_password function
    password_match = verify_password(password, user.UserPassword)
    logger.warning(f"[AUTH] verify_password() returned: {password_match}")

    if not password_match:
        logger.warning(f"[AUTH] === PASSWORD MISMATCH ===")
        return False

    logger.warning(f"[AUTH] === SUCCESS ===")
    return user

def get_candidate(db: Session, email: str):
    # Import here to avoid circular import
    from app.models import Candidate
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
    from app.models import Candidate
    return db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    