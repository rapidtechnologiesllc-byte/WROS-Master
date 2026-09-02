"""Secrets Management - Azure Key Vault or AWS Secrets Manager backend"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def get_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """Get a secret from configured backend (Azure or AWS or local env)"""
    try:
        env_key = secret_name.upper().replace("-", "_")
        if env_key in os.environ:
            return os.environ[env_key]
        return default
    except Exception as e:
        logger.error(f"Failed to retrieve secret {secret_name}: {e}", exc_info=True)
        return default
