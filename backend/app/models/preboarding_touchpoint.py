"""
import logging
S-067/HRMS-0467 -- Onboarding Agent.

Real architecture adaptation: D+1 ("D_PLUS_1", check-in the day after
joining) is NOT scheduled upfront alongside D-7/D-3/D-1. Step 1 lists
it as a real touchpoint, but Step 4's own completion condition ("all
touchpoints SENT") is what triggers onboarding.complete -> HRMS-0708
employee conversion -- and Step 1 itself says D+1 only fires "if
employee record created," which can only be true AFTER that same
conversion. Scheduling D+1 upfront would make the story's own
completion check depend on a touchpoint that can't exist yet -- a
real, unresolved circularity in the spec's own step ordering. Resolved
here by creating the D_PLUS_1 row only at the moment completion is
first detected (see onboarding_agent_service.check_onboarding_
completion()), which doubles as this table's own idempotency guard:
its presence means "onboarding.complete has already been handled for
this candidate," so HR is never notified twice.
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base

TOUCHPOINT_TYPES = ("D7", "D3", "D1", "D_PLUS_1")
TOUCHPOINT_STATUSES = ("PENDING", "SENT", "CANCELLED")

logger = logging.getLogger(__name__)

class PreboardingTouchpoint(Base):
    __tablename__ = "preboarding_touchpoints"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    offer_id = Column(Integer, ForeignKey("offer_letters.id", ondelete="CASCADE"), nullable=False, index=True)
    touchpoint_type = Column(String(20), nullable=False)
    scheduled_at = Column(DateTime(timezone=False), nullable=False)
    status = Column(String(20), nullable=False, server_default="PENDING")
    sent_at = Column(DateTime(timezone=False), nullable=True)
    created_at = Column(DateTime(timezone=False), server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
