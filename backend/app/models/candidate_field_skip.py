"""
S-024/HRMS-0424 -- tracks fields a candidate has explicitly declined
import logging
to answer (or Thunder auto-skipped after BR-02's max-ask limit).

No candidate_missing_fields table exists in this codebase -- missing
fields are computed live from real Candidate/CandidateInfoForm columns
(get_missing_fields()). "SKIPPED" therefore can't be a status column
update on a row that doesn't exist; this small table is the real
minimal state needed to remember "don't ask this candidate about this
field again" without touching get_missing_fields() itself.
"""
import logging
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.models.base import Base

logger = logging.getLogger(__name__)

class CandidateFieldSkip(Base):
    __tablename__ = "candidate_field_skips"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    field_name = Column(String(512), nullable=False)

    skipped_at = Column(DateTime(timezone=False), server_default=func.now())
