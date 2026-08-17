"""
S-074/HRMS-0474 -- Bulk Candidate Engagement Launch.

Real architecture adaptation: no separate `bulk_import_batches`
table -- Step 1's `batch_id` is realized simply as the list of
candidate IDs the import response already returns; the frontend
passes that list straight into `POST /candidates/bulk-engage`
(`candidate_ids`), so `POST .../bulk-engage-batch` (a second variant
keyed by a persisted batch id) is not built as a separate table/route
-- same real data, one real vehicle for it, not two.

`BulkEngagementJob`/`BulkEngagementError` ARE genuinely new (progress
tracking has no existing real substitute) -- Integer/String(36) PK,
String(50) UserID-as-tenant_id convention, matching every other new
table this round.
"""
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


BULK_JOB_STATUSES = ("QUEUED", "PROCESSING", "COMPLETED")


class BulkEngagementJob(Base):
    __tablename__ = "bulk_engagement_jobs"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    recruiter_id = Column(String(50), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)

    candidate_ids = Column(JSON, nullable=False)  # full target list, in order
    total_count = Column(Integer, nullable=False)
    queued_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)  # BR-02: already-engaged candidates
    status = Column(String(20), nullable=False, default="QUEUED")

    created_at = Column(DateTime(timezone=False), server_default=func.now())
    completed_at = Column(DateTime(timezone=False), nullable=True)

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    recruiter = relationship("Users", foreign_keys=[recruiter_id], lazy="select")


class BulkEngagementError(Base):
    __tablename__ = "bulk_engagement_errors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String(36), ForeignKey("bulk_engagement_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=False), server_default=func.now())
