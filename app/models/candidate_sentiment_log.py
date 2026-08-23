"""
S-036/HRMS-0436 -- Candidate Sentiment Analysis.

candidate_sentiment_log: a real, new, queryable ledger -- distinct from
the append-only ConversationEvent log (a trend check needs "last 5
rows for this candidate ordered by time," which ConversationEvent's
generic event_type/event_data JSON shape doesn't index well for), same
"genuinely new + structured data gets a real table" posture as
CandidateSkillTag/CandidateSLABreach this round.

Uses this codebase's real Integer-autoincrement PK + String(50)
UserID-as-tenant_id conventions (CandidateConversation, ConversationEvent,
CandidateSLABreach all do this), not the spec's UUID PK/tenant_id
assumption. sentiment is a plain String + module-level tuple constant,
not a DB-native ENUM (not used elsewhere in this codebase's real
schema). confidence is Float, matching CandidateSkillTag.confidence,
not the spec's DECIMAL(3,2).

message_event_id points at ConversationEvent.id (the real message log),
not a fictional conversation_messages.id.
"""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base

SENTIMENT_VALUES = ("POSITIVE", "NEUTRAL", "NEGATIVE")


class CandidateSentimentLog(Base):
    __tablename__ = "candidate_sentiment_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("candidate_conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    message_event_id = Column(Integer, ForeignKey("conversation_events.id", ondelete="SET NULL"), nullable=True)

    sentiment = Column(String(20), nullable=False, server_default="NEUTRAL")
    confidence = Column(Float, nullable=False, server_default="0.0")

    analyzed_at = Column(DateTime(timezone=False), server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    conversation = relationship("CandidateConversation", foreign_keys=[conversation_id], lazy="select")

    __table_args__ = (
        Index("ix_candidate_sentiment_log_trend", "candidate_id", "analyzed_at"),
    )
