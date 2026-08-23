"""
Secrets Management Integration - Production-Grade Secret Handling

Supports multiple backends:
1. Azure Key Vault (recommended for Azure deployments)
2. AWS Secrets Manager (for AWS deployments)
3. Environment Variables (for development/testing)
4. Local .env files (development only)

USAGE:
    from app.core.secrets_manager import get_secret

    db_password = get_secret("database-password")
    api_key = get_secret("third-party-api-key")
"""
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

# Backend selection via environment variable
SECRETS_BACKEND = os.getenv("SECRETS_BACKEND", "env").lower()
SECRETS_VAULT_NAME = os.getenv("SECRETS_VAULT_NAME", "")


class SecretsBackend(ABC):
    """Abstract base class for secrets backends."""

    @abstractmethod
    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve a secret by name.

        Args:
            secret_name: Name of the secret to retrieve
            default: Default value if secret not found

        Returns:
            Secret value or default
        """
        pass


class EnvironmentVariableBackend(SecretsBackend):
    """
    Retrieve secrets from environment variables.

    Usage:
        SECRETS_BACKEND=env
        DATABASE_PASSWORD=secret123
    """

    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve secret from environment variable.
        Converts secret-name format to SECRET_NAME format.
        """
        # Convert kebab-case to UPPER_SNAKE_CASE
        env_var = secret_name.replace("-", "_").upper()

        value = os.getenv(env_var, default)
        if value:
            logger.debug(f"Retrieved secret from environment: {env_var}")
        return value


class AzureKeyVaultBackend(SecretsBackend):
    """
    Retrieve secrets from Azure Key Vault.

    Requirements:
        - pip install azure-identity azure-keyvault-secrets
        - Azure credentials configured (via environment or managed identity)
        - SECRETS_VAULT_NAME environment variable set to vault name

    Usage:
        SECRETS_BACKEND=azure
        SECRETS_VAULT_NAME=my-vault-name
        # Azure credentials from environment or MSI
    """

    def __init__(self):
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            if not SECRETS_VAULT_NAME:
                raise ValueError("SECRETS_VAULT_NAME environment variable not set")

            vault_url = f"https://{SECRETS_VAULT_NAME}.vault.azure.net/"
            credential = DefaultAzureCredential()
            self.client = SecretClient(vault_url=vault_url, credential=credential)
            logger.info(f"Azure Key Vault initialized: {SECRETS_VAULT_NAME}")
        except ImportError:
            raise ImportError(
                "Azure SDK packages not installed. "
                "Install with: pip install azure-identity azure-keyvault-secrets"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Azure Key Vault: {e}")
            raise

    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Retrieve secret from Azure Key Vault.
        Azure Key Vault requires lowercase names with hyphens, so no conversion needed.
        """
        try:
            secret = self.client.get_secret(secret_name)
            logger.debug(f"Retrieved secret from Azure Key Vault: {secret_name}")
            return secret.value
        except Exception as e:
            logger.warning(f"Failed to retrieve secret from Azure Key Vault: {secret_name} - {e}")
            return default


class AWSSecretsManagerBackend(SecretsBackend):
    """
    Retrieve secrets from AWS Secrets Manager.

    Requirements:
        - pip install boto3
        - AWS credentials configured (via environment, config file, or IAM role)
        - AWS_REGION environment variable set (optional, uses default region)

    Usage:
        SECRETS_BACKEND=aws
        AWS_REGION=us-east-1  # optional
        # AWS credentials from environment or IAM role
    """

    def __init__(self):
        try:
            import boto3

            region = os.getenv("AWS_REGION", "us-east-1")
            self.client = boto3.client("secretsmanager", region_name=region)
            logger.info(f"AWS Secrets Manager initialized: {region}")
        except ImportError:
            raise ImportError(
                "boto3 not installed. "
                "Install with: pip install boto3"
            )
        except Exception as e:
            logger.error(f"Failed to initialize AWS Secrets Manager: {e}")
            raise

    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve secret from AWS Secrets Manager."""
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            logger.debug(f"Retrieved secret from AWS Secrets Manager: {secret_name}")

            # AWS returns either SecretString or SecretBinary
            if "SecretString" in response:
                return response["SecretString"]
            else:
                # For binary secrets, return as-is (caller must decode)
                return response.get("SecretBinary")
        except Exception as e:
            logger.warning(f"Failed to retrieve secret from AWS Secrets Manager: {secret_name} - {e}")
            return default


class FallbackSecretsBackend(SecretsBackend):
    """
    Tries multiple backends in order until one succeeds.
    Useful for development that can fall back to environment variables.

    Usage:
        SECRETS_BACKEND=fallback  # tries azure, then aws, then env
    """

    def __init__(self):
        self.backends = []

        # Try to initialize each backend
        if SECRETS_BACKEND == "fallback" or SECRETS_BACKEND == "azure":
            try:
                self.backends.append(("Azure Key Vault", AzureKeyVaultBackend()))
            except Exception as e:
                logger.debug(f"Azure Key Vault backend unavailable: {e}")

        if SECRETS_BACKEND == "fallback" or SECRETS_BACKEND == "aws":
            try:
                self.backends.append(("AWS Secrets Manager", AWSSecretsManagerBackend()))
            except Exception as e:
                logger.debug(f"AWS Secrets Manager backend unavailable: {e}")

        # Always fall back to environment variables
        self.backends.append(("Environment Variables", EnvironmentVariableBackend()))

    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """Try each backend until one succeeds."""
        for backend_name, backend in self.backends:
            try:
                value = backend.get_secret(secret_name, default=None)
                if value is not None:
                    logger.debug(f"Retrieved secret from {backend_name}: {secret_name}")
                    return value
            except Exception as e:
                logger.debug(f"Backend {backend_name} failed for secret {secret_name}: {e}")
                continue

        logger.warning(f"Secret not found in any backend: {secret_name}")
        return default


# Global secrets manager instance (lazy-loaded, cached)
_secrets_backend: Optional[SecretsBackend] = None


def _init_secrets_backend() -> SecretsBackend:
    """Initialize the appropriate secrets backend based on configuration."""
    global _secrets_backend

    if _secrets_backend is not None:
        return _secrets_backend

    backend_name = SECRETS_BACKEND.lower()

    try:
        if backend_name == "azure":
            _secrets_backend = AzureKeyVaultBackend()
        elif backend_name == "aws":
            _secrets_backend = AWSSecretsManagerBackend()
        elif backend_name == "fallback":
            _secrets_backend = FallbackSecretsBackend()
        else:  # Default to environment variables
            _secrets_backend = EnvironmentVariableBackend()

        logger.info(f"Secrets backend initialized: {backend_name}")
        return _secrets_backend

    except Exception as e:
        logger.error(f"Failed to initialize secrets backend {backend_name}: {e}")
        # Fall back to environment variables as last resort
        _secrets_backend = EnvironmentVariableBackend()
        logger.warning("Falling back to environment variables for secrets")
        return _secrets_backend


@lru_cache(maxsize=1024)
def get_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Retrieve a secret by name from configured backend.

    Results are cached in memory. For security-sensitive operations
    where you need fresh values, call get_secret_uncached().

    Args:
        secret_name: Name of the secret (e.g., "database-password")
        default: Default value if secret not found

    Returns:
        Secret value or default

    Examples:
        db_pass = get_secret("database-password")
        api_key = get_secret("third-party-api-key", default="public-key")
    """
    backend = _init_secrets_backend()
    return backend.get_secret(secret_name, default)


def get_secret_uncached(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Retrieve a secret without caching.

    Use this when you need fresh values that might have changed
    (e.g., rotated credentials). Regular get_secret() is cached
    for performance.

    Args:
        secret_name: Name of the secret
        default: Default value if secret not found

    Returns:
        Secret value or default
    """
    backend = _init_secrets_backend()
    return backend.get_secret(secret_name, default)


def clear_secrets_cache() -> None:
    """
    Clear the in-memory secrets cache.

    Use after credential rotation or in tests where you need
    fresh values.
    """
    global _secrets_backend
    get_secret.cache_clear()
    logger.debug("Secrets cache cleared")


# Configuration helper for settings module
def create_secrets_aware_config():
    """
    Create a configuration object that pulls secrets from the vault.

    Usage in app/core/config.py:
        from app.core.secrets_manager import get_secret

        JWT_SECRET = get_secret("jwt-secret", default=os.getenv("JWT_SECRET", "dev-key"))
        DATABASE_PASSWORD = get_secret("database-password")
    """
    return {
        "get_secret": get_secret,
        "get_secret_uncached": get_secret_uncached,
        "clear_secrets_cache": clear_secrets_cache,
    }
