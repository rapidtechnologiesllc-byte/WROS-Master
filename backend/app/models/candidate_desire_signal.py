"""
S-347/HRMS-P117 -- Candidate Desire Intelligence Engine.

candidate_desire_signals: a real, new, queryable ledger of every
behavioral signal Thunder observes about a candidate. Same real
conventions as CandidateSentimentLog/CandidateSkillTag this codebase
already established: Integer-autoincrement PK, String(50)
UserID-as-tenant_id, plain String (module-tuple-backed) instead of a
DB-native ENUM, Float not the spec's DECIMAL(3,2).

signal_data is JSON (SQLAlchemy JSON -- SQL Server JSON-as-NVARCHAR,
same as CandidateJobScore.score_breakdown), holding whatever raw
payload that signal_source implies (message text, page/duration,
objection type, response-speed minutes, sentiment score).

Two signal sources (OBJECTION, RESPONSE_SPEED) have a real deterministic
scoring rule in the spec itself (BR-03/BR-04) -- those are scored and
marked processed=True at insert time by desire_signal_service, never
queued for the LLM SignalProcessingJob. Every other source is inserted
unprocessed and picked up by that job.
"""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, JSON, Boolean, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base

SIGNAL_SOURCES = (
    "CHAT_MESSAGE", "WHATSAPP_MESSAGE", "EMAIL_MESSAGE", "PORTAL_PAGE_VIEW",
    "OBJECTION", "QUESTION_ASKED", "RESPONSE_SPEED", "SENTIMENT", "OFFER_QUESTION",
)
DESIRE_CATEGORIES = (
    "CAREER_GROWTH", "COMPENSATION", "STABILITY", "REMOTE_FLEXIBILITY",
    "DOMAIN_INTEREST", "COMPANY_REPUTATION", "WORK_LIFE_BALANCE", "SPEED_OF_DECISION",
)
DESIRE_DIRECTIONS = ("TOWARDS", "AWAY_FROM")


class CandidateDesireSignal(Base):
    __tablename__ = "candidate_desire_signals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)

    signal_source = Column(String(30), nullable=False)  # see SIGNAL_SOURCES
    signal_data = Column(JSON, nullable=False)

    desire_category = Column(String(30), nullable=True)  # see DESIRE_CATEGORIES, filled by processing (or deterministic rule)
    desire_direction = Column(String(20), nullable=True)  # see DESIRE_DIRECTIONS
    desire_strength = Column(Float, nullable=True)  # 0.0-1.0
    extracted_insight = Column(Text, nullable=True)

    processed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    processed_at = Column(DateTime(timezone=False), nullable=True)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")

    __table_args__ = (
        Index("ix_candidate_desire_signals_lookup", "tenant_id", "candidate_id", "created_at"),
        Index("ix_candidate_desire_signals_unprocessed", "processed"),
    )
