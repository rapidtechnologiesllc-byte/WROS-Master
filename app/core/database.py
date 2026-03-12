# database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

load_dotenv()
# Build the SQL Server connection string
DATABASE_URL = os.getenv("DATABASE_URL")

# Create SQLAlchemy engine with optimized settings
engine = create_engine(
    DATABASE_URL,
    pool_size=5,              # Number of connections to keep in pool
    max_overflow=10,          # Extra connections if pool is full
    pool_pre_ping=False,      # Disabled: avoids a SELECT 1 round-trip to Azure on every checkout
    pool_recycle=1800,        # Recycle connections after 30 minutes
    echo=False,               # Set to True for SQL debugging
    fast_executemany=True,    # Improves bulk insert performance
    connect_args={
        "timeout": 10,        # Connection timeout in seconds
    },
)

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
    user = get_user(db, email)
    if not user:
        return False
    if not verify_password(password, user.UserPassword):
        return False
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
    