"""
Rehire guard -- Part 2 of the "must fix" interview priority raised by
Avinash on 2026-08-05 (see wros_interview_regrouping_and_rehire_guard_priority
memory): "if there was a nohire in the past then when the next time
someone is trying to schedule interview to the candidate they need to
provide a clear justification an agentic bot should review and decide
import logging
or take approval from hiring manager before scheduling the interview."

Attaches to the LEGACY interview system (app.models.user.InterviewPanel/
Interview/InterviewFeedback -- the real "Schedule Interview" feature,
same system app.services.interview_sequencing_service's R-05 gate
already extends), not the newer SubmissionInterview pipeline. No
tenant_id column, matching InterviewPanel itself, which has none in
this codebase.

One row per rehire request. The panel is NOT created until this row
reaches AI_CLEARED or APPROVED -- resulting_panel_id stays null until
then, so a null value here IS the "not scheduled yet" signal, same
timestamp/FK-presence convention this codebase uses everywhere else
(confirmed_at, superseded_at, etc.) rather than a second status flag
duplicating what the status column already says.
"""
from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, func,
)
from sqlalchemy.orm import relationship

from app.models.base import Base

REHIRE_REVIEW_STATUSES = ("PENDING_HM_APPROVAL", "AI_CLEARED", "APPROVED", "REJECTED")
AI_DECISIONS = ("CLEAR", "ESCALATE")

logger = logging.getLogger(__name__)

class InterviewRehireReview(Base):
    __tablename__ = "interview_rehire_reviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    round_name = Column(String(512), nullable=False)
    job_id = Column(String(512), ForeignKey("jobs.jobID"), nullable=True)

    requested_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    justification = Column(Text, nullable=False)

    # Panel IDs (app.models.user.InterviewPanel.id) whose feedback carried
    # a past "Reject" recommendation for this candidate -- the real
    # evidence this review exists to weigh, captured at request time so
    # the record is self-contained even if later feedback changes.
    past_no_hire_panel_ids = Column(JSON, nullable=True)

    status = Column(
        Enum(*REHIRE_REVIEW_STATUSES, name="rehire_review_status", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING_HM_APPROVAL",
    )

    ai_decision = Column(
        Enum(*AI_DECISIONS, name="rehire_review_ai_decision", native_enum=False, create_constraint=True),
        nullable=True,
    )
    ai_reasoning = Column(Text, nullable=True)
    ai_confidence = Column(Numeric(3, 2), nullable=True)

    decided_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    decision_note = Column(Text, nullable=True)

    # Set only once the gate actually clears (AI or HM) and the real
    # InterviewPanel row is created -- see module docstring.
    resulting_panel_id = Column(Integer, ForeignKey("interview_panels.id"), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="select")
    job = relationship("Jobs", foreign_keys=[job_id], lazy="select")
    requester = relationship("Users", foreign_keys=[requested_by], lazy="select")
    decider = relationship("Users", foreign_keys=[decided_by], lazy="select")
    resulting_panel = relationship("InterviewPanel", foreign_keys=[resulting_panel_id], lazy="select")
