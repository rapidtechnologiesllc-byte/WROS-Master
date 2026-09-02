"""
HRMS-1104 -- Automated Outreach Agent (Phase 3 Workstream 1 / Recruit),
import logging
EPIC-11, S-319.

One table: outreach_sequences, per S-319_HRMS-1104.docx's Data Mapping
section. This agent never sends via a raw channel API -- every send
goes through app.services.thunder_service.send_thunder_message(), the
same governed path Thunder itself uses, so R-08 ownership and consent
are enforced uniformly (BR-1104-01).
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.models.base import Base

OUTREACH_CHANNELS = ("whatsapp", "linkedin", "email")
OUTREACH_SEQUENCE_STATUSES = (
    "QUEUED", "SENT", "BLOCKED_OWNERSHIP", "COMPLETE_NO_RESPONSE", "RESPONDED",
)
MAX_TOUCHES = 3  # BR-1104-04

logger = logging.getLogger(__name__)

class OutreachSequence(Base):
    __tablename__ = "outreach_sequences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    demand_id = Column(String(512), ForeignKey("demands.id"), nullable=True, index=True)

    message_text = Column(Text, nullable=True)          # max 1000 chars per UI spec
    primary_channel = Column(String(20), nullable=False)  # one of OUTREACH_CHANNELS
    fallback_sequence = Column(Text, nullable=True)       # JSON-encoded remaining channel list

    status = Column(String(30), nullable=False, default="QUEUED")

    # BR-1104-04: capped at 3, enforced at insert -- see
    # app.services.outreach_agent_service._record_touch().
    touch_count = Column(Integer, nullable=False, default = False)

    # Data Mapping: "snapshot, re-checked live at send time, not trusted
    # from snapshot alone" -- this column is informational/audit only,
    # every actual send re-checks thunder_service.has_active_consent().
    consent_given_snapshot = Column(Boolean, nullable=True)

    sent_via = Column(String(512), nullable=True)  # always 'sendThunderMessage' once any send occurs
    last_touch_sent_at = Column(DateTime(timezone=False), nullable=True)
    blocked_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now())
