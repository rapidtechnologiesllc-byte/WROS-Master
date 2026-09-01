"""
Candidate History Model
=======================
Stores a chronological audit trail / timeline for every candidate.

Each row represents one event in the candidate's journey, for example:
  - Applied for a job
  - Screened by HR
  - Interview scheduled by <user>
  - Interview completed
  - Offer released by <user>
  - Offer accepted / rejected
  - Onboarded
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class CandidateHistory(Base):
    __tablename__ = "candidate_history"

    id              = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # The candidate this event belongs to
    candidateID     = Column(
        String(50),
        ForeignKey("candidates.candidateID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Event metadata ──────────────────────────────────────────────────────
    # Pre-defined event types (open string so callers can extend without a DB change)
    # Recommended values:
    #   "Applied" | "Screening" | "Interview Scheduled" | "Interview Completed"
    #   "Offer Released" | "Offer Accepted" | "Offer Rejected"
    #   "Pre-Onboarding" | "Onboarded" | "Rejected" | "Custom"
    event_type      = Column(String(256), nullable=False)

    # Human-readable description / note (e.g. "Interview scheduled at 3 PM on 15 May")
    note            = Column(Text, nullable=True)

    # Who performed / triggered this event (user ID or name stored as string)
    performed_by_id   = Column(String(256), nullable=True)   # user / HR / admin ID
    performed_by_name = Column(String(256), nullable=True)  # display name snapshot

    # Optional reference IDs to related records
    job_id          = Column(String(256), nullable=True)      # which job this event is for
    interview_id    = Column(Integer, nullable=True)         # FK-less; store raw ID
    offer_letter_id = Column(Integer, nullable=True)         # FK-less; store raw ID

    # When the event actually happened (defaults to now, can be overridden by caller)
    event_at        = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )

    # Audit timestamps
    createdAt       = Column(DateTime(timezone=False), server_default=func.now())

    # Relationship (lazy — only fetched when accessed)
    candidate = relationship(
        "Candidate",
        foreign_keys=[candidateID],
        lazy="select",
        backref="history",
    )
