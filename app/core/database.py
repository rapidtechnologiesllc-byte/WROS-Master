# database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Bare load_dotenv() resolves .env via the process's current working
# directory, not this file's location -- some launchers (e.g. this repo's
# dev-server preview registration) start uvicorn with an unrelated CWD,
# which silently produces DATABASE_URL=None here instead of a clear
# "file not found" error. Resolve relative to this file instead so the
# repo's own .env is always found regardless of launch CWD.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(_REPO_ROOT, ".env"))
# 2026-08-06, same override as app.core.config -- this module builds its
# own engine independently (separate from Settings.DATABASE_URL), so it
# needs its own .env.local load too, or a local SQLite override here
# would silently keep pointing at production. See CLAUDE.md's login-
# outage session log for why this matters.
load_dotenv(os.path.join(_REPO_ROOT, ".env.local"), override=True)
# Build the SQL Server connection string
DATABASE_URL = os.getenv("DATABASE_URL")

# fast_executemany and the pyodbc-style connect_args are SQL-Server-only
# (mssql+pyodbc) -- SQLite (used for local dev via .env.local, and for
# every test in this repo) doesn't accept either kwarg and raises
# TypeError on create_engine() if they're passed unconditionally.
_is_sqlserver = DATABASE_URL and DATABASE_URL.startswith("mssql")
_engine_kwargs = {
    "pool_pre_ping": False,   # Disabled: avoids a SELECT 1 round-trip to Azure on every checkout
    "echo": False,            # Set to True for SQL debugging
}
if _is_sqlserver:
    _engine_kwargs.update(
        pool_size=5,              # Number of connections to keep in pool
        max_overflow=10,          # Extra connections if pool is full
        pool_recycle=1800,        # Recycle connections after 30 minutes
        fast_executemany=True,    # Improves bulk insert performance
        connect_args={"timeout": 10},  # Connection timeout in seconds
    )

# Create SQLAlchemy engine with optimized settings
engine = create_engine(DATABASE_URL, **_engine_kwargs)

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
    return db.query(Candidate).filter(Candidate.candidateEmail == email).first()

def check_user(db: Session, email: str):
    # Import here to avoid circular import
    from app.models import Users
    return db.query(Users).filter(Users.UserEmail == email).first()

def get_user(db: Session, email: str):
    # Import here to avoid circular import
    from app.models import Users
    return db.query(Users).filter(Users.UserEmail == email).first()

def authenticate_user(db: Session, email: str, password: str):
    from app.core.security import verify_password
    from app.core.logging import logger

    user = get_user(db, email)
    if not user:
        logger.warning(f"[AUTH] authenticate_user: user not found for email='{email}'")
        return False

    password_match = verify_password(password, user.UserPassword)
    if not password_match:
        logger.warning(f"[AUTH] authenticate_user: password mismatch for email='{email}'")
        return False

    logger.info(f"[AUTH] authenticate_user: SUCCESS for email='{email}'")
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
    