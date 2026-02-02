# security.py
from datetime import datetime, timedelta
import jwt
import bcrypt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
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


