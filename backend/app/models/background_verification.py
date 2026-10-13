from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func

from app.models.base import Base

BGV_STATUSES = ("NOT_STARTED", "IN_PROGRESS", "PASSED", "FAILED", "WAIVED")


class BackgroundVerification(Base):
    """Background verification for a candidate who accepted an offer. A candidate reaches the
    bench (and so a client) only once it is PASSED, or WAIVED with a recorded reason."""
    __tablename__ = "background_verifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    offer_letter_id = Column(Integer, ForeignKey("offer_letters.id"), nullable=True)
    status = Column(String(16), nullable=False, default="NOT_STARTED", index=True)
    vendor_name = Column(String(256), nullable=True)
    vendor_reference = Column(String(256), nullable=True, index=True)
    initiated_at = Column(DateTime, nullable=True)
    verdict_at = Column(DateTime, nullable=True)
    verdict_by = Column(String(512), nullable=True)  # UserID or "vendor:<name>"
    report_url = Column(Text, nullable=True)
    waiver_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("candidate_id", "offer_letter_id", name="uq_bgv_candidate_offer"),)
