"""
import logging
S-213/HRMS-0115 -- System Configuration & Admin Settings Panel.

Real config keys seeded below are genuinely hardcoded module constants
found in this codebase (not invented values) -- see each ConfigKeySpec's
`source` note. Two are wired end-to-end as proof the read path really
works, not just inert storage: get_config_value() is called from
app.services.facts_extraction_service in place of the module constant
it used to hard-import, and from app.services.notification_service's
business-hours check. Every other seeded key has a real default matching
current behavior, ready for the same treatment without a schema change.

Locale (timezone/date format/currency) is NOT a system_config category --
Tenant already has real, migrated columns for it (S-219/HRMS-0121,
app.models.tenant.Tenant). get_settings_panel()/update_locale() read and
write those columns directly so there's exactly one source of truth,
never a shadow copy in this table.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.audit import write_audit_log
from app.models.client import BILLING_CURRENCIES
from app.models.system_config import CONFIG_CATEGORIES, SystemConfig
from app.models.tenant import TENANT_DATE_FORMATS, Tenant

CACHE_TTL_SECONDS = 60  # AC-4 -- a saved change must be visible within 60s
_CONFIG_CACHE: Dict[Tuple[int, Optional[int], str], Tuple[float, Any]] = {}

logger = logging.getLogger(__name__)

class UnknownConfigKey(Exception):
    pass


class InvalidConfigValue(Exception):
    pass


@dataclass
class ConfigKeySpec:
    key: str
    category: str
    value_type: str  # PERCENT | INT | ENUM
    default: Any
    label: str
    source: str
    enum_values: Optional[Tuple[str, ...]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


KNOWN_CONFIG_KEYS: Dict[str, ConfigKeySpec] = {
    "low_confidence_threshold": ConfigKeySpec(
        key="low_confidence_threshold", category="AI_THRESHOLDS", value_type="PERCENT", default=0.7,
        label="Candidate memory: low-confidence fact threshold",
        source="app.models.candidate_memory.LOW_CONFIDENCE_THRESHOLD (BR-03)",
        min_value=0.0, max_value=1.0,
    ),
    "profile_update_confidence_threshold": ConfigKeySpec(
        key="profile_update_confidence_threshold", category="AI_THRESHOLDS", value_type="PERCENT", default=0.5,
        label="Minimum confidence to auto-apply a profile field update",
        source="app.services.facts_extraction_service.PROFILE_UPDATE_CONFIDENCE_THRESHOLD (BR-03) -- wired live",
        min_value=0.0, max_value=1.0,
    ),
    "response_parser_confidence_threshold": ConfigKeySpec(
        key="response_parser_confidence_threshold", category="AI_THRESHOLDS", value_type="PERCENT", default=0.6,
        label="Minimum confidence to accept a parsed candidate response",
        source="app.services.response_parser_service.CONFIDENCE_THRESHOLD (BR-01)",
        min_value=0.0, max_value=1.0,
    ),
    # No SLA key seeded yet: the one real candidate found
    # (sla_monitoring_service.NO_CONTACT_THRESHOLD_HOURS) already routes
    # through TenantAIConfig.sla_no_contact_hours whenever a tenant_id is
    # available (sla_monitoring_service.py's own get_sla_no_contact_hours()
    # wrapper) -- adding it here too would be a third, competing source of
    # truth for the same real setting, not a new one. The SLA tab stays in
    # the UI (matching the spec's category grouping) but is honestly empty
    # until a genuinely uncentralized SLA setting is found.
    "business_hours_start": ConfigKeySpec(
        key="business_hours_start", category="CHANNELS", value_type="INT", default=8,
        label="Business hours start (24h, local)",
        source="app.services.notification_service.BUSINESS_HOURS_START -- wired live",
        min_value=0, max_value=23,
    ),
    "business_hours_end": ConfigKeySpec(
        key="business_hours_end", category="CHANNELS", value_type="INT", default=20,
        label="Business hours end (24h, local)",
        source="app.services.notification_service.BUSINESS_HOURS_END",
        min_value=1, max_value=24,
    ),
}


def _validate_value(spec: ConfigKeySpec, value: Any) -> Any:
    if spec.value_type in ("PERCENT", "INT"):
        try:
            value = float(value) if spec.value_type == "PERCENT" else int(value)
        except (TypeError, ValueError):
            raise InvalidConfigValue(f"'{spec.key}' must be a {spec.value_type.lower()}.")
        if spec.min_value is not None and value < spec.min_value:
            raise InvalidConfigValue(f"'{spec.key}' must be >= {spec.min_value}.")
        if spec.max_value is not None and value > spec.max_value:
            raise InvalidConfigValue(f"'{spec.key}' must be <= {spec.max_value}.")
    elif spec.value_type == "ENUM":
        if spec.enum_values and value not in spec.enum_values:
            raise InvalidConfigValue(f"'{spec.key}' must be one of {spec.enum_values}.")
    return value


def _cache_key(tenant_id: int, business_unit_id: Optional[int], key: str) -> Tuple[int, Optional[int], str]:
    return (tenant_id, business_unit_id, key)


def invalidate_config_cache(tenant_id: int, key: Optional[str] = None) -> None:
    if key is None:
        for cache_key in list(_CONFIG_CACHE):
            if cache_key[0] == tenant_id:
                _CONFIG_CACHE.pop(cache_key, None)
    else:
        for cache_key in list(_CONFIG_CACHE):
            if cache_key[0] == tenant_id and cache_key[2] == key:
                _CONFIG_CACHE.pop(cache_key, None)


def get_config_value(
    db: Session, *, tenant_id: int, key: str, business_unit_id: Optional[int] = None, use_cache: bool = True,
) -> Any:
    """
    BR-0115-03 resolution: BU-specific override, else tenant default,
    else the key's real fallback default (so a lookup failure -- or this
    key simply never having been configured -- degrades to today's
    hardcoded behavior rather than breaking a caller).
    """
    spec = KNOWN_CONFIG_KEYS.get(key)
    if spec is None:
        raise UnknownConfigKey(f"Unknown config key '{key}'.")

    ck = _cache_key(tenant_id, business_unit_id, key)
    if use_cache:
        cached = _CONFIG_CACHE.get(ck)
        if cached is not None and cached[0] > time.monotonic():
            return cached[1]

    value = spec.default
    if business_unit_id is not None:
        bu_row = (
            db.query(SystemConfig)
            .filter(SystemConfig.tenant_id == tenant_id, SystemConfig.business_unit_id == business_unit_id, SystemConfig.config_key == key)
            .first()
        )
        if bu_row is not None:
            value = bu_row.config_value
    if value == spec.default:
        tenant_row = (
            db.query(SystemConfig)
            .filter(SystemConfig.tenant_id == tenant_id, SystemConfig.business_unit_id.is_(None), SystemConfig.config_key == key)
            .first()
        )
        if tenant_row is not None:
            value = tenant_row.config_value

    if use_cache:
        _CONFIG_CACHE[ck] = (time.monotonic() + CACHE_TTL_SECONDS, value)
    return value


def set_config_value(
    db: Session, *, tenant_id: int, key: str, value: Any, updated_by: str, business_unit_id: Optional[int] = None,
) -> SystemConfig:
    """BR-0115-02: writes exactly one audit_log entry with before/after,
    in the same commit as the config write (write_audit_log's own
    atomicity contract -- see app.core.audit)."""
    spec = KNOWN_CONFIG_KEYS.get(key)
    if spec is None:
        raise UnknownConfigKey(f"Unknown config key '{key}'.")
    value = _validate_value(spec, value)

    row = (
        db.query(SystemConfig)
        .filter(SystemConfig.tenant_id == tenant_id, SystemConfig.business_unit_id == business_unit_id, SystemConfig.config_key == key)
        .first()
    )
    old_value = row.config_value if row is not None else None
    if row is None:
        row = SystemConfig(
            tenant_id=tenant_id, business_unit_id=business_unit_id,
            config_category=spec.category, config_key=key, config_value=value, updated_by=updated_by,
        )
        db.add(row)
    else:
        row.config_value = value
        row.updated_by = updated_by
        db.add(row)

    write_audit_log(
        db, tenant_id=tenant_id, entity_type="system_config", entity_id=key, action="update",
        user_id=updated_by, old_value=str(old_value), new_value=str(value),
    )
    db.commit()
    invalidate_config_cache(tenant_id, key)
    return row


def get_locale_config(db: Session, tenant_id: int) -> Dict:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise ValueError(f"Tenant '{tenant_id}' not found.")
    return {
        "default_timezone": tenant.default_timezone,
        "default_date_format": tenant.default_date_format,
        "default_currency": tenant.default_currency,
    }


def update_locale_config(db: Session, tenant_id: int, updates: Dict, *, updated_by: str) -> Dict:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise ValueError(f"Tenant '{tenant_id}' not found.")

    if "default_date_format" in updates and updates["default_date_format"] not in TENANT_DATE_FORMATS:
        raise InvalidConfigValue(f"default_date_format must be one of {TENANT_DATE_FORMATS}.")
    if "default_currency" in updates and updates["default_currency"] not in BILLING_CURRENCIES:
        raise InvalidConfigValue(f"default_currency must be one of {BILLING_CURRENCIES}.")

    before = get_locale_config(db, tenant_id)
    changed = False
    for field_name in ("default_timezone", "default_date_format", "default_currency"):
        if field_name in updates and updates[field_name] != before[field_name]:
            setattr(tenant, field_name, updates[field_name])
            changed = True

    if changed:
        db.add(tenant)
        write_audit_log(
            db, tenant_id=tenant_id, entity_type="tenant_locale", entity_id=str(tenant_id), action="update",
            user_id=updated_by, old_value=str(before), new_value=str(get_locale_config(db, tenant_id)),
        )
        db.commit()
    return get_locale_config(db, tenant_id)


def get_settings_panel(db: Session, *, tenant_id: int, business_unit_id: Optional[int] = None) -> Dict:
    """One unified read for the Admin Settings screen, grouped by
    category (AI Thresholds / SLA / Channels / Locale) -- same shape as
    the UI's own tab grouping."""
    categories: Dict[str, List[Dict]] = {c: [] for c in CONFIG_CATEGORIES}
    for spec in KNOWN_CONFIG_KEYS.values():
        categories[spec.category].append({
            "config_key": spec.key,
            "label": spec.label,
            "value_type": spec.value_type,
            "value": get_config_value(db, tenant_id=tenant_id, key=spec.key, business_unit_id=business_unit_id),
            "default": spec.default,
            "min_value": spec.min_value,
            "max_value": spec.max_value,
            "enum_values": list(spec.enum_values) if spec.enum_values else None,
        })
    return {
        "AI_THRESHOLDS": categories["AI_THRESHOLDS"],
        "SLA": categories["SLA"],
        "CHANNELS": categories["CHANNELS"],
        "LOCALE": get_locale_config(db, tenant_id),
    }
