"""
import logging
S-058/HRMS-0458 -- Joining Readiness Score.

candidate_joining_scores: genuinely new table -- one row per (tenant,
candidate, offer), UPSERTed on every recalculation (not append-only).
Integer-autoincrement PK + String(50) UserID-as-tenant_id convention,
matching every other new table this round, not the spec's UUID
assumption. `offer_id` FKs the real, pre-existing `OfferLetter.id`
(Integer PK) -- no fictional `offers` table (same real substitute
S-057's `preboarding_documents` already established).

BR-02: this is genuinely distinct from HRMS-0407's profile
completeness score (a different table, different stage, different
question -- "is this candidate's qualification data complete" vs. "is
this candidate about to actually show up on day one"). Never combined
or confused here.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

logger = logging.getLogger(__name__)

class CandidateJoiningScore(Base):
    __tablename__ = "candidate_joining_scores"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    offer_id = Column(Integer, ForeignKey("offer_letters.id", ondelete="CASCADE"), nullable=False, index=True)

    readiness_score = Column(Integer, nullable=False)
    score_breakdown = Column(JSON, nullable=True)
    calculated_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    offer = relationship("OfferLetter", foreign_keys=[offer_id], lazy="select")

    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", "offer_id", name="uq_candidate_joining_score"),
    )
