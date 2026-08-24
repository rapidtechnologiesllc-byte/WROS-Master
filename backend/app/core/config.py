"""
Configuration management for the Onboarding Application.
Loads environment variables and provides centralized configuration.

SECRETS MANAGEMENT (2026-08-18):
- Production: Use SECRETS_BACKEND env var to specify vault (azure, aws, env)
- Development: Falls back to environment variables and .env files
- See app.core.secrets_manager for implementation details
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Bare load_dotenv() resolves .env via the process's current working
# directory, not this file's location -- some launchers (e.g. this repo's
# dev-server preview registration) start uvicorn with an unrelated CWD,
# which silently leaves every setting below at its "" default instead of
# a clear "file not found" error. Resolve relative to this file instead.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(_REPO_ROOT, ".env"))

# 2026-08-06, per Avinash's explicit instruction: local dev/click-through
# sessions must never point at the real production database again (the
# .env above has always held the real production DATABASE_URL -- that
# was the root cause of the login-outage incident logged in CLAUDE.md).
# .env.local (gitignored, same as .env) overrides DATABASE_URL and any
# other setting for local-only work -- see scripts/setup_local_db.py for
# how it's built. override=True so this genuinely wins over .env, not
# just fills in what .env left blank.
load_dotenv(os.path.join(_REPO_ROOT, ".env.local"), override=True)

# Import secrets manager for production secret retrieval
try:
    from app.core.secrets_manager import get_secret
except ImportError:
    # Fallback if module not available
    def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
        return os.getenv(name.replace("-", "_").upper(), default)


class Settings:
    """Application settings and configuration."""
    
    # Application Settings
    APP_NAME: str = "Onboarding Auth API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Server Settings
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8080"))
    
    # Database Settings
    # Tries to load from secrets vault first, falls back to environment variables
    DATABASE_URL: str = get_secret("database-url", default=os.getenv("DATABASE_URL", ""))

    # JWT Settings (HS256 with symmetric key)
    JWT_ALGORITHM: str = "HS256"
    # Tries secrets vault first, falls back to environment variable
    JWT_SECRET: str = get_secret("jwt-secret", default=os.getenv("JWT_SECRET", "dev-secret-key-change-in-production"))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    JWT_PRIVATE_KEY: str = ""  # Deprecated: using HS256 with JWT_SECRET instead
    JWT_PUBLIC_KEY: str = ""   # Deprecated: using HS256 with JWT_SECRET instead
    
    # Microsoft Graph API Settings
    # These can be stored in secrets vault for production security
    TENANT_ID: str = os.getenv("TENANT_ID", "")  # Usually public, but still configurable
    CLIENT_ID: str = os.getenv("CLIENT_ID", "")  # Usually public, but still configurable
    # CLIENT_SECRET is sensitive - load from vault with fallback
    CLIENT_SECRET: str = get_secret("client-secret", default=os.getenv("CLIENT_SECRET", ""))
    AUTHORITY: str = os.getenv("AUTHORITY", "") or f"https://login.microsoftonline.com/{TENANT_ID}"
    REDIRECT_URI: str = os.getenv("REDIRECT_URI", "")
    SCOPES: list = os.getenv("SCOPES", "").split() if os.getenv("SCOPES") else []

    # Webhook Settings (HRMS-0114) -- shared secret for endpoints that
    # must accept calls from non-interactive external callers, e.g.
    # POST /ai-agent/webhook/email-reply. See app.core.webhook_auth.
    # Load from secrets vault for production security
    WEBHOOK_SHARED_SECRET: str = get_secret("webhook-shared-secret", default=os.getenv("WEBHOOK_SHARED_SECRET", ""))

    # S-002/HRMS-0402 -- WhatsApp Cloud API webhook (Meta). Empty by
    # default since no WhatsApp Business API app is registered with Meta
    # yet in this environment (same posture as whatsapp_routing_service's
    # outbound send stub) -- the receiver endpoint is real, structurally
    # correct code either way; these two values are what Avinash provides
    # once a real Meta app + webhook subscription exist.
    # Load from secrets vault for production security
    WHATSAPP_VERIFY_TOKEN: str = get_secret("whatsapp-verify-token", default=os.getenv("WHATSAPP_VERIFY_TOKEN", ""))
    WHATSAPP_APP_SECRET: str = get_secret("whatsapp-app-secret", default=os.getenv("WHATSAPP_APP_SECRET", ""))

    # Field-level encryption (HRMS-0101 BR-01) -- AES-256 key (32 raw
    # bytes, base64-encoded) for employee bank account/routing fields.
    # See app.core.field_encryption.
    # CRITICAL: Load from secrets vault for production
    FIELD_ENCRYPTION_KEY: str = get_secret("field-encryption-key", default=os.getenv("FIELD_ENCRYPTION_KEY", ""))

    # S-017/HRMS-0417 -- base URL used to build the candidate portal
    # link Thunder sends via WhatsApp/Email (/candidate/{token}).
    # Defaults to localhost for development; must be set via FRONTEND_BASE_URL
    # environment variable for production/staging deployments.
    FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

    # CORS Settings - Environment-based configuration
    # Default: localhost for development
    # Production: Use CORS_ORIGINS env var as comma-separated list
    CORS_ORIGINS: list = ["*"]  # Temporary wildcard for dev testing

    # Allow additional origins from environment variable (production/staging)
    _CORS_ENV = os.getenv("CORS_ORIGINS", "").strip()
    if _CORS_ENV:
        CORS_ORIGINS.extend([origin.strip() for origin in _CORS_ENV.split(",") if origin.strip()])
    
    # Security Settings
    BCRYPT_ROUNDS: int = 12
    
    # File Upload Settings
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB default
    
    # Email Settings (if needed in future)
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: Optional[int] = int(os.getenv("SMTP_PORT", "587")) if os.getenv("SMTP_PORT") else None
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    
    @classmethod
    def validate_config(cls) -> bool:
        """Validate that required configuration is present."""
        required_vars = [
            ("DATABASE_URL", cls.DATABASE_URL),
            ("JWT_SECRET", cls.JWT_SECRET),
        ]

        missing = [var_name for var_name, var_value in required_vars if not var_value]

        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        return True


# Create a global settings instance
settings = Settings()
