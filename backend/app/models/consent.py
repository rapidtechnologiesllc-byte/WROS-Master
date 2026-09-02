import logging
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func

from app.models.base import Base

logger = logging.getLogger(__name__)

class ConsentRecord(Base):
    """
    Phase 1 B6 -- general-purpose consent capture, honored by any story
    that needs it (e.g. HRMS-1501's Interview Integrity Analysis consent
    gate builds on this rather than storing its own consent flag).
    """
    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    subject_type = Column(String(512), nullable=False)   # e.g. "candidate", "employee"
    subject_id = Column(String(512), nullable=False, index=True)
    consent_type = Column(String(512), nullable=False, index=True)  # e.g. "whatsapp_outreach", "interview_recording"
    consent_given = Column(Boolean, nullable=False)
    captured_at = Column(DateTime(timezone=False), server_default=func.now())
    captured_by = Column(String(512), nullable=True)  # user_id, or "candidate_self_service"
