"""
Internal Note Model
===================
Allows HR team members to attach private, timestamped notes to a candidate
for internal tracking purposes. These notes are NOT visible to the candidate.

Each note records:
  - The candidate it belongs to
  - The note content (free-text)
  - An optional category tag  (e.g. "Background Check", "Salary Negotiation", "General")
  - Who wrote it (HR user ID + display name snapshot)
  - When it was created / last updated
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from app.models.base import Base


class InternalNote(Base):
    __tablename__ = "internal_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # ── Candidate linkage ─────────────────────────────────────────────────────
    candidate_id = Column(
        String(50),
        ForeignKey("candidates.candidateID", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Note content ──────────────────────────────────────────────────────────
    # Free-text note written by the HR user
    content = Column(Text, nullable=False)

    # Optional category to help HR filter / search notes
    # e.g. "General" | "Background Check" | "Salary Negotiation" | "Reference Check"
    category = Column(String(100), nullable=True, default="General")

    # ── Authorship ────────────────────────────────────────────────────────────
    # HR user who created the note
    created_by_id   = Column(String(50), nullable=False)       # user ID
    created_by_name = Column(String(200), nullable=True)       # display name snapshot

    # ── Audit timestamps ──────────────────────────────────────────────────────
    created_at = Column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    candidate = relationship(
        "Candidate",
        foreign_keys=[candidate_id],
        lazy="select",
        backref="internal_notes",
    )
