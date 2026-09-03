"""
Candidate Ownership Model
=========================
Tracks whether a candidate belongs to the Org Pool (visible to all BUs)
import logging
or is exclusively owned by a specific Business Unit.

State machine:
  Org Pool  →  BU Owned   (when assigned to a job with a BU)
  BU Owned  →  Org Pool   (BU rejects at interview, candidate rejects offer,
                            or 90-day ownership lock expires)
"""

import logging
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.models.base import Base


# Pool status constants — use these everywhere, never raw strings
POOL_ORG   = "Org Pool"
POOL_BU    = "BU Owned"

logger = logging.getLogger(__name__)

class CandidateOwnership(Base):
    __tablename__ = "candidate_ownership"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # The candidate this record belongs to
    candidateID = Column(
        String(50),
        ForeignKey("candidates.candidateID", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,       # only ONE active record per candidate (upsert pattern)
    )

    # ── Pool status ───────────────────────────────────────────────────────────
    pool_status = Column(
        String(20),
        nullable=False,
        default=POOL_ORG,
        server_default=POOL_ORG,
    )

    # Which BU currently owns the candidate (null when Org Pool)
    owned_by_bu_id = Column(
        Integer,
        ForeignKey("business_units.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Human-readable BU name snapshot (stored so it survives BU renames)
    owned_by_bu_name = Column(String(512), nullable=True)

    # Why the status was set — e.g. "Assigned to job JOB-42", "BU Rejected"
    ownership_reason = Column(String(512), nullable=True)

    # When BU ownership was acquired (null for Org Pool rows)
    bu_owned_since = Column(DateTime(timezone=False), nullable=True)

    # 90-day expiry: set when offer is created; null = no expiry
    bu_ownership_expires_at = Column(DateTime(timezone=False), nullable=True)

    # Audit
    created_at = Column(DateTime(timezone=False), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    candidate    = relationship("Candidate",     foreign_keys=[candidateID], lazy="select")
    business_unit = relationship("BusinessUnit", foreign_keys=[owned_by_bu_id], lazy="select")
