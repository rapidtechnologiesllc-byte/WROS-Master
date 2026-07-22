"""
Configuration management for the Onboarding Application.
Loads environment variables and provides centralized configuration.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Bare load_dotenv() resolves .env via the process's current working
# directory, not this file's location -- some launchers (e.g. this repo's
# dev-server preview registration) start uvicorn with an unrelated CWD,
# which silently leaves every setting below at its "" default instead of
# a clear "file not found" error. Resolve relative to this file instead.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))


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
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # JWT Settings
    JWT_ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    JWT_PRIVATE_KEY: str = os.getenv("JWT_PRIVATE_KEY", "").replace("\\n", "\n").replace("\r\n", "\n")
    JWT_PUBLIC_KEY: str = os.getenv("JWT_PUBLIC_KEY", "").replace("\\n", "\n").replace("\r\n", "\n")
    
    # Microsoft Graph API Settings
    TENANT_ID: str = os.getenv("TENANT_ID", "")
    CLIENT_ID: str = os.getenv("CLIENT_ID", "")
    CLIENT_SECRET: str = os.getenv("CLIENT_SECRET", "")
    AUTHORITY: str = os.getenv("AUTHORITY", "") or f"https://login.microsoftonline.com/{TENANT_ID}"
    REDIRECT_URI: str = os.getenv("REDIRECT_URI", "")
    SCOPES: list = os.getenv("SCOPES", "").split() if os.getenv("SCOPES") else []

    # Webhook Settings (HRMS-0114) -- shared secret for endpoints that
    # must accept calls from non-interactive external callers, e.g.
    # POST /ai-agent/webhook/email-reply. See app.core.webhook_auth.
    WEBHOOK_SHARED_SECRET: str = os.getenv("WEBHOOK_SHARED_SECRET", "")

    # Field-level encryption (HRMS-0101 BR-01) -- AES-256 key (32 raw
    # bytes, base64-encoded) for employee bank account/routing fields.
    # See app.core.field_encryption.
    FIELD_ENCRYPTION_KEY: str = os.getenv("FIELD_ENCRYPTION_KEY", "")

    # CORS Settings
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://46.224.149.7:3005",
        "http://46.224.149.7:8080",
        "http://localhost:8080",
        # Add production frontend URLs here
    ]
    
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
            ("JWT_PRIVATE_KEY", cls.JWT_PRIVATE_KEY),
            ("JWT_PUBLIC_KEY", cls.JWT_PUBLIC_KEY),
        ]
        
        missing = [var_name for var_name, var_value in required_vars if not var_value]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True


# Create a global settings instance
settings = Settings()
