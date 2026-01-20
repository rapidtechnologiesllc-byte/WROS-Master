# security.py
from datetime import datetime, timedelta
import jwt
import bcrypt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
import os

# JWT Configuration - RS256 with RSA Keys
ALGORITHM = "RS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour

# Load RSA keys from environment variables
# Note: python-dotenv doesn't process \n escape sequences, so we need to manually convert them
# Also replace \r\n with \n because PEM format requires Unix line endings
PRIVATE_KEY = os.getenv("JWT_PRIVATE_KEY", "").replace("\\n", "\n").replace("\r\n", "\n")
PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "").replace("\\n", "\n").replace("\r\n", "\n")

if not PRIVATE_KEY or not PUBLIC_KEY:
    # Fallback to local files if environment variables are not set (optional, but good for local dev)
    import pathlib
    KEYS_DIR = pathlib.Path(__file__).parent / "keys"
    PRIVATE_KEY_PATH = KEYS_DIR / "private_key.pem"
    PUBLIC_KEY_PATH = KEYS_DIR / "public_key.pem"
    
    if PRIVATE_KEY_PATH.exists() and PUBLIC_KEY_PATH.exists():
        with open(PRIVATE_KEY_PATH, "r") as f:
            PRIVATE_KEY = f.read()
        with open(PUBLIC_KEY_PATH, "r") as f:
            PUBLIC_KEY = f.read()

# HTTP Bearer security scheme for JWT
security = HTTPBearer(
    scheme_name="JWT Authentication",
    description="Enter your JWT token obtained from /login (e.g., `your-token-here`)"
)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plain password against a hashed password.
    
    Args:
        plain: Plain text password
        hashed: Hashed password from database
        
    Returns:
        bool: True if password matches, False otherwise
    """
    # Convert strings to bytes for bcrypt
    plain_bytes = plain.encode('utf-8')
    hashed_bytes = hashed.encode('utf-8') if isinstance(hashed, str) else hashed
    return bcrypt.checkpw(plain_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
        
    Note:
        Bcrypt has a 72-byte password limit. Longer passwords are truncated.
    """
    # Bcrypt has a 72-byte limit, truncate if necessary
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Generate salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Return as string
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a JWT access token using RS256 algorithm.
    
    Args:
        data: Dictionary containing data to encode in token (e.g., {"sub": user_id})
        expires_delta: Optional custom expiration time
        
    Returns:
        str: Encoded JWT token signed with private key
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, PRIVATE_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT token using RS256 algorithm.
    
    Args:
        token: JWT token string
        
    Returns:
        dict: Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer credentials containing JWT token
        db: Database session
        
    Returns:
        User or Candidate object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    user_id: str = payload.get("sub")
    user_type: str = payload.get("type", "candidate")  # Default to candidate
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Import here to avoid circular dependency
    if user_type == "user":
        from model import Users
        user = db.query(Users).filter(Users.UserID == user_id).first()
    else:
        from model import Candidate
        user = db.query(Candidate).filter(Candidate.candidateID == user_id).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user


async def get_current_candidate(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated candidate from JWT token.
    Ensures the user is a candidate.
    
    Args:
        credentials: HTTP Bearer credentials containing JWT token
        db: Database session
        
    Returns:
        Candidate object
        
    Raises:
        HTTPException: If token is invalid, user not found, or not a candidate
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    user_id: str = payload.get("sub")
    user_type: str = payload.get("type")
    
    if not user_id or user_type != "candidate":
        raise HTTPException(status_code=403, detail="Not authorized as candidate")
    
    from model import Candidate
    candidate = db.query(Candidate).filter(Candidate.candidateID == user_id).first()
    
    if not candidate:
        raise HTTPException(status_code=401, detail="Candidate not found")
    
    return candidate


async def get_current_hr_or_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get the current authenticated HR or Admin user from JWT token.
    Ensures the user has HR or Admin role.
    
    Args:
        credentials: HTTP Bearer credentials containing JWT token
        db: Database session
        
    Returns:
        Users object with HR or Admin role
        
    Raises:
        HTTPException: If token is invalid, user not found, or not HR/Admin
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    user_id: str = payload.get("sub")
    user_type: str = payload.get("type")
    
    # Accept 'user', 'hr', or 'admin' types
    if not user_id or user_type not in ["user", "hr", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    from model import Users
    # For Microsoft SSO users, 'sub' contains email, not UserID
    user = db.query(Users).filter(Users.UserEmail == user_id).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    if user.UserRole.lower() not in ["hr", "admin"]:
        raise HTTPException(status_code=403, detail="Requires HR or Admin role")
    
    return user
