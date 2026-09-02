"""
HRMS-0706 -- Interview Panel Assignment, Phase 2 Domain 2 (the interview
import logging
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
calendar. HRMS-0449 (Interview Confirmation) is also now built
(app.services.interview_confirmation_service.confirm_interview()) and
populates `scheduled_via_graph_event_id` for real with the actual
Graph event ID once the interviewer's calendar invite is created;
`confirmed_at` (added by that story) is the real "status=CONFIRMED"
signal. Null on `scheduled_via_graph_event_id` still means "scheduled,
no Graph invite created (yet, or the invite creation itself failed --
see that story's own CALENDAR_INVITE_FAILED handling)", never a
generic "scheduling failed".

S-051/HRMS-0451 (Interview Reschedule Workflow) added
`reschedule_count`/`rescheduled_from_interview_id`/`superseded_at`.
BR-03 there requires a NEW row per reschedule (never UPDATE the old
time in place) -- this genuinely conflicted with this table's
original `uq_one_interview_per_level_per_submission` UniqueConstraint
(one row per submission+level, full stop), which a second row for the
same submission+level would violate. Resolved by replacing that
UniqueConstraint with a partial/filtered unique index
(`ix_one_current_interview_per_level`, `WHERE superseded_at IS NULL`)
that only enforces "one CURRENT interview per submission+level" --
historical (superseded) rows are exempt. `superseded_at` (a
timestamp-presence signal, same convention as `confirmed_at`/
`scheduled_at`) is the real "status=RESCHEDULED" this story's own
spec calls for -- there is still no separate literal status enum
column on this row.
"""
import uuid

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, func, text,
)

from app.models.base import Base


def _new_uuid() -> str:
    return str(uuid.uuid4())


INTERVIEW_LEVELS = ("L1", "L2")
INTERVIEW_OUTCOMES = ("PENDING", "PASS", "FAIL")

logger = logging.getLogger(__name__)

class DemandInterviewPanel(Base):
    """HRMS-0706 -- the pool of employees eligible to interview for a
    given demand + level. getAssignedInterviewer() picks from here."""
    __tablename__ = "demand_interview_panels"

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    demand_id = Column(String(512), ForeignKey("demands.id"), nullable=False, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id"), nullable=False, index=True)
    interview_level = Column(
        Enum(*INTERVIEW_LEVELS, name="panel_interview_level", native_enum=False, create_constraint=True),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    assigned_at = Column(DateTime, server_default=func.now())
    assigned_by = Column(String(512), ForeignKey("users.UserID"), nullable=True)

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

    id = Column(String(512), primary_key=True, default=_new_uuid)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    submission_id = Column(String(512), ForeignKey("submissions.id"), nullable=False, index=True)
    candidate_id = Column(String(512), ForeignKey("candidates.candidateID"), nullable=False, index=True)
    level = Column(
        Enum(*INTERVIEW_LEVELS, name="submission_interview_level", native_enum=False, create_constraint=True),
        nullable=False,
    )
    panel_id = Column(String(512), ForeignKey("demand_interview_panels.id"), nullable=True)

    scheduled_at = Column(DateTime, nullable=True)
    outcome = Column(
        Enum(*INTERVIEW_OUTCOMES, name="submission_interview_outcome", native_enum=False, create_constraint=True),
        nullable=False, default="PENDING",
    )
    outcome_set_at = Column(DateTime, nullable=True)
    # S-049/HRMS-0449 -- populated for real once
    # interview_confirmation_service.confirm_interview() successfully
    # creates the interviewer's Outlook invite. This is the exact
    # column HRMS-0448's own docstring already reserved for this.
    scheduled_via_graph_event_id = Column(String(512), nullable=True)
    # S-049/HRMS-0449 -- presence means "status=CONFIRMED" (spec's own
    # literal status value). No separate status enum column exists on
    # this row (scheduled_at's presence already means "scheduled" the
    # same way) -- a second timestamp-presence signal, not a new enum.
    confirmed_at = Column(DateTime, nullable=True)
    # S-051/HRMS-0451 -- BR-01's cap (max 2 autonomous reschedules, then
    # escalate). Tracked on every row in a reschedule chain, not just
    # the current one, so the full chain's count is always readable
    # from any single row without a recursive walk.
    reschedule_count = Column(Integer, nullable=False, server_default="0")
    # S-051/HRMS-0451 -- BR-03: links a rescheduled interview back to
    # the one it superseded. Null for an interview that has never been
    # rescheduled.
    rescheduled_from_interview_id = Column(String(512), ForeignKey("submission_interviews.id"), nullable=True)
    # S-051/HRMS-0451 -- presence means "status=RESCHEDULED" (spec's
    # own literal value) -- same timestamp-presence convention as
    # confirmed_at/scheduled_at, not a new status enum column.
    superseded_at = Column(DateTime, nullable=True)
    # S-052/HRMS-0452 -- the real no-show state machine, all
    # timestamp-presence signals (same convention as confirmed_at/
    # superseded_at, no separate status enum): CONFIRMED (all 4 null)
    # -> NO_SHOW_CHECK_IN_SENT (no_show_check_in_at set) ->
    # NO_SHOW (no_show_confirmed_at set) -> reschedule offer sent
    # (no_show_reschedule_offer_sent_at set) -> NO_SHOW_NO_RESPONSE
    # (no_show_no_response_at set) if the offer itself goes unanswered.
    no_show_check_in_at = Column(DateTime, nullable=True)
    no_show_confirmed_at = Column(DateTime, nullable=True)
    no_show_reschedule_offer_sent_at = Column(DateTime, nullable=True)
    no_show_no_response_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # S-051/HRMS-0451 -- replaces the original full UniqueConstraint
        # (see module docstring): only CURRENT (non-superseded)
        # interviews are constrained to one per submission+level;
        # historical, superseded rows are exempt.
        Index(
            "ix_one_current_interview_per_level", "submission_id", "level", unique=True,
            sqlite_where=text("superseded_at IS NULL"), mssql_where=text("superseded_at IS NULL"),
        ),
    )
