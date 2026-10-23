"""Tenant AI (Thunder) configuration -- S-077/HRMS-0477.

Several services already import the getters below (follow-up timing,
ghosting reactivation, SLA thresholds, escalation keywords, digest time)
and fell back to their module defaults because this module did not exist.

Storage: one JSON row of overrides per tenant in system_config (key "tenant_ai_config"),
including the org-wide identity and switches -- Thunder's name and persona, the morning
digest switch and the Thunder kill switch. They used to live on an arbitrary "engagement
tenant" user row, so the kill switch saved on whoever clicked it while the pause check read a
different user: it did not reliably stop anything. A missing key means the default below.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger

CONFIG_KEY = "tenant_ai_config"
# Org-wide identity and switches (validated separately from the numeric thresholds)
IDENTITY_FIELDS = ("ai_agent_name", "ai_agent_persona", "digest_enabled", "thunder_enabled")
GREETING_CHANNELS = ("WHATSAPP", "EMAIL")


def _defaults() -> Dict[str, Any]:
    """The values the services use when nothing is configured."""
    from app.services.first_engagement_service import SLA_SECONDS
    from app.services.follow_up_scheduler_service import EMAIL_FOLLOWUP_HOURS, MAX_FOLLOWUPS, WHATSAPP_FOLLOWUP_HOURS
    from app.services.ghosting_detection_service import GHOSTING_REACTIVATION_DAYS
    from app.services.sla_monitoring_service import NO_CONTACT_THRESHOLD_HOURS
    from app.services.daily_digest_service import DIGEST_LOCAL_HOUR

    return {
        "whatsapp_followup_hours": WHATSAPP_FOLLOWUP_HOURS,
        "email_followup_hours": EMAIL_FOLLOWUP_HOURS,
        "max_followup_count": MAX_FOLLOWUPS,
        "ghosting_reactivation_days": GHOSTING_REACTIVATION_DAYS,
        "sla_first_contact_seconds": SLA_SECONDS,
        "sla_no_contact_hours": NO_CONTACT_THRESHOLD_HOURS,
        "escalation_keywords": [],
        "greeting_channel": "WHATSAPP",
        "digest_send_time": f"{DIGEST_LOCAL_HOUR:02d}:00",
    }


def _identity_defaults() -> Dict[str, Any]:
    from app.services.ai_conversation_service import DEFAULT_THUNDER_DISPLAY_NAME, DEFAULT_THUNDER_PERSONA_TEXT

    return {"ai_agent_name": DEFAULT_THUNDER_DISPLAY_NAME, "ai_agent_persona": DEFAULT_THUNDER_PERSONA_TEXT,
            "digest_enabled": True, "thunder_enabled": True}


def _tenant(db: Session, tenant_id) -> int:
    from app.core.tenant_context import tenant_of_key

    return tenant_of_key(db, tenant_id)


def _row(db: Session, tenant: int):
    from app.models.system_config import SystemConfig
    return db.query(SystemConfig).filter(
        SystemConfig.tenant_id == tenant, SystemConfig.config_key == CONFIG_KEY,
        SystemConfig.business_unit_id.is_(None),
    ).first()


def get_tenant_ai_config(db: Session, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """The tenant's settings: defaults overlaid with what was saved. tenant_id is a tenant id
    or an engagement-record key (app.core.tenant_context.tenant_of_key); None = the only tenant."""
    config = {**_defaults(), **_identity_defaults()}
    row = _row(db, _tenant(db, tenant_id))
    if row and isinstance(row.config_value, dict):
        config.update({k: v for k, v in row.config_value.items() if k in config})
    config["updated_at"] = row.updated_at.isoformat() if row and row.updated_at else None
    config["updated_by"] = row.updated_by if row else None
    return config


def thunder_identity(db: Session, tenant_id: Optional[str] = None) -> Dict[str, str]:
    """Thunder's candidate-facing name and persona for the tenant -- never blank (BR-02)."""
    config = get_tenant_ai_config(db, tenant_id)
    defaults = _identity_defaults()
    name = (config.get("ai_agent_name") or "").strip() or defaults["ai_agent_name"]
    persona = (config.get("ai_agent_persona") or "").strip() or defaults["ai_agent_persona"]
    return {"name": name, "persona": persona}


def is_thunder_enabled(db: Session, tenant_id: Optional[str] = None) -> bool:
    """The org-wide kill switch: False halts every automated Thunder send."""
    return get_tenant_ai_config(db, tenant_id).get("thunder_enabled") is not False


def update_tenant_ai_config(db: Session, updates: Dict[str, Any], changed_by: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Validate and save; unknown keys are rejected (ValueError)."""
    from app.models.system_config import SystemConfig

    defaults = _defaults()
    unknown = set(updates) - set(defaults) - set(IDENTITY_FIELDS)
    if unknown:
        raise ValueError(f"Unknown setting(s): {sorted(unknown)}")
    if "greeting_channel" in updates and str(updates["greeting_channel"]).upper() not in GREETING_CHANNELS:
        raise ValueError(f"greeting_channel must be one of {GREETING_CHANNELS}")
    for key in ("whatsapp_followup_hours", "email_followup_hours", "max_followup_count",
                "ghosting_reactivation_days", "sla_first_contact_seconds", "sla_no_contact_hours"):
        if key in updates and (not isinstance(updates[key], int) or updates[key] <= 0):
            raise ValueError(f"{key} must be a positive whole number")
    if "digest_send_time" in updates:
        try:
            datetime.strptime(str(updates["digest_send_time"]), "%H:%M")
        except ValueError:
            raise ValueError("digest_send_time must be HH:MM")
    if "escalation_keywords" in updates and not isinstance(updates["escalation_keywords"], list):
        raise ValueError("escalation_keywords must be a list")
    if "ai_agent_name" in updates and not str(updates["ai_agent_name"] or "").strip():
        raise ValueError("ai_agent_name cannot be blank")
    for key in ("digest_enabled", "thunder_enabled"):
        if key in updates and not isinstance(updates[key], bool):
            raise ValueError(f"{key} must be true or false")

    overrides = {k: v for k, v in updates.items() if k in defaults or k in IDENTITY_FIELDS}
    if "greeting_channel" in overrides:
        overrides["greeting_channel"] = str(overrides["greeting_channel"]).upper()
    if "ai_agent_name" in overrides:
        overrides["ai_agent_name"] = str(overrides["ai_agent_name"]).strip()
    if overrides:
        tenant = _tenant(db, tenant_id)
        row = _row(db, tenant)
        if row is None:
            row = SystemConfig(tenant_id=tenant, business_unit_id=None, config_category="AI_THRESHOLDS",
                               config_key=CONFIG_KEY, config_value={})
            db.add(row)
        row.config_value = {**(row.config_value or {}), **overrides}
        row.updated_by = changed_by
    db.commit()
    logger.info(f"[TenantAIConfig] Updated {sorted(updates)} by {changed_by}")
    return get_tenant_ai_config(db, tenant_id)


# Getters the engagement services import (each falls back on any error)
def get_followup_hours(db: Session, tenant_id: str, channel: str) -> int:
    config = get_tenant_ai_config(db, tenant_id)
    return config["whatsapp_followup_hours"] if channel == "whatsapp" else config["email_followup_hours"]


def get_max_followup_count(db: Session, tenant_id: str) -> int:
    return get_tenant_ai_config(db, tenant_id)["max_followup_count"]


def get_ghosting_reactivation_days(db: Session, tenant_id: str) -> int:
    return get_tenant_ai_config(db, tenant_id)["ghosting_reactivation_days"]


def get_sla_first_contact_seconds(db: Session, tenant_id: str) -> int:
    return get_tenant_ai_config(db, tenant_id)["sla_first_contact_seconds"]


def get_sla_no_contact_hours(db: Session, tenant_id: str) -> int:
    return get_tenant_ai_config(db, tenant_id)["sla_no_contact_hours"]


def get_escalation_keywords(db: Session, tenant_id: str) -> list:
    return list(get_tenant_ai_config(db, tenant_id)["escalation_keywords"] or [])
