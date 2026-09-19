"""CSRF token validation decorator for state-changing endpoints."""
from functools import wraps
from fastapi import HTTPException, Header
from app.core.csrf_protection import validate_csrf_token
from app.core.logging import logger

def require_csrf_token(func):
    """Decorator to require valid CSRF token on state-changing endpoints.
    
    Expects X-CSRF-Token header in request.
    Token must be valid, non-expired, and unused.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Extract CSRF token from kwargs (FastAPI passes headers as params)
        csrf_token = kwargs.get("x_csrf_token")
        
        if not csrf_token:
            logger.warning("[CSRF] Missing CSRF token on state-changing operation")
            raise HTTPException(
                status_code=403,
                detail="CSRF token required for this operation"
            )
        
        if not validate_csrf_token(csrf_token):
            logger.warning(f"[CSRF] Invalid or expired CSRF token: {csrf_token[:10]}...")
            raise HTTPException(
                status_code=403,
                detail="Invalid or expired CSRF token"
            )
        
        return func(*args, **kwargs)
    
    return wrapper
