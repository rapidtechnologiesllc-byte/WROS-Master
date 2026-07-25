"""
S-041/HRMS-0441 -- Follow-Up Scheduler.

follow_up_schedule: genuinely new table -- a real, queryable, job-driven
schedule (needs "all PENDING rows due now" and "does a PENDING row
exist for this candidate" lookups), not derivable from ConversationEvent's
append-only log. Integer-autoincrement PK + String(50)
UserID-as-tenant_id convention, matching every other new table this
round, not the spec's UUID assumption.

channel/status use this round's "new enum-like field -> plain String +
tuple constant" convention. channel is lowercase ("whatsapp"/"email"),
matching CandidateConversation.channel_preference's existing
convention; status is UPPERCASE (PENDING/SENT/CANCELLED/SKIPPED),
matching this round's other brand-new enum fields (FACT_CATEGORIES,
SENTIMENT_VALUES, SKILL_TAG_SOURCES, FLAG_TYPES/SEVERITIES) -- the
established split is: the ORIGINAL pre-EPIC-04 three-axis conversation
state model is lowercase, new fields introduced this round are
uppercase.

triggered_by_message_id FKs into ConversationEvent.id (the real
message log; no conversation_messages table exists). Column name kept
as the spec's own Step 1 table-schema name even though Step 2's
function signature and the data-mapping table call the identical
concept "original_message_id" -- a real spec-internal naming
inconsistency, not resolved by picking one name globally; each
reference in code matches whichever spec section it's implementing
(the DB column vs. the schedule_follow_up() parameter).
"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base

FOLLOWUP_CHANNELS = ("whatsapp", "email")
FOLLOWUP_STATUSES = ("PENDING", "SENT", "CANCELLED", "SKIPPED")
MAX_FOLLOWUPS = 3  # BR-01: never a 4th


class FollowUpSchedule(Base):
    __tablename__ = "follow_up_schedule"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("candidate_conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    channel = Column(String(20), nullable=False)
    scheduled_at = Column(DateTime(timezone=False), nullable=False)
    status = Column(String(20), nullable=False, server_default="PENDING")
    follow_up_number = Column(Integer, nullable=False)
    # The original unanswered message this follow-up chain is responding
    # to -- see module docstring on the triggered_by_message_id/
    # original_message_id naming split.
    triggered_by_message_id = Column(Integer, ForeignKey("conversation_events.id", ondelete="SET NULL"), nullable=True)
    sent_at = Column(DateTime(timezone=False), nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    conversation = relationship("CandidateConversation", foreign_keys=[conversation_id], lazy="select")

    __table_args__ = (
        Index("ix_follow_up_schedule_job_queue", "tenant_id", "scheduled_at", "status"),
    )
