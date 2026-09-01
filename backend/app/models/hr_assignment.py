"""
HR Assignment Model
===================
Links a candidate to one or two HR/Recruiter users for the recruitment process.

Fields:
  - candidate_id   : FK → candidates.candidateID (unique — one active assignment per candidate)
  - hr1_id         : FK → users.UserID  (primary HR/Recruiter — required)
  - hr2_id         : FK → users.UserID  (secondary HR/Recruiter — optional)
  - assigned_by    : FK → users.UserID  (the user who created / last modified this assignment)
  - created_at     : timestamp when the assignment was first created
  - updated_at     : timestamp of the last update
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.models.base import Base


class HRAssignment(Base):
    __tablename__ = "hr_assignments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # The candidate being assigned
    candidate_id = Column(String(256),
        ForeignKey("candidates.candidateID", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,  # only ONE active HR assignment per candidate (upsert pattern)
    )

    # Primary HR / Recruiter (required)
    # NO ACTION on user delete — SQL Server disallows multiple SET NULL FKs to same table (cascade cycle)
    hr1_id = Column(
        String(50),
        ForeignKey("users.UserID", ondelete="NO ACTION"),
        nullable=True,
        index=True,
    )

    # Secondary HR / Recruiter (optional)
    hr2_id = Column(
        String(50),
        ForeignKey("users.UserID", ondelete="NO ACTION"),
        nullable=True,
        index=True,
    )

    # Who created / last modified this assignment
    assigned_by = Column(
        String(50),
        ForeignKey("users.UserID", ondelete="NO ACTION"),
        nullable=True,
    )

    # Audit timestamps
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ORM relationships
    candidate   = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    hr1         = relationship("Users",     foreign_keys=[hr1_id],       lazy="select")
    hr2         = relationship("Users",     foreign_keys=[hr2_id],       lazy="select")
    assigner    = relationship("Users",     foreign_keys=[assigned_by],  lazy="select")
