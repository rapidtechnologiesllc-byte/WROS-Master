"""CSRF Token Endpoint - Provides CSRF tokens for frontend state-changing requests."""
import logging
from fastapi import APIRouter, HTTPException
from app.core.csrf_protection import generate_csrf_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/csrf", tags=["CSRF"])

@router.get(
    "/token",
    summary="Get CSRF Token",
    description="Returns a fresh CSRF token for state-changing requests"
)
def get_csrf_token():
    """
    Get a fresh CSRF token for state-changing requests.

    Response:
        {
            "csrf_token": "token_value",
            "expires_in": 3600
        }
    """
    try:
        token = generate_csrf_token()
        return {
            "csrf_token": token,
            "token": token,  # Backward compatibility
            "expires_in": 3600
        }
    except Exception as e:
        logger.error(f"Failed to generate CSRF token: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate CSRF token")
