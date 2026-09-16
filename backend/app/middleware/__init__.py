"""
Middleware package for HRMS Onboarding Application.
Exports all middleware components for easy import.
"""
from app.middleware.auth_middleware import (
    AuthenticationMiddleware,
    RequestLoggingMiddleware,
    RateLimitMiddleware
)
import logging
from app.middleware.cors import setup_cors, get_cors_config, CORSConfig

__all__ = [
    "AuthenticationMiddleware",
    "RequestLoggingMiddleware",
    "RateLimitMiddleware",
    "setup_cors",
    "get_cors_config",
    "CORSConfig"
]
