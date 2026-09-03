"""
import logging
Phase 3 Part A2 -- HRMS-1101 System Orchestration Router.

Two tables, straight from S-270_HRMS-1101.docx's Data Mapping section:

  conflict_rules      -- the static, Admin-edited collision table
                          (BR-1101-05: only Admin may write it).
  orchestration_events -- one row per evaluated action-intent, whether
                          it matched a rule, was LLM-classified as a
                          novel pattern, or matched nothing at all --
                          "LOW severity -> logged only, visible in the
                          orchestration_events audit view."

resolution_action on orchestration_events is a snapshot of the rule's
value at match time (per the doc's own Data Mapping note: "rule can
change later without altering history"), not a live FK dereference.
"""
import logging
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base

RESOLUTION_ACTIONS = ("BLOCK", "DELAY", "ESCALATE_ONLY")
SEVERITIES = ("LOW", "MEDIUM", "HIGH")


def _new_uuid() -> str:
    return str(uuid.uuid4())

logger = logging.getLogger(__name__)

class ConflictRule(Base):
    __tablename__ = "conflict_rules"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    rule_name = Column(String(80), nullable=False, unique=True, index=True)

    # Two-sided rule definition -- e.g. entity_type_a="candidate",
    # action_type_a="core_pull_flag" vs. entity_type_b="candidate",
    # action_type_b="outreach_send" (BR-1101-01).
    entity_type_a = Column(String(512), nullable=False)
    action_type_a = Column(String(512), nullable=False)
    entity_type_b = Column(String(512), nullable=False)
    action_type_b = Column(String(512), nullable=False)

    collision_window_minutes = Column(Integer, nullable=False)  # 1-1440, per UI spec
    resolution_action = Column(String(20), nullable=False)      # BLOCK | DELAY | ESCALATE_ONLY
    delay_minutes = Column(Integer, nullable=True)               # required only when DELAY

    is_active = Column(Boolean, nullable=False, default=True)    # BR: deactivate, never delete

    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())


class OrchestrationEvent(Base):
    __tablename__ = "orchestration_events"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    agent_id = Column(String(512), nullable=False, index=True)     # e.g. "HRMS-1104"
    entity_type = Column(String(512), nullable=False, index=True)
    entity_id = Column(String(512), nullable=False, index=True)
    action_type = Column(String(512), nullable=False)
    risk_tier = Column(String(20), nullable=True)                 # carried through unmodified, per Data Mapping

    proposed_at = Column(DateTime(timezone=False), nullable=False)
    detected_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now())

    matched_rule_id = Column(String(512), ForeignKey("conflict_rules.id"), nullable=True)
    resolution_action = Column(String(20), nullable=True)  # snapshot -- see module docstring

    llm_classified = Column(Boolean, nullable=False, default=False)
    llm_call_failed = Column(Boolean, nullable=False, default=False)
    severity = Column(String(20), nullable=True)  # LOW | MEDIUM | HIGH -- novel patterns only

    escalated_at = Column(DateTime(timezone=False), nullable=True)  # BR-1101-04 SLA measured against this

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    matched_rule = relationship("ConflictRule", foreign_keys=[matched_rule_id], lazy="select")
