"""
HRMS-0312: Offer Management Model
Comprehensive offer lifecycle tracking with approval workflows.
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, BigInteger,
    Boolean, Date, func, JSON
)
from sqlalchemy.orm import relationship
import logging
from app.models.base import Base

logger = logging.getLogger(__name__)

class OfferStatus(str, Enum):
    """Offer lifecycle status values."""
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SENT = "SENT"
    REVIEWED = "REVIEWED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    RETRACTED = "RETRACTED"
    EXPIRED = "EXPIRED"
    SIGNED = "SIGNED"

class Offer(Base):
    """
    Complete offer record tracking candidate offers through approval and acceptance.

    Workflow:
    DRAFT → APPROVED → SENT → (REVIEWED) → ACCEPTED → SIGNED
                                        → REJECTED
                                        → RETRACTED
    """
    __tablename__ = "offers"

    # ── Identity ──────────────────────────────────────────────────────────────
    id = Column(String(512), primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # ── Foreign Keys ──────────────────────────────────────────────────────────
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"),
                         nullable=False, index=True)
    job_id = Column(String(512), ForeignKey("jobs.jobID"), nullable=False, index=True)
    created_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=False)

    # ── Offer Details ─────────────────────────────────────────────────────────
    position_title = Column(String(512), nullable=False)
    base_salary_usd_cents = Column(BigInteger, nullable=False)  # Base annual salary in USD cents
    signing_bonus_usd_cents = Column(BigInteger, default = False, nullable=False)  # One-time signing bonus
    benefits = Column(JSON, default={}, nullable=False)  # Health insurance, 401k, PTO, etc.

    # ── Dates ─────────────────────────────────────────────────────────────────
    expected_start_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    sent_at = Column(DateTime(timezone=False), nullable=True)
    expiration_date = Column(DateTime(timezone=False), nullable=True)  # Offer expires if not accepted

    # ── Status Tracking ───────────────────────────────────────────────────────
    status = Column(String(20), default=OfferStatus.DRAFT, nullable=False, index=True)

    # ── Approval Workflow ─────────────────────────────────────────────────────
    approved_by_user_id = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    approved_at = Column(DateTime(timezone=False), nullable=True)
    approval_notes = Column(Text, nullable=True)

    # ── Candidate Response ────────────────────────────────────────────────────
    sent_to_email = Column(String(512), nullable=True)
    accepted_by_candidate_id = Column(String(512), ForeignKey("candidates.candidateID"),
                                     nullable=True)
    accepted_at = Column(DateTime(timezone=False), nullable=True)

    rejected_at = Column(DateTime(timezone=False), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    retracted_at = Column(DateTime(timezone=False), nullable=True)
    retraction_reason = Column(Text, nullable=True)

    signed_at = Column(DateTime(timezone=False), nullable=True)
    signature_path = Column(Text, nullable=True)  # Document storage path

    # ── Document References ───────────────────────────────────────────────────
    document_url = Column(Text, nullable=True)  # External URL to offer document
    document_path = Column(Text, nullable=True)  # Internal storage path
    signed_document_url = Column(Text, nullable=True)  # Final signed document URL
    signed_document_path = Column(Text, nullable=True)

    # ── Audit Fields ──────────────────────────────────────────────────────────
    updated_at = Column(DateTime(timezone=False), server_default=func.now(),
                       onupdate=func.now(), nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    candidate = relationship("Candidate", foreign_keys=[candidate_id],
                            lazy="select", backref="offers")
    job = relationship("Jobs", foreign_keys=[job_id], lazy="select")
    created_by = relationship("Users", foreign_keys=[created_by_user_id],
                             lazy="select")
    approved_by = relationship("Users", foreign_keys=[approved_by_user_id],
                              lazy="select")

    def __repr__(self):
        return f"<Offer(id={self.id}, candidate={self.candidate_id}, status={self.status})>"
