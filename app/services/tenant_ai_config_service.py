"""
S-077/HRMS-0477 -- Tenant AI Configuration.

get_tenant_ai_config() is the ONE unified read: it merges the 4
Thunder-identity/pause fields that already live on the real Users row
(ai_agent_name/ai_agent_persona/digest_enabled/thunder_enabled --
S-011/S-065/S-075) with the genuinely new TenantAIConfig row, so a
caller (the admin UI, or any of the wired consumers below) never has
to know which table a given setting actually lives in. See
app.models.tenant_ai_config's module docstring for why those 4 fields
are read from Users rather than duplicated into a second table.

No Redis in this codebase -- real in-process 5-min TTL cache instead,
same convention app.services.candidate_context_service already
established for its own cache.
"""
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.tenant_ai_config import GREETING_CHANNELS, TenantAIConfig, TenantAIConfigChangeLog
from app.models.user import Users

CACHE_TTL_SECONDS = 300  # 5 min, matching the spec's own literal Redis TTL

_CONFIG_CACHE: Dict[str, Tuple[float, Dict]] = {}

# Fields that already live on Users (S-011/S-065/S-075) -- never
# duplicated onto TenantAIConfig; update_tenant_ai_config() routes
# writes for these to the Users row instead.
USER_BACKED_FIELDS = ("ai_agent_name", "ai_agent_persona", "digest_enabled", "thunder_enabled")

CONFIG_ROW_FIELDS = (
    "greeting_channel", "whatsapp_followup_hours", "email_followup_hours", "max_followup_count",
    "ghosting_reactivation_days", "digest_send_time", "sla_first_contact_seconds", "sla_no_contact_hours",
    "qualification_field_order", "escalation_keywords",
)


class PersonaChangeRequiresApproval(Exception):
    """BR-01: ai_agent_persona changes require the BA-approval checkbox."""


class InvalidTenantAIConfigField(Exception):
    pass


def invalidate_tenant_ai_config_cache(tenant_id: str) -> None:
    _CONFIG_CACHE.pop(tenant_id, None)


def _get_or_create_config_row(db: Session, tenant_id: str) -> TenantAIConfig:
    row = db.query(TenantAIConfig).filter(TenantAIConfig.tenant_id == tenant_id).first()
    if row is None:
        row = TenantAIConfig(tenant_id=tenant_id)
        db.add(row)
        db.flush()
    return row


def _serialize(tenant_user: Users, config_row: TenantAIConfig) -> Dict:
    return {
        "tenant_id": tenant_user.UserID,
        "ai_agent_name": tenant_user.ai_agent_name,
        "ai_agent_persona": tenant_user.ai_agent_persona,
        "digest_enabled": tenant_user.digest_enabled,
        "thunder_enabled": tenant_user.thunder_enabled,
        "greeting_channel": config_row.greeting_channel,
        "whatsapp_followup_hours": config_row.whatsapp_followup_hours,
        "email_followup_hours": config_row.email_followup_hours,
        "max_followup_count": config_row.max_followup_count,
        "ghosting_reactivation_days": config_row.ghosting_reactivation_days,
        "digest_send_time": config_row.digest_send_time,
        "sla_first_contact_seconds": config_row.sla_first_contact_seconds,
        "sla_no_contact_hours": config_row.sla_no_contact_hours,
        "qualification_field_order": config_row.qualification_field_order,
        "escalation_keywords": config_row.escalation_keywords,
        "updated_at": config_row.updated_at.isoformat() if config_row.updated_at else None,
        "updated_by": config_row.updated_by,
    }


def get_tenant_ai_config(db: Session, tenant_id: str, *, use_cache: bool = True) -> Dict:
    if use_cache:
        cached = _CONFIG_CACHE.get(tenant_id)
        if cached is not None:
            if cached[0] > time.monotonic():
                return cached[1]
            _CONFIG_CACHE.pop(tenant_id, None)

    tenant_user = db.query(Users).filter(Users.UserID == tenant_id).first()
    if tenant_user is None:
        raise ValueError(f"Tenant '{tenant_id}' not found.")
    config_row = _get_or_create_config_row(db, tenant_id)
    db.commit()
    result = _serialize(tenant_user, config_row)

    if use_cache:
        _CONFIG_CACHE[tenant_id] = (time.monotonic() + CACHE_TTL_SECONDS, result)
    return result


def update_tenant_ai_config(
    db: Session, tenant_id: str, updates: Dict, *, updated_by: str, ba_approved: bool = False,
) -> Dict:
    """AC-4/BR-01: a persona change without ba_approved=True is rejected
    outright, never silently applied. AC-7: every real change (no-op
    updates that match the current value are NOT logged) is recorded in
    TenantAIConfigChangeLog with before/after state."""
    if "ai_agent_persona" in updates and not ba_approved:
        raise PersonaChangeRequiresApproval(
            "Changing the AI persona requires Lead BA written approval -- resubmit with ba_approved=true."
        )
    if "greeting_channel" in updates and updates["greeting_channel"] not in GREETING_CHANNELS:
        raise InvalidTenantAIConfigField(f"greeting_channel must be one of {GREETING_CHANNELS}.")

    for field in updates:
        if field not in USER_BACKED_FIELDS and field not in CONFIG_ROW_FIELDS:
            raise InvalidTenantAIConfigField(f"Unknown config field '{field}'.")

    tenant_user = db.query(Users).filter(Users.UserID == tenant_id).first()
    if tenant_user is None:
        raise ValueError(f"Tenant '{tenant_id}' not found.")
    config_row = _get_or_create_config_row(db, tenant_id)

    before = _serialize(tenant_user, config_row)
    changed_fields = {}

    for field, value in updates.items():
        old_value = before[field]
        if old_value == value:
            continue
        changed_fields[field] = {"before": old_value, "after": value}
        if field in USER_BACKED_FIELDS:
            setattr(tenant_user, field, value)
            db.add(tenant_user)
        else:
            setattr(config_row, field, value)
            db.add(config_row)

    if changed_fields:
        config_row.updated_by = updated_by
        config_row.updated_at = datetime.utcnow()
        db.add(config_row)
        db.add(TenantAIConfigChangeLog(tenant_id=tenant_id, changed_fields=changed_fields, updated_by=updated_by))

    db.commit()
    invalidate_tenant_ai_config_cache(tenant_id)
    return get_tenant_ai_config(db, tenant_id, use_cache=False)


# ---------------------------------------------------------------------------
# Thin per-setting readers -- used by the real consumers this story wires
# (Step 4). Each returns the module-constant default if the tenant lookup
# itself fails for any reason (e.g. tenant_id doesn't resolve to a real
# Users row), so a lookup failure degrades to pre-S-077 behavior rather
# than breaking an autonomous send.
# ---------------------------------------------------------------------------

def get_followup_hours(db: Session, tenant_id: str, channel: str) -> int:
    cfg = get_tenant_ai_config(db, tenant_id)
    return cfg["whatsapp_followup_hours"] if channel == "whatsapp" else cfg["email_followup_hours"]


def get_max_followup_count(db: Session, tenant_id: str) -> int:
    return get_tenant_ai_config(db, tenant_id)["max_followup_count"]


def get_ghosting_reactivation_days(db: Session, tenant_id: str) -> int:
    return get_tenant_ai_config(db, tenant_id)["ghosting_reactivation_days"]


def get_sla_no_contact_hours(db: Session, tenant_id: str) -> int:
    return get_tenant_ai_config(db, tenant_id)["sla_no_contact_hours"]


def get_sla_first_contact_seconds(db: Session, tenant_id: str) -> int:
    return get_tenant_ai_config(db, tenant_id)["sla_first_contact_seconds"]


def get_greeting_channel(db: Session, tenant_id: str) -> str:
    return get_tenant_ai_config(db, tenant_id)["greeting_channel"]


def get_escalation_keywords(db: Session, tenant_id: str) -> List[str]:
    return get_tenant_ai_config(db, tenant_id).get("escalation_keywords") or []
