"""
S-042/HRMS-0442 -- No Response Detection.

candidate_no_response_log: genuinely new table, real audit trail of
every detection event (Step 2's own "log every detection event for
audit and analytics"). Integer-autoincrement PK + String(50)
UserID-as-tenant_id convention, matching every other new table this
round. last_outbound_message_id FKs into ConversationEvent.id (the
real message log; no conversation_messages table exists).
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base

NO_RESPONSE_DETECTION_TYPES = ("FIRST_NO_RESPONSE", "SECOND_NO_RESPONSE", "THIRD_NO_RESPONSE", "POST_THIRD")


class CandidateNoResponseLog(Base):
    __tablename__ = "candidate_no_response_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("candidate_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    last_outbound_message_id = Column(Integer, ForeignKey("conversation_events.id", ondelete="SET NULL"), nullable=True)

    detection_type = Column(String(20), nullable=False)
    detected_at = Column(DateTime(timezone=False), server_default=func.now())
    follow_up_scheduled_at = Column(DateTime(timezone=False), nullable=True)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    conversation = relationship("CandidateConversation", foreign_keys=[conversation_id], lazy="select")
