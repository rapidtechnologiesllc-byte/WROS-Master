"""
S-359/HRMS-P511 -- HTD Intake Pause Engine: Conversion Rate Breach.

Three small tables rather than the doc's generic `system_config` key-
value store (this codebase has no such table anywhere, and building a
generic config mechanism for exactly one flag would be over-building
for what this story actually needs): a per-tenant singleton pause
flag, a monthly metrics history, and a permanent pause/resume audit
log (AC-6).
"""
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


HTD_PAUSE_LOG_ACTIONS = ("PAUSED", "RESUMED")


class HtdIntakeStatus(Base):
    """One row per tenant -- the live pause flag a future HRMS-0307
    SourcingWorkflowTrigger would check before starting HTD sourcing
    (that trigger doesn't exist in this codebase; is_htd_intake_paused()
    is the real, callable gate a future build of it wires into)."""
    __tablename__ = "htd_intake_status"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, unique=True, index=True)

    is_paused = Column(Boolean, nullable=False, default=False)
    paused_at = Column(DateTime, nullable=True)
    pause_reason = Column(Text, nullable=True)


class HtdMonthlyMetric(Base):
    __tablename__ = "htd_monthly_metrics"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    month_start = Column(Date, nullable=False, index=True)
    cohort_size = Column(Integer, nullable=False)
    converted = Column(Integer, nullable=False)
    # Nullable: an empty cohort (no HTD intake that month) has no rate to
    # compute -- "insufficient data," not a fabricated 0%, same
    # convention as every other rough-estimate calculation this codebase
    # already follows.
    conversion_rate = Column(Numeric(5, 4), nullable=True)

    calculated_at = Column(DateTime, server_default=func.now())


class HtdPauseLogEntry(Base):
    """AC-6: permanent, never-deleted pause/resume history."""
    __tablename__ = "htd_pause_log"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    action = Column(
        Enum(*HTD_PAUSE_LOG_ACTIONS, name="htd_pause_log_action", native_enum=False, create_constraint=True),
        nullable=False,
    )
    reason = Column(Text, nullable=True)
    audit_findings = Column(Text, nullable=True)
    corrective_actions = Column(Text, nullable=True)
    resumed_by = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
