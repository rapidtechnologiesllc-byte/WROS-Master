"""
S-057/HRMS-0457 -- Document Collection Agent.

preboarding_documents: genuinely new table -- one row per (tenant,
candidate, offer, document_type). Integer-autoincrement PK + String(50)
UserID-as-tenant_id convention, matching every other new table this
round, not the spec's UUID assumption. `offer_id` FKs the real,
pre-existing `OfferLetter.id` (Integer PK), not a fictional `offers`
table.

`CANCELLED` is a real, deliberate addition beyond the spec's own
4-value status sketch (PENDING/RECEIVED/VERIFIED/WAIVED) -- BR-01's
own text asks for "cancel all pending reminder jobs" if a candidate's
status changes (withdrawn/declined) mid-collection; there's no
existing status value that means that, so this table gets one rather
than silently reusing WAIVED (which means something different --
"this document isn't required for this candidate" vs. "collection was
abandoned because the candidate isn't joining after all").

Document upload pipeline reality (HRMS-0427, this story's own "Before
You Start" dependency): confirmed by `resume_upload_service.py`'s own
module docstring -- neither WhatsApp (media downloaded, never stored)
nor email (attachments not even requested) actually produce a real
inbound document today. `mark_document_received()`
(`document_collection_service.py`) is real, complete, and tested, but
has no live trigger yet, same honest gap S-027 already flagged for
the identical missing infrastructure.
"""
from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.models.base import Base

DOCUMENT_STATUSES = ("PENDING", "RECEIVED", "VERIFIED", "WAIVED", "CANCELLED")


class PreboardingDocument(Base):
    __tablename__ = "preboarding_documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(256), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(256), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    offer_id = Column(Integer, ForeignKey("offer_letters.id", ondelete="CASCADE"), nullable=False, index=True)

    document_type = Column(String(256), nullable=False)
    document_label = Column(String(256), nullable=False)
    status = Column(
        Enum(*DOCUMENT_STATUSES, name="preboarding_document_status", native_enum=False, create_constraint=True),
        nullable=False, server_default="PENDING",
    )
    document_url = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=False), nullable=True)
    reminder_count = Column(Integer, nullable=False, server_default="0")
    last_reminded_at = Column(DateTime(timezone=False), nullable=True)
    is_mandatory = Column(Boolean, nullable=False, server_default="1")

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    offer = relationship("OfferLetter", foreign_keys=[offer_id], lazy="select")

    __table_args__ = (
        UniqueConstraint("tenant_id", "candidate_id", "offer_id", "document_type", name="uq_preboarding_document"),
    )
