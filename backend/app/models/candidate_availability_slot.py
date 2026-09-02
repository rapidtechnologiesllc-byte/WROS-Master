"""
import logging
S-047/HRMS-0447 -- Interview Availability Collection.

candidate_availability_slots: genuinely new table -- one row per
candidate-proposed interview time window. Integer-autoincrement PK +
String(50) UserID-as-tenant_id / candidateID-as-candidate_id
convention, matching every other new table this round, not the spec's
UUID assumption.

slot_source distinguishes candidate-message-parsed slots
('CANDIDATE_MESSAGE', the only source this story writes) from a future
recruiter-entered slot ('MANUAL', not built by this story -- no
recruiter-facing UI/endpoint exists for it yet, included as a column
value only so a future story doesn't need a migration to add it).

is_confirmed is reserved for HRMS-0448 (Interviewer Calendar Matching)
to flip once a slot is actually booked -- that story doesn't exist in
this codebase yet, so every slot this story writes stays
is_confirmed=false; see interview_availability_service's own module
docstring for the full "no calendar-matching consumer exists yet" note.
"""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, Time, func
from sqlalchemy.orm import relationship

from app.models.base import Base

SLOT_SOURCES = ("CANDIDATE_MESSAGE", "MANUAL")

logger = logging.getLogger(__name__)

class CandidateAvailabilitySlot(Base):
    __tablename__ = "candidate_availability_slots"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    tenant_id = Column(String(512), ForeignKey("users.UserID", ondelete="NO ACTION"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("candidate_conversations.id", ondelete="CASCADE"), nullable=False, index=True)

    slot_date = Column(Date, nullable=False)
    slot_start_time = Column(Time, nullable=False)
    slot_end_time = Column(Time, nullable=False)
    timezone = Column(String(512), nullable=False)

    is_confirmed = Column(Boolean, nullable=False, server_default="0")
    slot_source = Column(String(20), nullable=False, server_default="CANDIDATE_MESSAGE")

    created_at = Column(DateTime(timezone=False), server_default=func.now())

    tenant = relationship("Users", foreign_keys=[tenant_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    conversation = relationship("CandidateConversation", foreign_keys=[conversation_id], lazy="select")
