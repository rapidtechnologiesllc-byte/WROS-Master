"""
R-05 ("L1 must pass before L2 can be scheduled") applied to the legacy
interview-panel system (`app.models.user.InterviewPanel`/`Interview`/
`InterviewFeedback` -- the original "Schedule Interview" feature). This
is distinct from the newer, leveled `app.models.interview_pipeline.
SubmissionInterview` system, which already enforces R-05 for real in
`app.services.interview_service.create_interview()` -- this module does
not duplicate that, it closes the gap in the OTHER, older system the
Phase 3 doc names specifically ("the existing Onboarding Module code
has zero enforcement of it today").

This legacy system has no L1/L2 concept in its schema at all --
`round_name` is free text ("HR", "Technical", "Managerial", or anything
a caller sends), one `InterviewPanel` per candidate+round, with no
ordering field. Per the Development & Review Standard's own
verification wording ("create an L2 (or any round 2+) panel with zero
prior rounds logged -- must be rejected"), R-05 generalizes here to an
ORDINAL rule: a candidate's next panel cannot be created until their
most recently created prior panel has actually passed.

"Passed" is not an existing concept in this legacy system either --
`Interview.status` only tracks Scheduled/Completed/Cancelled, and
`InterviewFeedback.recommendation` (Hire/Hold/Reject) is per-interviewer,
never aggregated into a round-level decision anywhere in this codebase
(confirmed by reading `_check_and_auto_submit_for_hire()`, the one
existing piece of related automation -- it counts completed interviews,
it never looks at recommendation at all).

This module makes that judgment call explicitly rather than inventing
it silently: a round has passed once at least one of its Interview
sessions is Completed AND at least one submitted InterviewFeedback for
that round recommends "Hire" AND none recommend "Reject" -- fail-closed
on any negative signal, same posture as R-01 and the virus-scan gate.
**This specific aggregation rule is this session's judgment call, not a
confirmed product decision** -- flagged for whoever owns the interview
process to confirm or override, same posture as the MFA role-mapping
and Client v2 contact-role-vocabulary calls made earlier this session.
"""
from sqlalchemy.orm import Session

from app.models.user import Interview, InterviewFeedback, InterviewPanel


class PriorRoundNotPassed(Exception):
    """R-05: the candidate's most recent prior interview round has not
    been recorded as passed -- a new round cannot be scheduled yet."""


def _round_has_passed(db: Session, panel: InterviewPanel) -> bool:
    interviews = db.query(Interview).filter(Interview.panel_id == panel.id).all()
    interview_ids = [interview.id for interview in interviews]
    if not any(interview.status == "Completed" for interview in interviews):
        return False

    feedback = (
        db.query(InterviewFeedback)
        .filter(InterviewFeedback.interview_id.in_(interview_ids))
        .all()
    )
    recommendations = {item.recommendation for item in feedback}
    if "Reject" in recommendations:
        return False
    return "Hire" in recommendations


def enforce_interview_sequencing_gate(db: Session, candidate_id: str) -> None:
    """
    R-05 at panel-creation time. The candidate's first panel is always
    allowed -- there is nothing to sequence against yet. Every
    subsequent panel requires the most recently created existing panel
    to have passed, per _round_has_passed() above. Raises
    PriorRoundNotPassed otherwise; callers must not catch this and
    proceed.
    """
    most_recent = (
        db.query(InterviewPanel)
        .filter(InterviewPanel.candidate_id == candidate_id)
        .order_by(InterviewPanel.created_at.desc(), InterviewPanel.id.desc())
        .first()
    )
    if most_recent is None:
        return  # first round -- nothing to sequence against

    if not _round_has_passed(db, most_recent):
        raise PriorRoundNotPassed(
            f"Candidate {candidate_id}'s prior interview round "
            f"'{most_recent.round_name}' (panel {most_recent.id}) has not "
            f"been recorded as passed -- a new round cannot be scheduled "
            f"until it is."
        )
