from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class OfferLetter(Base):
    __tablename__ = "offer_letters"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(String(256), ForeignKey("candidates.candidateID"), nullable=False)
    job_id = Column(String(256), ForeignKey("jobs.jobID"), nullable=True)
    hiring_manager_id = Column(String(256), ForeignKey("users.UserID"), nullable=True)
    reporting_manager_id = Column(String(256), ForeignKey("users.UserID"), nullable=True)

    position = Column(String(256), nullable=False)
    salary = Column(String(256), nullable=False)
    joining_date = Column(Date, nullable=False)
    offer_expire_date = Column(Date, nullable=False)

    # ── Candidate-facing status ───────────────────────────────────────────────
    # Pending → (after generate) AwaitingApproval → (HM approves) Approved →
    # (HR releases) Released → (candidate signs) Accepted | Rejected | Cancelled
    offer_status = Column(String(30), nullable=False, default="Pending")
    candidate_response = Column(Text, nullable=True)
    responded_at = Column(DateTime(timezone=False), nullable=True)

    created_at = Column(DateTime(timezone=False), server_default=func.now())
    created_by = Column(String(256), ForeignKey("users.UserID"), nullable=True)

    cancelled_at = Column(DateTime(timezone=False), nullable=True)
    cancelled_by = Column(String(256), ForeignKey("users.UserID"), nullable=True)

    # ── Document links (populated after generation) ───────────────────────────
    sharepoint_url  = Column(Text, nullable=True)
    download_url    = Column(Text, nullable=True)
    sharepoint_path = Column(Text, nullable=True)

    # ── Hiring Manager Approval workflow ──────────────────────────────────────
    # approval_status: None | AwaitingApproval | Approved | Rejected
    approval_status  = Column(String(30), nullable=True)
    approved_at      = Column(DateTime(timezone=False), nullable=True)
    approved_by      = Column(String(256), ForeignKey("users.UserID"), nullable=True)
    approval_notes   = Column(Text, nullable=True)

    # ── Release to candidate ──────────────────────────────────────────────────
    released_at = Column(DateTime(timezone=False), nullable=True)
    released_by = Column(String(256), ForeignKey("users.UserID"), nullable=True)

    # ── Signature file paths ──────────────────────────────────────────────────
    hm_signature_path        = Column(Text, nullable=True)   # SharePoint path of HM PNG
    candidate_signature_path = Column(Text, nullable=True)   # SharePoint path of candidate PNG
    signed_offer_path        = Column(Text, nullable=True)   # Final docx with both signatures

    # ── Relationships ─────────────────────────────────────────────────────────
    candidate        = relationship("Candidate", foreign_keys=[candidate_id])
    job              = relationship("Jobs", foreign_keys=[job_id])
    hiring_manager   = relationship("Users", foreign_keys=[hiring_manager_id])
    reporting_manager = relationship("Users", foreign_keys=[reporting_manager_id])
    creator          = relationship("Users", foreign_keys=[created_by])
    canceller        = relationship("Users", foreign_keys=[cancelled_by])
    approver         = relationship("Users", foreign_keys=[approved_by])
    releaser         = relationship("Users", foreign_keys=[released_by])
