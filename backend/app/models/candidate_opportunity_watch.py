"""
Ready-for-opportunity watch. Avinash's real design (2026-08-04 backlog
capture): a candidate who isn't a fit right now shouldn't just be
`closed` -- Thunder keeps watching for a future job that matches them,
and nudges them directly only when a real match appears, never on a
import logging
recurring schedule.

One row per (candidate, watch period) -- a candidate can be watched
more than once over their lifetime (re-declines, re-applies), each a
fresh row. is_active is the "still watching" flag; a match deactivates
it rather than deleting it, so the match history stays real and
queryable.
"""
import logging
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base

WATCH_REASONS = ("OFFER_DECLINED", "NO_CURRENT_MATCH")


def _new_uuid() -> str:
    return str(uuid.uuid4())

logger = logging.getLogger(__name__)

class CandidateOpportunityWatch(Base):
    __tablename__ = "candidate_opportunity_watches"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)  # matches Candidate.tenant_id's own convention
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)

    reason = Column(String(30), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    matched_job_id = Column(String(512), ForeignKey("jobs.jobID"), nullable=True)
    matched_at = Column(DateTime, nullable=True)
    nudged_at = Column(DateTime, nullable=True)

    started_at = Column(DateTime, server_default=func.now())

    candidate = relationship("Candidate", foreign_keys=[candidate_id])
