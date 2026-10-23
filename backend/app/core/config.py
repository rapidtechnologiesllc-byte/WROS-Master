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

# A test run names its own throwaway database (TEST_DATABASE_URL, set by tests/conftest.py).
# It must beat .env.local, or app code under test reads and writes the dev database.
if os.getenv("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

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
    # Candidate rejection email: off until the rejection-email UX is decided (OPEN_ITEMS decision 5)
    REJECTION_EMAIL_ENABLED: bool = os.getenv("REJECTION_EMAIL_ENABLED", "false").lower() == "true"
    # Every pipeline status change is emailed to the candidate (incl. rejection, never the reason);
    # app.services.candidate_status_notifications. The rejection handler's own email stays behind
    # REJECTION_EMAIL_ENABLED so a rejection is never emailed twice.
    CANDIDATE_STATUS_EMAILS_ENABLED: bool = os.getenv("CANDIDATE_STATUS_EMAILS_ENABLED", "true").lower() == "true"

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
    # Panel vs Flash calibration: Flash "advances" a candidate whose job match score is at least this
    FLASH_ADVANCE_SCORE: int = int(os.getenv("FLASH_ADVANCE_SCORE", "60"))
    # Name of the parent company created on an empty database (the primary tenant)
    PRIMARY_TENANT_NAME: str = os.getenv("PRIMARY_TENANT_NAME", "BlitzenX")
    # Tenant the public website chat creates candidates in (empty = the only tenant)
    PUBLIC_CHAT_TENANT_ID: Optional[int] = int(os.getenv("PUBLIC_CHAT_TENANT_ID")) if os.getenv("PUBLIC_CHAT_TENANT_ID") else None
    # Expense receipts: a receipt whose amount and date match the entry approves the manager step
    # automatically; anything else goes to the manager with the reasons
    EXPENSE_RECEIPT_MAX_BYTES: int = int(os.getenv("EXPENSE_RECEIPT_MAX_BYTES", str(10 * 1024 * 1024)))
    EXPENSE_RECEIPT_AMOUNT_TOLERANCE_PCT: float = float(os.getenv("EXPENSE_RECEIPT_AMOUNT_TOLERANCE_PCT", "2"))
    EXPENSE_RECEIPT_DATE_TOLERANCE_DAYS: int = int(os.getenv("EXPENSE_RECEIPT_DATE_TOLERANCE_DAYS", "7"))
    MAX_UPLOAD_SIZE: int = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB default

    # Flash matching: a candidate qualifies for a job at this skill-match score (0-100) or above
    FLASH_MATCH_MIN_SCORE: int = int(os.getenv("FLASH_MATCH_MIN_SCORE", "60"))
    # Flash's recruiter run re-runs this often while a job is active
    FLASH_RECRUITER_INTERVAL_HOURS: int = int(os.getenv("FLASH_RECRUITER_INTERVAL_HOURS", "4"))

    # Flash's language models (CEO 2026-10-15: hybrid). The large model (Claude) plans and uses
    # tools; the small self-hosted model (Ollama-compatible /api/chat) parses and classifies.
    # Either may be off; with both off Flash answers from its rules and says what is offline.
    # Only work data reaches a model: app.services.flash_brain.redaction strips contact details,
    # pay, documents and finance figures first.
    ANTHROPIC_API_KEY: str = get_secret("anthropic-api-key", default=os.getenv("ANTHROPIC_API_KEY", "")) or ""
    FLASH_LARGE_LLM_MODEL: str = os.getenv("FLASH_LARGE_LLM_MODEL", "claude-opus-5-5")
    FLASH_LARGE_LLM_EFFORT: str = os.getenv("FLASH_LARGE_LLM_EFFORT", "medium")
    FLASH_LARGE_LLM_TIMEOUT_S: float = float(os.getenv("FLASH_LARGE_LLM_TIMEOUT_S", "60"))
    FLASH_LARGE_LLM_MAX_TOKENS: int = int(os.getenv("FLASH_LARGE_LLM_MAX_TOKENS", "16000"))
    FLASH_LARGE_LLM_MAX_TOOL_ROUNDS: int = int(os.getenv("FLASH_LARGE_LLM_MAX_TOOL_ROUNDS", "8"))
    # Server-side refusal fallback (Anthropic picks the fallback model by refusal category)
    FLASH_LARGE_LLM_FALLBACKS_ENABLED: bool = os.getenv("FLASH_LARGE_LLM_FALLBACKS_ENABLED", "true").lower() == "true"
    FLASH_SMALL_LLM_BASE_URL: str = os.getenv("FLASH_SMALL_LLM_BASE_URL", "")
    FLASH_SMALL_LLM_MODEL: str = os.getenv("FLASH_SMALL_LLM_MODEL", "")
    FLASH_SMALL_LLM_TIMEOUT_S: float = float(os.getenv("FLASH_SMALL_LLM_TIMEOUT_S", "15"))
    # Kill switch: false = Flash answers from its rules only, no model call at all
    FLASH_AGENT_ENABLED: bool = os.getenv("FLASH_AGENT_ENABLED", "true").lower() == "true"
    # Flash conversation (one per user, kept server-side): earlier turns a reply may draw on, the
    # most recent messages the bubble loads, and how often the closed bubble checks for news
    FLASH_CONTEXT_TURNS: int = int(os.getenv("FLASH_CONTEXT_TURNS", "6"))
    FLASH_CONVERSATION_PAGE: int = int(os.getenv("FLASH_CONVERSATION_PAGE", "100"))
    FLASH_POLL_SECONDS: int = int(os.getenv("FLASH_POLL_SECONDS", "60"))
    # Jobs created by talking to Flash (CEO 2026-10-15): employment type and openings when the user
    # does not say
    FLASH_JOB_DEFAULT_COMPANY_TYPE: str = os.getenv("FLASH_JOB_DEFAULT_COMPANY_TYPE", "Full time")
    FLASH_JOB_DEFAULT_POSITIONS: int = int(os.getenv("FLASH_JOB_DEFAULT_POSITIONS", "1"))
    # Flash missions (flash spec D): after a job is created in the chat, Flash sources, schedules
    # interviews and chases feedback until the positions are filled -- a position is filled when the
    # candidate JOINS (CEO 2026-10-15), never at offer. Off until piloted.
    FLASH_MISSIONS_ENABLED: bool = os.getenv("FLASH_MISSIONS_ENABLED", "false").lower() == "true"
    FLASH_MISSION_BATCH: int = int(os.getenv("FLASH_MISSION_BATCH", "20"))  # missions per sweep
    # Up to this many candidates interviewed at once per open position (CEO 2026-10-15: 20)
    FLASH_PARALLEL_CANDIDATES: int = int(os.getenv("FLASH_PARALLEL_CANDIDATES", "20"))
    FLASH_MISSION_RECHECK_HOURS: int = int(os.getenv("FLASH_MISSION_RECHECK_HOURS", "4"))  # no eligible candidate
    FLASH_MISSION_TRACK_CHECK_MINUTES: int = int(os.getenv("FLASH_MISSION_TRACK_CHECK_MINUTES", "15"))
    # No match: tell the recruiter after this many days, then the hiring manager every N days; a
    # search is never closed for having no match (CEO 2026-10-15)
    FLASH_MISSION_ESCALATE_AFTER_DAYS: int = int(os.getenv("FLASH_MISSION_ESCALATE_AFTER_DAYS", "5"))
    FLASH_MISSION_REESCALATE_DAYS: int = int(os.getenv("FLASH_MISSION_REESCALATE_DAYS", "7"))
    # A queued job that never appears fails its mission after this long
    FLASH_MISSION_JOB_WAIT_HOURS: int = int(os.getenv("FLASH_MISSION_JOB_WAIT_HOURS", "24"))
    FLASH_MISSION_MAX_ERRORS: int = int(os.getenv("FLASH_MISSION_MAX_ERRORS", "3"))
    # No common free slot: retry this often; tell the recruiter after this long
    FLASH_NO_SLOT_RETRY_HOURS: int = int(os.getenv("FLASH_NO_SLOT_RETRY_HOURS", "24"))
    FLASH_NO_SLOT_ESCALATE_HOURS: int = int(os.getenv("FLASH_NO_SLOT_ESCALATE_HOURS", "48"))
    # Missing interview feedback: remind the interviewer this often; after this many reminders the
    # hiring manager is told too
    FLASH_FEEDBACK_CHASE_HOURS: int = int(os.getenv("FLASH_FEEDBACK_CHASE_HOURS", "24"))
    FLASH_FEEDBACK_CHASES_BEFORE_HM: int = int(os.getenv("FLASH_FEEDBACK_CHASES_BEFORE_HM", "2"))
    # Interview slots Flash picks: no sooner than this, no later than this, on the quarter hour
    INTERVIEW_MIN_LEAD_HOURS: int = int(os.getenv("INTERVIEW_MIN_LEAD_HOURS", "24"))
    INTERVIEW_HORIZON_DAYS: int = int(os.getenv("INTERVIEW_HORIZON_DAYS", "10"))
    INTERVIEW_SLOT_STEP_MINUTES: int = int(os.getenv("INTERVIEW_SLOT_STEP_MINUTES", "15"))
    # Read interviewers' Outlook busy times and put Flash's interviews in their calendar (needs the
    # Graph app with Calendars.ReadWrite); off -> database conflicts only, the invite says the link follows
    FLASH_USE_GRAPH_CALENDAR: bool = os.getenv("FLASH_USE_GRAPH_CALENDAR", "false").lower() == "true"

    # Interview scheduling: interviewer business hours (local time), working days, buffer, length
    INTERVIEW_WORKDAY_START_HOUR: int = int(os.getenv("INTERVIEW_WORKDAY_START_HOUR", "9"))
    INTERVIEW_WORKDAY_END_HOUR: int = int(os.getenv("INTERVIEW_WORKDAY_END_HOUR", "17"))
    # Python weekday numbers (Monday=0) that are never scheduled
    INTERVIEW_WEEKEND_DAYS: tuple = tuple(
        int(d) for d in os.getenv("INTERVIEW_WEEKEND_DAYS", "5,6").split(",") if d.strip())
    INTERVIEW_BUFFER_MINUTES: int = int(os.getenv("INTERVIEW_BUFFER_MINUTES", "15"))
    INTERVIEW_DURATION_MINUTES: int = int(
        os.getenv("INTERVIEW_DURATION_MINUTES", os.getenv("DEFAULT_INTERVIEW_DURATION_MINUTES", "60")))
    # Time zone used for a person whose profile has none
    INTERVIEW_DEFAULT_TIMEZONE: str = os.getenv("INTERVIEW_DEFAULT_TIMEZONE", "Asia/Kolkata")
    # Wall-clock zone that interview start/end times were saved in before storage became naive
    # UTC (2026-10-15). Read once, by the one-time interview_times_to_utc data migration.
    INTERVIEW_LEGACY_STORAGE_TIMEZONE: str = os.getenv("INTERVIEW_LEGACY_STORAGE_TIMEZONE", "Asia/Kolkata")
    # Employment type by the candidate's country (CEO 2026-10-15), the one place this lives:
    # app.services.employment_type_policy reads it. One canonical set of types (FULLTIME, CONTRACT,
    # C2C, 1099, UNKNOWN); a country lists the types it accepts with its own labels, and "names"
    # are how a free-text location names the country. A country not listed accepts nothing.
    # C2C, 1099 and UNKNOWN can never be accepted (checked when the policy loads).
    EMPLOYMENT_TYPE_POLICY_JSON: str = os.getenv("EMPLOYMENT_TYPE_POLICY_JSON", "") or """{
      "labels": {"FULLTIME": "Full-time", "CONTRACT": "Contract", "C2C": "Corp-to-corp (C2C)",
                 "1099": "1099 contractor", "UNKNOWN": "Not confirmed"},
      "countries": {
        "US": {"name": "United States", "names": ["united states", "united states of america", "usa", "us", "u.s.", "u.s.a."],
               "accepts": {"FULLTIME": "W2 full-time", "CONTRACT": "W2 contract"}},
        "IN": {"name": "India", "names": ["india", "in", "bharat"],
               "accepts": {"FULLTIME": "Full-time", "CONTRACT": "Contract"}}
      }
    }"""
    # Every interview invites the candidate (CEO 2026-10-15). The automatic invite waits this long
    # so an invite sent from the screen (POST /email/interview/invite/{id}) supersedes it
    INTERVIEW_INVITE_DELAY_SECONDS: int = int(os.getenv("INTERVIEW_INVITE_DELAY_SECONDS", "300"))
    # interview_reminders job: reminders before the start and feedback nudges after the end (minutes),
    # sent only within this many minutes of their due time (older ones are skipped, never sent late)
    INTERVIEW_REMINDER_MINUTES_BEFORE: tuple = tuple(
        int(m) for m in os.getenv("INTERVIEW_REMINDER_MINUTES_BEFORE", "60,15").split(",") if m.strip())
    INTERVIEW_FEEDBACK_NUDGE_MINUTES_AFTER: tuple = tuple(
        int(m) for m in os.getenv("INTERVIEW_FEEDBACK_NUDGE_MINUTES_AFTER", "60,1440").split(",") if m.strip())
    INTERVIEW_REMINDER_GRACE_MINUTES: int = int(os.getenv("INTERVIEW_REMINDER_GRACE_MINUTES", "30"))
    
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
    # Thunder first engagement (go-live 2026-10-13): every contactable candidate created in the
    # last THUNDER_ENGAGEMENT_LOOKBACK_DAYS who is not yet in the email cadence is engaged by the
    # thunder_engagement_sweep job. Kill switches: this flag, and the global pause on the
    # Message Queue screen (stops every queue send at once).
    THUNDER_ENGAGEMENT_ENABLED: bool = os.getenv("THUNDER_ENGAGEMENT_ENABLED", "true").lower() == "true"
    THUNDER_ENGAGEMENT_LOOKBACK_DAYS: int = int(os.getenv("THUNDER_ENGAGEMENT_LOOKBACK_DAYS", "30"))
    THUNDER_ENGAGEMENT_BATCH: int = int(os.getenv("THUNDER_ENGAGEMENT_BATCH", "50"))

    # Finance: invoices are emailed from this mailbox (same Graph app permissions as Thunder)
    FINANCE_MAILBOX: str = os.getenv("FINANCE_MAILBOX", "") or THUNDER_MAILBOX
    # Rupees per US dollar, to turn an accepted offer letter's annual CTC (INR) into the
    # employee's monthly USD cost. Unset = cost stays unknown (flagged in the P&L), never guessed.
    # Authority thresholds on RoleTemplate.hierarchy_level (1 Intern .. 17 CEO; see
    # org_hierarchy_validator.HIERARCHY_LEVELS). app.core.authority reads these.
    SENIOR_MANAGER_MIN_LEVEL: int = int(os.getenv("SENIOR_MANAGER_MIN_LEVEL", "9"))
    DIRECTOR_MIN_LEVEL: int = int(os.getenv("DIRECTOR_MIN_LEVEL", "11"))
    # An employee whose active allocation ends within this many days is rolling off and may be
    # submitted to their next client (CEO 2026-10-14)
    ROLL_OFF_WINDOW_DAYS: int = int(os.getenv("ROLL_OFF_WINDOW_DAYS", "30"))
    # Core certification (CEO 2026-10-14): approved billable days on Staff Aug with no escalation,
    # and how long the BU Head's approval task runs
    CORE_CERT_BILLABLE_DAYS: int = int(os.getenv("CORE_CERT_BILLABLE_DAYS", "90"))
    CORE_CERT_TASK_DUE_DAYS: int = int(os.getenv("CORE_CERT_TASK_DUE_DAYS", "7"))
    BU_LEADER_MIN_LEVEL: int = int(os.getenv("BU_LEADER_MIN_LEVEL", "14"))
    PARTNER_MIN_LEVEL: int = int(os.getenv("PARTNER_MIN_LEVEL", "16"))
    CEO_LEVEL: int = int(os.getenv("CEO_LEVEL", "17"))
    MFA_TOTP_MIN_LEVEL: int = int(os.getenv("MFA_TOTP_MIN_LEVEL", "14"))
    # auto-invoicing considers this many complete months back (oldest first), so late approvals still bill
    AUTO_INVOICE_LOOKBACK_MONTHS: int = int(os.getenv("AUTO_INVOICE_LOOKBACK_MONTHS", "3"))
    # INR per 1 USD (CEO 2026-10-11: $1 = 85 INR); the FX_INR_PER_USD env var overrides it
    FX_INR_PER_USD: float = float(os.getenv("FX_INR_PER_USD") or 85)
    # Paid hours in a month (40h x 52 weeks / 12); turns monthly loaded cost into an hourly cost
    STANDARD_MONTHLY_HOURS: float = float(os.getenv("STANDARD_MONTHLY_HOURS", "173.33"))
    # My Timesheet: how many weeks before the current one an employee may open and fill. Never more
    # than the submission window (app.models.timesheet.MAX_SUBMISSION_LOOKBACK_WEEKS)
    TIMESHEET_SELF_SERVICE_BACK_WEEKS: int = int(os.getenv("TIMESHEET_SELF_SERVICE_BACK_WEEKS", "4"))
    # Missing-timesheet reminders: the employee is reminded first; still missing this many days
    # later, their approver (reporting manager -> manager -> BU head -> partner) is told
    TIMESHEET_NAG_ESCALATION_DAYS: int = int(os.getenv("TIMESHEET_NAG_ESCALATION_DAYS", "3"))
    # Bulk employee import: how long a dry run's token stays valid, and the largest file accepted
    EMPLOYEE_IMPORT_TOKEN_TTL_MINUTES: int = int(os.getenv("EMPLOYEE_IMPORT_TOKEN_TTL_MINUTES", "60"))
    EMPLOYEE_IMPORT_MAX_ROWS: int = int(os.getenv("EMPLOYEE_IMPORT_MAX_ROWS", "2000"))
    # planned billable hours per business day for projected revenue (allocation x utilization)
    STANDARD_DAILY_HOURS: float = float(os.getenv("STANDARD_DAILY_HOURS", "8"))
    # Project expected-revenue estimate: a positive margin below this % of revenue shows as TIGHT
    PROJECT_MARGIN_TIGHT_PCT: float = float(os.getenv("PROJECT_MARGIN_TIGHT_PCT", "20"))
    # Utilization: a billable employee below this % in their latest week is flagged on the
    # Utilization dashboard (the target the dashboard measures against)
    UTILIZATION_TARGET_PCT: float = float(os.getenv("UTILIZATION_TARGET_PCT", "50"))
    # Available hours in a week, the denominator of weekly utilization
    UTILIZATION_STANDARD_WEEKLY_HOURS: float = float(os.getenv("UTILIZATION_STANDARD_WEEKLY_HOURS", "40"))
    # The weekly utilization_snapshot job recomputes this many completed weeks (so late timesheet
    # approvals are picked up)
    UTILIZATION_SNAPSHOT_WEEKS: int = int(os.getenv("UTILIZATION_SNAPSHOT_WEEKS", "4"))

    # Background jobs (app/core/scheduled_jobs.py): comma-separated names. Unset = every
    # registered job (all internal: drafts, staff reminders, AR tasks, metrics); set it to ""
    # in .env to switch them all off, or to a shorter list
    SCHEDULED_JOBS_ENABLED: str = os.getenv(
        "SCHEDULED_JOBS_ENABLED",
        "timesheet_draft_creation,timesheet_reminders,ar_follow_up,expire_bu_ownerships,"
        "daily_revenue_scan,engagement_metrics,birthday_drafts,hiring_pipeline_sweep,client_start_date,auto_invoicing,"
        "utilization_snapshot",
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
