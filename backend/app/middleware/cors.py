"""
CORS Middleware Configuration for HRMS Onboarding Application.
Handles Cross-Origin Resource Sharing for frontend applications.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from typing import List

from app.core.config import settings
from app.core.logging import logger

def setup_cors(app: FastAPI) -> None:
    """
    Configure CORS middleware for the FastAPI application.
    
    This allows the frontend application to make requests to the API
    from different origins (domains, ports, or protocols).
    
    Args:
        app: FastAPI application instance
    """
    # Get allowed origins from settings. NOTE: this was hardcoded to ["*"]
    # (wildcard) with allow_credentials=True below -- in combination,
    # starlette's CORSMiddleware echoes back whatever Origin header the
    # request sent whenever allow_origins is "*", so this let ANY website
    # make authenticated (cookie/Authorization-header) requests to this
    # API. Restored to the real, already-configured allowlist (includes
    # the production server's own origins) -- found and fixed as part of
    # pre-launch security hardening, not something that was ever supposed
    # to ship this way.
    allowed_origins = list(settings.CORS_ORIGINS)
    
    # Add additional origins from environment if specified
    import os
    env_origins = os.getenv("ADDITIONAL_CORS_ORIGINS", "")
    if env_origins:
        additional = [origin.strip() for origin in env_origins.split(",") if origin.strip()]
        allowed_origins.extend(additional)
    
    # Log CORS configuration
    logger.info(f"Configuring CORS with origins: {allowed_origins}")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,  # List of allowed origins
        allow_credentials=True,          # Allow cookies and authorization headers
        allow_methods=["*"],             # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
        allow_headers=["*"],             # Allow all headers
        expose_headers=[                 # Headers that can be accessed by frontend
            "Content-Length",
            "Content-Type",
            "X-Process-Time",
            "X-Request-ID"
        ],
        max_age=3600,                    # Cache preflight requests for 1 hour
    )
    
    logger.info("[OK] CORS middleware configured successfully")

def get_cors_config() -> dict:
    """
    Get the current CORS configuration as a dictionary.
    Useful for debugging and documentation.
    
    Returns:
        Dictionary containing CORS configuration
    """
    return {
        "allowed_origins": settings.CORS_ORIGINS,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
        "expose_headers": [
            "Content-Length",
            "Content-Type",
            "X-Process-Time",
            "X-Request-ID"
        ],
        "max_age": 3600
    }

logger = logging.getLogger(__name__)

class CORSConfig:
    """
    CORS configuration class for more granular control.
    Can be used for custom CORS setups.
    """
    
    # Development origins
    DEV_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    
    # Production origins (add your production frontend URLs here)
    PROD_ORIGINS = [
        # "https://hrms.blitzenx.com",
        # "https://hrms.blitzenx.com",
    ]
    
    # Staging origins
    STAGING_ORIGINS = [
        # "https://domain.com",
    ]
    
    @classmethod
    def get_allowed_origins(cls, environment: str = "development") -> List[str]:
        """
        Get allowed origins based on environment.
        
        Args:
            environment: Environment name (development, staging, production)
            
        Returns:
            List of allowed origins
        """
        if environment == "production":
            return cls.PROD_ORIGINS + cls.DEV_ORIGINS  # Allow dev for testing
        elif environment == "staging":
            return cls.STAGING_ORIGINS + cls.DEV_ORIGINS
        else:  # development
            return cls.DEV_ORIGINS
    
    @classmethod
    def is_origin_allowed(cls, origin: str, environment: str = "development") -> bool:
        """
        Check if an origin is allowed.
        
        Args:
            origin: Origin URL to check
            environment: Current environment
            
        Returns:
            True if origin is allowed, False otherwise
        """
        allowed = cls.get_allowed_origins(environment)
        return origin in allowed

# Preflight request handler
def add_cors_headers(response, origin: str = "*"):
    """
    Manually add CORS headers to a response.
    Useful for custom response handling.
    
    Args:
        response: FastAPI Response object
        origin: Allowed origin (default: *)
        
    Returns:
        Response with CORS headers added
    """
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    response.headers["Access-Control-Max-Age"] = "3600"
    
    return response
