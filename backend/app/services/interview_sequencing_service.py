"""
R-05 ("L1 must pass before L2 can be scheduled") applied to the legacy
interview-panel system (`app.models.user.InterviewPanel`/`Interview`/
`InterviewFeedback` -- the original "Schedule Interview" feature). This
is distinct from the newer, leveled `app.models.interview_pipeline.
SubmissionInterview` system, which already enforces R-05 for real in
`app.services.interview_service.create_interview()` -- this module does
not duplicate that, it closes the gap in the OTHER, older system the
Phase 3 doc names specifically ("the existing Onboarding Module code
import logging
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
from typing import List

from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateStatus
from app.models.user import (
    CandidateAssignment,
    Interview,
    InterviewFeedback,
    InterviewPanel,
    Jobs,
    Users,
)

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# S-102/HRMS-P207 -- Hiring Manager Candidate Review. app.schemas.interview's
# HMFeedbackDetail/HMInterviewRound/HMCandidateReviewItem/HMCandidateReview
# ListResponse were already fully defined but imported into interviews.py
# and wired to no route -- this is the real, missing aggregation behind
# them, using the exact same round-level Hire/Reject vocabulary
# _round_has_passed() above already established for this legacy interview
# system, not a second competing definition.
#
# "Must Hire" is a valid value in the schema's own comment but no doc read
# this session defines what earns it (a score threshold would be guessed,
# not grounded) -- this function never emits it, only Hire/Mixed/No
# Feedback. The BR "HM must view all feedback before approving" is NOT
# enforced here or at the existing PUT /status/{candidate_id} approval
# endpoint (out of scope for this gap-fill -- that's a pre-existing,
# separately-owned, tested endpoint); flagged, not silently added.
# ---------------------------------------------------------------------------

def _round_overall_recommendation(feedbacks: List[InterviewFeedback]) -> str:
    if not feedbacks:
        return "No Feedback"
    recommendations = {f.recommendation for f in feedbacks}
    if recommendations == {"Hire"}:
        return "Hire"
    return "Mixed"


def get_hm_candidate_review_list(db: Session, hiring_manager: Users) -> dict:
    """Every candidate assigned to this hiring manager (CandidateAssignment.
    hiring_manager_id), with their full interview-round + feedback history.
    Returns a plain dict shaped exactly like HMCandidateReviewListResponse
    -- the API layer wraps it, this stays framework-agnostic."""
    assignments = (
        db.query(CandidateAssignment)
        .filter(CandidateAssignment.hiring_manager_id == hiring_manager.UserID)
        .all()
    )

    candidates = []
    for assignment in assignments:
        candidate = db.query(Candidate).filter(Candidate.candidateID == assignment.candidate_id).first()
        if candidate is None:
            continue

        status = (
            db.query(CandidateStatus)
            .filter(CandidateStatus.candidateID == candidate.candidateID)
            .order_by(CandidateStatus.updatedAt.desc())
            .first()
        )

        panels = (
            db.query(InterviewPanel)
            .filter(InterviewPanel.candidate_id == candidate.candidateID)
            .order_by(InterviewPanel.created_at.asc())
            .all()
        )

        job_title = None
        job_id = None
        completed_count = 0
        rounds = []
        for panel in panels:
            if panel.job_id and job_id is None:
                job_id = panel.job_id
                job = db.query(Jobs).filter(Jobs.jobID == panel.job_id).first()
                job_title = job.jobTitle if job else None

            interviews = db.query(Interview).filter(Interview.panel_id == panel.id).all()
            for interview in interviews:
                if interview.status == "Completed":
                    completed_count += 1

                feedback_rows = (
                    db.query(InterviewFeedback)
                    .filter(InterviewFeedback.interview_id == interview.id)
                    .all()
                )
                feedback_details = []
                for f in feedback_rows:
                    interviewer = db.query(Users).filter(Users.UserID == f.interviewer_id).first()
                    scores = [f.technical_score, f.communication_score, f.problem_solving_score, f.culture_fit_score]
                    valid_scores = [s for s in scores if s is not None]
                    feedback_details.append({
                        "feedback_id": f.id, "interviewer_id": f.interviewer_id,
                        "interviewer_name": interviewer.UserName if interviewer else "(unknown)",
                        "technical_score": f.technical_score, "communication_score": f.communication_score,
                        "problem_solving_score": f.problem_solving_score, "culture_fit_score": f.culture_fit_score,
                        "average_score": round(sum(valid_scores) / len(valid_scores), 2) if valid_scores else 0.0,
                        "comments": f.comments, "recommendation": f.recommendation, "submitted_at": f.submitted_at,
                    })

                rounds.append({
                    "interview_id": interview.id, "round_name": panel.round_name,
                    "start_time": interview.start_time, "end_time": interview.end_time,
                    "status": interview.status, "panel_id": panel.id,
                    "feedbacks": feedback_details,
                    "overall_recommendation": _round_overall_recommendation(feedback_rows),
                })

        candidates.append({
            "candidate_id": candidate.candidateID,
            "candidate_name": f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip(),
            "candidate_email": candidate.candidateEmail,
            "candidate_mobile": candidate.candidateMobile,
            "candidate_experience": candidate.candidateExperience,
            "job_id": job_id, "job_title": job_title,
            "pipeline_status": status.piplineStatus if status else "Applied",
            "completed_interview_count": completed_count,
            "approval_endpoint": f"/status/{candidate.candidateID}",
            "interviews": rounds,
        })

    return {
        "hiring_manager_id": hiring_manager.UserID,
        "hiring_manager_name": hiring_manager.UserName or hiring_manager.UserID,
        "total_candidates": len(candidates),
        "candidates": candidates,
    }
