import os
from datetime import datetime, timedelta
from typing import Optional
import jwt
import bcrypt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from fastapi import HTTPException, status

ALGORITHM = "HS256"

# PRODUCTION SAFETY: JWT_SECRET MUST be set via environment variable
# No default fallback allowed - forces explicit configuration
SECRET_KEY = os.getenv("JWT_SECRET")
print(f"[SECURITY-INIT] JWT_SECRET loaded: {SECRET_KEY[:20] if SECRET_KEY else 'NONE'}..., length={len(SECRET_KEY) if SECRET_KEY else 0}")
if not SECRET_KEY:
    raise ValueError(
        "🚨 FATAL: JWT_SECRET environment variable not set.\n"
        "Set it in .env file with a strong random string.\n"
        "Example: JWT_SECRET='your-secret-key-min-32-chars-required'\n"
        "This is CRITICAL for token signing and verification."
    )

ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7

security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token using HS256"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT refresh token using HS256 with longer expiration"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        raise ValueError("Operation failed")

def decode_access_token(token: str):
    """Decode JWT token for use in dependencies"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError as e:
        import logging
        logging.error(f"[JWT-ERROR] Token decode failed: {str(e)}, token_len={len(token)}, secret_len={len(SECRET_KEY) if SECRET_KEY else 0}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

def get_password_hash(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
