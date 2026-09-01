"""
Candidate Rejection Workflow Model

Tracks candidate rejections with audit trail, reasons, and archival status.
Implements soft-delete pattern for candidates to preserve audit trail.

HRMS Dependencies:
- S-322 (Candidate Rejection Workflow): reject_candidate, send_rejection_email, archive_candidate
- R-01: 5-year experience floor remains enforced at submission time
- R-07: Candidates only created via create_candidate_safe()
"""

from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Boolean, func, Index, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship

from app.models.base import Base


class CandidateRejection(Base):
    """
    Tracks candidate rejections with reason, rejection_date, and who performed the action.
    Soft-delete pattern: Candidate remains in DB, but rejection record marks them as REJECTED.
    """
    __tablename__ = "candidate_rejections"
    __table_args__ = (
        Index("ix_cand_rej_candidate", "candidate_id"),
        Index("ix_cand_rej_rejected_by", "rejected_by_user_id"),
        Index("ix_cand_rej_rejected_at", "rejected_at"),
        Index("ix_cand_rej_status", "rejection_status"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # FK to candidate
    candidate_id = Column(String(256), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)

    # FK to job (optional — rejection may not be job-specific)
    job_id = Column(String(256), ForeignKey("jobs.jobID", ondelete="SET NULL"), nullable=True, index=True)

    # Rejection reason (required)
    rejection_reason = Column(String(256), nullable=False)

    # Detailed note (optional)
    rejection_note = Column(Text, nullable=True)

    # Who rejected (FK to Users)
    rejected_by_user_id = Column(String(256), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)

    # Rejection timestamp
    rejected_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False, index=True)

    # Email sent status
    email_sent = Column(Boolean, nullable=False, server_default="0", default=False)
    email_sent_at = Column(DateTime(timezone=False), nullable=True)

    # Archive status (soft-delete)
    rejection_status = Column(
        SQLAlchemyEnum("ACTIVE", "ARCHIVED", name="rejection_status", native_enum=False),
        nullable=False,
        server_default="ACTIVE",
        default="ACTIVE",
        index=True
    )
    archived_at = Column(DateTime(timezone=False), nullable=True)
    archived_by_user_id = Column(String(256), ForeignKey("users.UserID", ondelete="SET NULL"), nullable=True)

    # Audit trail
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Tenant scoping (R-01: every table has tenant_id, NOT NULL, indexed)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default = True, server_default="1", index=True)

    # Relationships
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    job = relationship("Jobs", foreign_keys=[job_id], lazy="select")
    rejected_by = relationship("Users", foreign_keys=[rejected_by_user_id], lazy="select")
    archived_by = relationship("Users", foreign_keys=[archived_by_user_id], lazy="select")


class CandidateRejectionReason(Base):
    """
    Predefined rejection reasons for standardization.
    Used to populate dropdowns in UI.
    """
    __tablename__ = "candidate_rejection_reasons"
    __table_args__ = (
        Index("ix_cand_rej_reason_tenant", "tenant_id"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Reason code (e.g., "LACK_OF_EXPERIENCE", "FAILED_SCREENING")
    reason_code = Column(String(256), nullable=False, unique=True, index=True)

    # Display label (e.g., "Lacks Required Experience")
    reason_label = Column(String(256), nullable=False)

    # Description
    reason_description = Column(Text, nullable=True)

    # Category (e.g., "Experience", "Skills", "Screening", "Offer", "Other")
    category = Column(String(256), nullable=True)

    # Is this reason active/available for selection?
    is_active = Column(Boolean, nullable=False, server_default="1", default=True)

    # Tenant scoping
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, default = True, server_default="1", index=True)

    # Audit
    created_at = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=False)
