"""
S-213/HRMS-0115 -- System Configuration & Admin Settings Panel.

Generic key/value config, tenant-scoped and optionally BU-scoped (null
business_unit_id = tenant-wide default, per BR-0115-03's COALESCE
resolution). Deliberately NOT a duplicate of the real, already-working
per-tenant AI/conversation config in app.models.tenant_ai_config
(TenantAIConfig) -- that table already has real, tested, wired
consumers (greeting channel, follow-up hours, SLA-for-conversations,
ghosting). This table exists for settings that had no real config home
at all before this story: a few genuinely hardcoded module constants
(confidence thresholds, business-hours window) named explicitly, not
invented -- see system_config_service.KNOWN_CONFIG_KEYS.

Locale (timezone/date format/currency) is likewise NOT duplicated here
-- Tenant already has real, migrated columns for that (S-219/HRMS-0121).
The Admin Settings UI's Locale tab reads/writes those columns directly
through this same service, so there is exactly one source of truth per
setting, never two.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

CONFIG_CATEGORIES = ("AI_THRESHOLDS", "SLA", "CHANNELS")
CONFIG_VALUE_TYPES = ("PERCENT", "INT", "ENUM", "BOOL", "STRING")


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    # Null = tenant-wide default (BR-0115-03); a specific BU row overrides it.
    business_unit_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)

    config_category = Column(String(20), nullable=False)
    config_key = Column(String(100), nullable=False)
    config_value = Column(JSON, nullable=False)

    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=True)

    tenant = relationship("Tenant", foreign_keys=[tenant_id], lazy="select")
    business_unit = relationship("BusinessUnit", foreign_keys=[business_unit_id], lazy="select")

    __table_args__ = (
        # One row per (tenant, BU-or-tenant-wide, key) -- an upsert target,
        # not an append-only history (that's what audit_log is for).
        UniqueConstraint("tenant_id", "business_unit_id", "config_key", name="uq_system_config_scope_key"),
    )
