"""
Configuration management for the Onboarding Application.

Loads environment variables and provides centralized configuration.

SECRETS MANAGEMENT (2026-08-18):
- Production: Use SECRETS_BACKEND env var to specify vault (azure, aws, env)
- Development: Falls back to environment variables and .env files
- See app.core.secrets_manager for implementation details
"""
import logging
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

logger = logging.getLogger(__name__)

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
    # CRITICAL: Load JWT_SECRET from secrets vault in production
    # No fallback to dev key - fail explicitly if not configured
    JWT_SECRET: str = get_secret("jwt-secret", default=os.getenv("JWT_SECRET", ""))
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

    # Admin user initial password (SECURITY: Load from environment, NOT hardcoded)
    # For production: Set via ADMIN_PASSWORD environment variable
    # For development: Falls back to temporary random password (forces reset on first login)
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    # S-017/HRMS-0417 -- base URL used to build the candidate portal
    # link Thunder sends via WhatsApp/Email (/candidate/{token}).
    # Defaults to localhost for development; must be set via FRONTEND_BASE_URL
    # environment variable for production/staging deployments.
    FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

    # CORS Settings - Environment-based configuration
    # Default: localhost for development (explicit origins, not wildcard)
    # Production: Use CORS_ORIGINS env var as comma-separated list
    # NOTE: Cannot use ["*"] with allow_credentials=True due to CORS security policy
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    # Allow additional origins from environment variable (production/staging)
    _CORS_ENV = os.getenv("CORS_ORIGINS", "").strip()
    if _CORS_ENV:
        # Production: specific origins provided
        CORS_ORIGINS: list = [origin.strip() for origin in _CORS_ENV.split(",") if origin.strip()]
    else:
        # Development: localhost only (secure default)
        # Allow all localhost ports (3000-65535) for autoPort development servers
        # This is development-only and localhost-only, so it's secure
        # Production MUST set CORS_ORIGINS env var with specific origins
        CORS_ORIGINS: list = []

        # Add all common localhost ports (3000-65535) for development
        # This handles Create React App autoPort, Vite, Next.js, and other dev servers
        for port in range(3000, 65536):
            CORS_ORIGINS.append(f"http://localhost:{port}")
            CORS_ORIGINS.append(f"http://127.0.0.1:{port}")
    
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

    # Passive-talent enrichment (free sources only; a source with no credentials is skipped)
    ENRICHMENT_ENABLED: bool = os.getenv("ENRICHMENT_ENABLED", "true").lower() == "true"
    SEARXNG_URL: Optional[str] = os.getenv("SEARXNG_URL")
    GOOGLE_CSE_API_KEY: Optional[str] = get_secret("google-cse-api-key", default=os.getenv("GOOGLE_CSE_API_KEY"))
    GOOGLE_CSE_ID: Optional[str] = os.getenv("GOOGLE_CSE_ID")
    # Free tier is 100/day; keep headroom for manual checks
    GOOGLE_CSE_DAILY_BUDGET: int = int(os.getenv("GOOGLE_CSE_DAILY_BUDGET", "90"))
    GITHUB_TOKEN: Optional[str] = get_secret("github-token", default=os.getenv("GITHUB_TOKEN"))
    OUTREACH_SENDER_NAME: str = os.getenv("OUTREACH_SENDER_NAME", "the BlitzenX talent team")

    # Thunder email: one HRMS mailbox sends and is read for replies
    THUNDER_MAILBOX: str = os.getenv("THUNDER_MAILBOX", "helpdesk_hrms@blitzenx.com")
    # Exchange Online allows ~30 msgs/min and ~10k recipients/day per mailbox; ramp cold mail slowly
    THUNDER_MAX_SENDS_PER_HOUR: int = int(os.getenv("THUNDER_MAX_SENDS_PER_HOUR", "25"))
    THUNDER_MAX_SENDS_PER_DAY: int = int(os.getenv("THUNDER_MAX_SENDS_PER_DAY", "200"))
    THUNDER_SEND_WINDOW: str = os.getenv("THUNDER_SEND_WINDOW", "09-18")  # candidate-local hours
    THUNDER_MIN_GAP_HOURS: int = int(os.getenv("THUNDER_MIN_GAP_HOURS", "48"))
    THUNDER_NURTURE_INTERVAL_DAYS: int = int(os.getenv("THUNDER_NURTURE_INTERVAL_DAYS", "30"))

    # Finance: invoices are emailed from this mailbox (same Graph app permissions as Thunder)
    FINANCE_MAILBOX: str = os.getenv("FINANCE_MAILBOX", "") or THUNDER_MAILBOX
    # Rupees per US dollar, to turn an accepted offer letter's annual CTC (INR) into the
    # employee's monthly USD cost. Unset = cost stays unknown (flagged in the P&L), never guessed.
    FX_INR_PER_USD: Optional[float] = float(os.getenv("FX_INR_PER_USD")) if os.getenv("FX_INR_PER_USD") else None
    # Paid hours in a month (40h x 52 weeks / 12); turns monthly loaded cost into an hourly cost
    STANDARD_MONTHLY_HOURS: float = float(os.getenv("STANDARD_MONTHLY_HOURS", "173.33"))

    # Background jobs (app/core/scheduled_jobs.py): comma-separated names. Unset = every
    # registered job (all internal: drafts, staff reminders, AR tasks, metrics); set it to ""
    # in .env to switch them all off, or to a shorter list
    SCHEDULED_JOBS_ENABLED: str = os.getenv(
        "SCHEDULED_JOBS_ENABLED",
        "timesheet_draft_creation,timesheet_reminders,ar_follow_up,expire_bu_ownerships,"
        "daily_revenue_scan,engagement_metrics,birthday_drafts,hiring_pipeline_sweep,client_start_date",
    )
    SCHEDULED_JOB_LEASE_GRACE_SECONDS: int = int(os.getenv("SCHEDULED_JOB_LEASE_GRACE_SECONDS", "120"))

    @classmethod
    def validate_config(cls) -> bool:
        """Validate that required configuration is present.

        CRITICAL: All production secrets must be explicitly configured.
        No fallback to development values in production.
        """
        required_vars = [
            ("DATABASE_URL", cls.DATABASE_URL),
            ("JWT_SECRET", cls.JWT_SECRET),
        ]

        missing = [var_name for var_name, var_value in required_vars if not var_value]

        if missing:
            raise ValueError(
                f"PRODUCTION BLOCKER: Missing required configuration: {', '.join(missing)}. "
                f"These MUST be set via environment variables or secrets vault before deployment."
            )

        # MEDIUM FIX: Warn about missing critical API keys
        critical_keys = [
            ("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""), "AI features (memory, summaries, scoring)"),
            ("SENTRY_DSN", os.getenv("SENTRY_DSN", ""), "Error tracking and monitoring"),
            ("FIELD_ENCRYPTION_KEY", cls.FIELD_ENCRYPTION_KEY, "Bank account field encryption"),
        ]

        for key_name, key_value, purpose in critical_keys:
            if not key_value or key_value.startswith("your_"):
                logger.warning(f"[Config] {key_name} not configured - {purpose} will be disabled/stubbed")

        return True

# Create a global settings instance
settings = Settings()
