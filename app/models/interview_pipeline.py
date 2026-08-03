"""
HRMS-0706 -- Interview Panel Assignment, Phase 2 Domain 2 (the interview
half of the piece connecting Demand -> Candidate -> Employee).

New tables, deliberately NOT named `interview_panels` / `interviews` --
this codebase already has legacy tables with those exact names
(app.models.user.InterviewPanel / Interview), built for the pre-existing
Jobs/Candidate interview flow and keyed completely differently (Integer
PKs, a panel tied to one candidate+job+round rather than a demand+level
interviewer pool). Same "genuinely new, not retrofitted" precedent as
Demand vs. Jobs -- reconciling the two interview systems is a separate
decision, flagged here, not resolved by silently picking one.

SubmissionInterview is this codebase's version of 02-DATA-MODEL.md's
`interviews (id, submission_id, level, outcome, panel_id,
scheduled_via_graph_event_id)` sketch.

HRMS-0448 (Calendar Matching Engine) is now built
(app.services.calendar_matching_service.attempt_calendar_match()) and
populates `scheduled_at` for real by matching a candidate's
availability slots against the assigned interviewer's real Outlook
calendar. `scheduled_via_graph_event_id` still stays null even after a
real HRMS-0448 match -- that story deliberately does not create the
actual Graph calendar invite (see its own module docstring); the
literal invite/join-link creation is left to a future HRMS-0449
(Interview Confirmation), not yet built. Null continues to mean
"scheduled, no Graph invite created yet", not "scheduling failed".
"""
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


INTERVIEW_LEVELS = ("L1", "L2")
INTERVIEW_OUTCOMES = ("PENDING", "PASS", "FAIL")


class DemandInterviewPanel(Base):
    """HRMS-0706 -- the pool of employees eligible to interview for a
    given demand + level. getAssignedInterviewer() picks from here."""
    __tablename__ = "demand_interview_panels"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    demand_id = Column(String(36), ForeignKey("demands.id"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    interview_level = Column(
        Enum(*INTERVIEW_LEVELS, name="panel_interview_level", native_enum=False, create_constraint=True),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    assigned_at = Column(DateTime, server_default=func.now())
    assigned_by = Column(String(50), ForeignKey("users.UserID"), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "demand_id", "interview_level", "employee_id",
            name="uq_panel_member_per_demand_level",
        ),
    )


class SubmissionInterview(Base):
    """The interview event itself, tied to a submission (not just a
    demand) -- see module docstring for why this isn't named `interviews`.

    R-05 (L1 must pass before L2) is enforced in
    app.services.interview_service.create_interview(), not here -- the
    row itself doesn't know about its sibling rows.
    """
    __tablename__ = "submission_interviews"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    submission_id = Column(String(36), ForeignKey("submissions.id"), nullable=False, index=True)
    candidate_id = Column(String(50), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    level = Column(
        Enum(*INTERVIEW_LEVELS, name="submission_interview_level", native_enum=False, create_constraint=True),
        nullable=False,
    )
    panel_id = Column(String(36), ForeignKey("demand_interview_panels.id"), nullable=True)

    scheduled_at = Column(DateTime, nullable=True)
    outcome = Column(
        Enum(*INTERVIEW_OUTCOMES, name="submission_interview_outcome", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING",
    )
    outcome_set_at = Column(DateTime, nullable=True)
    scheduled_via_graph_event_id = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "submission_id", "level",
            name="uq_one_interview_per_level_per_submission",
        ),
    )
