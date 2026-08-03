"""
S-044/HRMS-0444 -- Multi-Touch Outreach Campaign.

outreach_campaigns/campaign_touchpoints: genuinely new tables. Integer-
autoincrement PK + String(50) UserID-as-tenant_id convention, matching
every other new table this round, not the spec's UUID assumption.
message_event_id FKs into ConversationEvent.id (the real message log;
no conversation_messages table exists).

BR-03 ("only one ACTIVE campaign per candidate") is enforced at the
application layer (query-then-check in start_campaign(), same pattern
CandidateMemoryFact's is_active uniqueness already uses this round),
not a DB partial/filtered unique index -- simpler and portable across
the SQLite test target and the real MSSQL database.

Real, deliberate architectural overlap, flagged not hidden: this is
now the THIRD near-identical "capped multi-touch, stop-on-reply,
cron-driven" outreach mechanism in this codebase, after
follow_up_schedule (S-041/HRMS-0441, triggered by no-response
detection, escalating relative-hour thresholds) and OutreachSequence
(HRMS-1104/S-319, EPIC-11, whatsapp->linkedin->email demand-sourcing
outreach). This one differs in trigger (unconditional, right after
Day-0 first contact -- see outreach_campaign_service's own module
docstring on the spec-internal inconsistency this resolves) and
schedule shape (fixed calendar-day offsets, not relative-hour
escalation). Same explicitly-approved "flag every new addition, don't
silently compound" posture already established for the four
"candidate went silent" mechanisms during S-041/042/043.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base

CAMPAIGN_TYPES = ("STANDARD_OUTREACH",)
CAMPAIGN_STATUSES = ("ACTIVE", "COMPLETED", "CANCELLED")

TOUCHPOINT_CHANNELS = ("whatsapp", "email")
TOUCHPOINT_STATUSES = ("PENDING", "SENT", "SKIPPED", "CANCELLED")


class OutreachCampaign(Base):
    __tablename__ = "outreach_campaigns"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("candidate_conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    campaign_type = Column(String(50), nullable=False, server_default="STANDARD_OUTREACH")
    status = Column(String(20), nullable=False, server_default="ACTIVE")
    started_at = Column(DateTime(timezone=False), nullable=False)
    completed_at = Column(DateTime(timezone=False), nullable=True)
    stop_reason = Column(String(200), nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    conversation = relationship("CandidateConversation", foreign_keys=[conversation_id], lazy="select")

    __table_args__ = (
        Index("ix_outreach_campaigns_active_lookup", "tenant_id", "candidate_id", "status"),
    )


class CampaignTouchpoint(Base):
    __tablename__ = "campaign_touchpoints"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    campaign_id = Column(Integer, ForeignKey("outreach_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)

    touchpoint_number = Column(Integer, nullable=False)
    channel = Column(String(20), nullable=False)
    message_type = Column(String(50), nullable=False)
    scheduled_at = Column(DateTime(timezone=False), nullable=False)
    status = Column(String(20), nullable=False, server_default="PENDING")
    sent_at = Column(DateTime(timezone=False), nullable=True)
    message_event_id = Column(Integer, ForeignKey("conversation_events.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    campaign = relationship("OutreachCampaign", foreign_keys=[campaign_id], lazy="select")

    __table_args__ = (
        Index("ix_campaign_touchpoints_job_queue", "tenant_id", "scheduled_at", "status"),
    )
