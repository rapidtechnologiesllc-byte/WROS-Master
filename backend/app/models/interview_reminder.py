"""
S-050/HRMS-0450 -- Interview Reminder Engine.

interview_reminders: genuinely new table -- one row per
(interview, reminder_type). String(36) UUID PK + Integer tenant_id
(matches SubmissionInterview's own convention family -- this table
hangs directly off submission_interviews, not the String(50)
UserID-as-tenant_id convention the candidate-conversation-era EPIC-04
tables use).

No `interviews.candidate_timezone` column exists (the spec's own
"Before You Start" assumption) -- `Candidate.timezone` (the same real
field S-047/048/049 already use) is read fresh at send time instead of
being duplicated onto this table or the interview row.
"""
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


REMINDER_TYPES = ("24H_BEFORE", "1H_BEFORE")
REMINDER_STATUSES = ("PENDING", "SENT", "CANCELLED")


class InterviewReminder(Base):
    __tablename__ = "interview_reminders"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    interview_id = Column(String(36), ForeignKey("submission_interviews.id"), nullable=False, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False, index=True)

    reminder_type = Column(
        Enum(*REMINDER_TYPES, name="interview_reminder_type", native_enum=False, create_constraint=True),
        nullable=False,
    )
    scheduled_at = Column(DateTime, nullable=False)
    status = Column(
        Enum(*REMINDER_STATUSES, name="interview_reminder_status", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING",
    )
    sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    interview = relationship("SubmissionInterview", foreign_keys=[interview_id], lazy="select")
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
