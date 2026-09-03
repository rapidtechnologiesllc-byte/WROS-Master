"""
import logging
S-021/HRMS-0421 -- Candidate Memory Store.

Uses this codebase's real Integer-autoincrement PK + String(50)
UserID-as-tenant_id conventions (same as CandidateConversation,
ConversationEvent, MessageTemplate, CandidateSLABreach), not the
spec's UUID assumption. source_message_id FKs into ConversationEvent
(no conversation_messages table exists -- same adaptation every
messaging story this round has made).

BR-02 (facts are versioned, history preserved) means a hard DB UNIQUE
constraint on (tenant_id, candidate_id, fact_category, fact_key) is
NOT applied here -- that would make it impossible to keep the
is_active=false historical rows the same rule requires. "At most one
is_active=true row per key" is enforced at the application layer in
candidate_memory_service.upsert_fact() instead; a regular (non-unique)
index on the same columns + is_active supports that lookup.
"""
import logging
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base

FACT_CATEGORIES = (
    "SALARY", "PREFERENCE", "CONSTRAINT", "MOTIVATOR",
    "OBJECTION", "AVAILABILITY", "SKILL", "EMPLOYER", "PERSONAL",
)

LOW_CONFIDENCE_THRESHOLD = 0.7  # BR-03

logger = logging.getLogger(__name__)

class CandidateMemory(Base):
    """BR-01: one record per candidate, shared across all conversations."""
    __tablename__ = "candidate_memory"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    summary = Column(Text, nullable=True)
    last_updated = Column(DateTime(timezone=False), nullable=True)
    version = Column(Integer, nullable=False, server_default="1")

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")

class CandidateMemoryFact(Base):
    __tablename__ = "candidate_memory_facts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)

    fact_category = Column(String(512), nullable=False)
    fact_key = Column(String(512), nullable=False)
    fact_value = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, server_default="1.0")  # BR-03
    source_message_id = Column(Integer, ForeignKey("conversation_events.id", ondelete="SET NULL"), nullable=True)

    extracted_at = Column(DateTime(timezone=False), server_default=func.now())
    is_active = Column(Boolean, nullable=False, server_default="1")  # BR-02

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")

    __table_args__ = (
        Index("ix_candidate_memory_facts_lookup", "candidate_id", "tenant_id", "fact_category", "is_active"),
    )
