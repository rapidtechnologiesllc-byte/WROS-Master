"""Tenant AI (Thunder) configuration -- S-077/HRMS-0477.

Several services already import the getters below (follow-up timing,
ghosting reactivation, SLA thresholds, escalation keywords, digest time)
and fell back to their module defaults because this module did not exist.

Storage:
- Identity / switches that already live on the engagement-tenant user row
  (ai_agent_name, ai_agent_persona, digest_enabled, thunder_enabled) are
  read and written there -- the services already read them from it.
- Everything else is one JSON row of overrides in system_config
  (key "tenant_ai_config"); a missing key means the service default.
"""
from app.core.tenant_context import sole_tenant_id
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger

CONFIG_KEY = "tenant_ai_config"
USER_FIELDS = ("ai_agent_name", "ai_agent_persona", "digest_enabled", "thunder_enabled")
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


def _row(db: Session):
    from app.models.system_config import SystemConfig
    return db.query(SystemConfig).filter(
        SystemConfig.config_key == CONFIG_KEY, SystemConfig.business_unit_id.is_(None)
    ).first()


def _tenant_user(db: Session, tenant_id: Optional[str]):
    from app.models.user import Users
    if not tenant_id:
        from app.services.ai_conversation_service import resolve_default_tenant_id
        tenant_id = resolve_default_tenant_id()
    return db.query(Users).filter(Users.UserID == tenant_id).first() if tenant_id else None


def get_tenant_ai_config(db: Session, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    config = _defaults()
    row = _row(db)
    if row and isinstance(row.config_value, dict):
        config.update({k: v for k, v in row.config_value.items() if k in config})
    user = _tenant_user(db, tenant_id)
    for field in USER_FIELDS:
        config[field] = getattr(user, field, None) if user else None
    config["updated_at"] = row.updated_at.isoformat() if row and row.updated_at else None
    config["updated_by"] = row.updated_by if row else None
    return config


def update_tenant_ai_config(db: Session, updates: Dict[str, Any], changed_by: str, tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Validate and save; unknown keys are rejected (ValueError)."""
    from app.models.system_config import SystemConfig

    defaults = _defaults()
    unknown = set(updates) - set(defaults) - set(USER_FIELDS)
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

    user = _tenant_user(db, tenant_id)
    for field in USER_FIELDS:
        if field in updates:
            if user is None:
                raise ValueError("No engagement tenant user to store this setting on")
            setattr(user, field, updates[field])

    overrides = {k: v for k, v in updates.items() if k in defaults}
    if "greeting_channel" in overrides:
        overrides["greeting_channel"] = str(overrides["greeting_channel"]).upper()
    if overrides:
        row = _row(db)
        if row is None:
            row = SystemConfig(tenant_id=sole_tenant_id(db), business_unit_id=None, config_category="AI_THRESHOLDS",
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
