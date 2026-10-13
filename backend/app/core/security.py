import os
from datetime import datetime, timedelta
from typing import Optional
import jwt
import bcrypt
from fastapi.security import HTTPBearer
import logging
from fastapi import HTTPException, status

ALGORITHM = "HS256"

# PRODUCTION SAFETY: JWT_SECRET MUST be set via environment variable
# No default fallback allowed - forces explicit configuration
SECRET_KEY = os.getenv("JWT_SECRET")
# Never print any part of the secret: these lines end up in log files and CI output
print(f"[SECURITY-INIT] JWT_SECRET {'set' if SECRET_KEY else 'NOT SET'}, length={len(SECRET_KEY) if SECRET_KEY else 0}")
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
    """Create JWT access token using HS256

    Real internal-user session tokens ("type": "user") MUST include both
    tenant_id and role_template_id, no fallback, no hardcoded default -
    every permission check downstream depends on these being accurate.

    Real candidate session tokens ("type": "candidate") MUST include
    tenant_id; candidates have no RBAC role template so role_template_id
    does not apply to them.

    Narrow-purpose tokens that carry no RBAC context at all (OAuth
    link-state nonces, candidate portal magic links, system-audit probe
    tokens, MFA-pending tokens are the "user"/"candidate" exception
    above, not this one) are identified by any other `type` value and are
    exempt from both checks - they're verified by their own specific
    claim (e.g. "msgraph_link") rather than by tenant/role context.
    """
    to_encode = data.copy()
    token_type = to_encode.get('type')

    if token_type == 'user':
        if 'tenant_id' not in to_encode or to_encode['tenant_id'] is None:
            raise ValueError("tenant_id is REQUIRED in token payload - cannot proceed without it")
        if 'role_template_id' not in to_encode or to_encode['role_template_id'] is None:
            raise ValueError("role_template_id is REQUIRED in token payload - cannot proceed without it")
    elif token_type == 'candidate':
        if 'tenant_id' not in to_encode or to_encode['tenant_id'] is None:
            raise ValueError("tenant_id is REQUIRED in token payload - cannot proceed without it")

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT refresh token using HS256 with longer expiration"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": int(expire.timestamp()), "type": "refresh"})
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

def require_role_template_permission(*permissions):
    """Stub: Role-template permission checker (returns pass-through dependency)"""
    from fastapi import Depends
    async def check_permission(current_user = Depends(lambda: None)):
        return current_user
    return Depends(check_permission)
