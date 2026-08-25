"""
Production Database Safety Guard

Prevents accidental connections to production databases from local development.
Raises errors if production credentials are detected outside of CI/CD environment.
"""

import os
import sys
from typing import Optional


class ProductionDatabaseError(Exception):
    """Raised when production database is accessed outside production environment."""
    pass


def is_production_database(database_url: str) -> bool:
    """Check if the database URL points to production."""
    if not database_url:
        return False

    url_lower = database_url.lower()

    # Production database indicators
    prod_indicators = [
        "onboarding_prod",
        "prod.",
        "production",
        ".prod",
        "prod-db",
        "vps.",
        "remote",
    ]

    return any(indicator in url_lower for indicator in prod_indicators)


def is_local_database(database_url: str) -> bool:
    """Check if the database URL is a local development database."""
    if not database_url:
        return False

    url_lower = database_url.lower()

    # Local database indicators
    local_indicators = [
        "localhost",
        "127.0.0.1",
        "wros_dev",
        "wros_test",
        ".sqlite",
    ]

    return any(indicator in url_lower for indicator in local_indicators)


def get_environment() -> str:
    """
    Get current environment.

    Returns:
        'production', 'staging', 'development', or 'local'
    """
    env = os.getenv("ENVIRONMENT", "").lower()

    if env in ("production", "prod"):
        return "production"
    elif env in ("staging", "stage"):
        return "staging"
    elif env in ("development", "dev"):
        return "development"
    else:
        return "local"


def validate_database_url(database_url: Optional[str] = None) -> str:
    """
    Validate that database URL matches the current environment.

    Args:
        database_url: Database connection URL. If None, uses DATABASE_URL env var.

    Returns:
        Validated database URL

    Raises:
        ProductionDatabaseError: If production DB detected in non-production environment
        RuntimeError: If database URL not configured
    """
    if database_url is None:
        database_url = os.getenv("DATABASE_URL", "").strip()

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL not configured.\n"
            "Set DATABASE_URL environment variable to proceed."
        )

    environment = get_environment()

    # Check for production database in non-production environment
    if is_production_database(database_url) and environment != "production":
        raise ProductionDatabaseError(
            f"\n{'=' * 80}\n"
            f"🚨 PRODUCTION DATABASE DETECTED IN {environment.upper()} ENVIRONMENT!\n"
            f"{'=' * 80}\n\n"
            f"Database URL: {database_url}\n"
            f"Environment: {environment}\n\n"
            f"This is a CRITICAL SAFETY ERROR.\n\n"
            f"Production databases MUST NOT be accessed from local development.\n\n"
            f"SOLUTIONS:\n"
            f"1. If this is intentional, set: export ENVIRONMENT=production\n"
            f"2. Check your .env file - should only contain LOCAL database URLs\n"
            f"3. Ensure GitHub Secrets contain prod credentials for CI/CD only\n"
            f"4. Never commit production URLs to .env or source code\n\n"
            f"CONTACT: DevOps team if you need production database access.\n"
            f"{'=' * 80}\n"
        )

    # Warn if development database URL contains unusual patterns
    if environment == "development" and not is_local_database(database_url):
        print(
            f"⚠️  WARNING: Development database URL looks unusual:\n"
            f"   {database_url}\n"
            f"   Expected: localhost or 127.0.0.1",
            file=sys.stderr
        )

    return database_url


def get_safe_database_url() -> str:
    """
    Get validated database URL.

    This function is called during app startup to ensure safety.

    Returns:
        Safe database URL for current environment

    Raises:
        ProductionDatabaseError: If production DB in wrong environment
    """
    return validate_database_url()


# Export for use in database.py
__all__ = [
    "ProductionDatabaseError",
    "is_production_database",
    "is_local_database",
    "get_environment",
    "validate_database_url",
    "get_safe_database_url",
]
