"""
S-077/HRMS-0477 -- Tenant AI Configuration.

Consolidates Thunder's currently-scattered, per-story config surface
into one admin-editable table. Real architecture note: this does NOT
duplicate the 4 Thunder-identity/pause fields that already live on the
real Users row (ai_agent_name/ai_agent_persona/digest_enabled/
thunder_enabled -- S-011/S-065/S-075, all keyed off the same "tenant_id
resolves to Users.UserID" convention this whole subsystem uses). Moving
those into a second table would mean either dropping live, tested
columns other already-shipped code reads directly
(ai_conversation_service.resolve_thunder_config(), every
send_thunder_message() pause check) or maintaining two sources of
truth for the same setting -- a real drift risk for zero functional
gain. tenant_ai_config_service.get_tenant_ai_config() presents both
sources as ONE unified read; this table only stores the genuinely NEW
settings that had no real backing store before this story (follow-up
timing, ghosting/SLA thresholds, escalation keywords, greeting channel,
qualification field order).

No Redis in this codebase (same gap already flagged for
candidate_context_service's context cache) -- real in-process 5-min
TTL cache instead, same pattern, see tenant_ai_config_service.py.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base

GREETING_CHANNELS = ("WHATSAPP_FIRST", "EMAIL_FIRST", "BOTH_PARALLEL")


class TenantAIConfig(Base):
    __tablename__ = "tenant_ai_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(
        String(50), ForeignKey("users.UserID", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    # BOTH_PARALLEL is the real, live default behavior today
    # (ai_conversation_service.auto_assign_ai_agent_on_creation() fires
    # both first-engagement channels unconditionally) -- this column
    # makes that switchable for the first time.
    greeting_channel = Column(String(20), nullable=False, server_default="BOTH_PARALLEL")
    whatsapp_followup_hours = Column(Integer, nullable=False, server_default="24")
    email_followup_hours = Column(Integer, nullable=False, server_default="48")
    max_followup_count = Column(Integer, nullable=False, server_default="3")
    ghosting_reactivation_days = Column(Integer, nullable=False, server_default="14")
    # S-065's own digest send time was a hardcoded module constant,
    # explicitly flagged there as "not separately configurable" -- this
    # is the first real store for it. "HH:MM", 24h.
    digest_send_time = Column(String(5), nullable=False, server_default="08:00")
    sla_first_contact_seconds = Column(Integer, nullable=False, server_default="60")
    sla_no_contact_hours = Column(Integer, nullable=False, server_default="24")
    # HRMS-0425 field-priority engine has no live consumer anywhere in
    # this codebase yet (same gap S-025/S-073 already flagged) -- stored
    # for real, honestly not wired to anything.
    qualification_field_order = Column(JSON, nullable=True)
    # Merged with (never replacing) the real LEGAL_ESCALATION_KEYWORDS
    # tuple conversation_state_service.trigger_escalation() already
    # checks (S-035).
    escalation_keywords = Column(JSON, nullable=True)

    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=True)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")


class TenantAIConfigChangeLog(Base):
    """AC-7's audit trail. Real substitute for the spec's literal
    'conversation_audit_log' -- app.models.conversation_audit_log.
    ConversationAuditLog.candidate_id is a hard NOT NULL FK (S-076's
    own real constraint), so a candidate-less, tenant-level admin
    action genuinely cannot be logged there. This is a minimal,
    parallel table for exactly that case -- config history UI is
    explicitly out of scope (Section 9 of the spec), so no read
    endpoint beyond what AC-7 itself needs is built here."""

    __tablename__ = "tenant_ai_config_change_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="CASCADE"), nullable=False, index=True)
    changed_fields = Column(JSON, nullable=False)  # {"field": {"before": ..., "after": ...}, ...}
    updated_by = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
