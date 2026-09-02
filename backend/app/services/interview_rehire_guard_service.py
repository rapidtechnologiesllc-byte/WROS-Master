"""
Rehire guard -- Part 2 of the interview regrouping + rehire guard
priority Avinash flagged as "a must fix item as the first one after
epic-01 is complete" (2026-08-05). His own words: "if there was a
nohire in the past then when the next time someone is trying to
schedule interview to the candidate they need to provide a clear
justification an agentic bot should review and decide or take approval
import logging
from hiring manager before scheduling the interview."

Attaches to the LEGACY interview system
(app.models.user.InterviewPanel/Interview/InterviewFeedback) at the
same real "schedule a new round" entry point
app.services.interview_sequencing_service's R-05 gate already extends
-- app.api.v1.endpoints.interviews.create_interview_panel(). "Past
no-hire" = any InterviewFeedback.recommendation=="Reject" on ANY of
this candidate's past panels, across any job -- Avinash's own wording
("if there was a nohire in the past") is candidate-scoped, not
job-scoped, consistent with the panel-diversity rule he raised the
same session ("same candidate but different jobs/clients").

Fail-closed by construction: the panel row itself is never created
until this module's own status reaches AI_CLEARED or APPROVED. Any
LLM failure (timeout, bad JSON, missing key) routes to
PENDING_HM_APPROVAL, never CLEAR -- same posture as every other
compliance/security gate in this codebase (virus_scan_service's scan
gate, app.core.tenant_context's fail-closed tenant check).

LLM call shape mirrors response_parser_service._call_llm() -- a
direct, injectable Gemini call, not the candidate-context-shaped
prompt_framework_service (that module's placeholder catalogue is built
for candidate-facing Thunder replies; this is an internal recruiter
tool with no candidate context object to feed it).
"""
import json
import os
import re
from typing import Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.user import Interview, InterviewFeedback, InterviewPanel, Jobs
from app.models.interview_rehire_review import InterviewRehireReview

GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

FAIL_CLOSED_REASONING = (
    "AI review unavailable -- routed to hiring manager for manual approval (fail-closed)."
)

logger = logging.getLogger(__name__)

class RehireReviewNotFound(Exception):
    pass


class RehireReviewAlreadyDecided(Exception):
    pass


def get_past_no_hire_panels(db: Session, candidate_id: str) -> List[InterviewPanel]:
    """Every panel (any job, any round) this candidate has been through
    where at least one submitted InterviewFeedback recommended
    'Reject'. Empty list = no past no-hire on record."""
    panels = db.query(InterviewPanel).filter(InterviewPanel.candidate_id == candidate_id).all()
    if not panels:
        return []

    panel_ids = [p.id for p in panels]
    interviews = db.query(Interview).filter(Interview.panel_id.in_(panel_ids)).all()
    if not interviews:
        return []
    interview_ids = [i.id for i in interviews]

    reject_feedback = (
        db.query(InterviewFeedback)
        .filter(InterviewFeedback.interview_id.in_(interview_ids), InterviewFeedback.recommendation == "Reject")
        .all()
    )
    if not reject_feedback:
        return []

    rejected_interview_ids = {f.interview_id for f in reject_feedback}
    rejected_panel_ids = {i.panel_id for i in interviews if i.id in rejected_interview_ids}
    return [p for p in panels if p.id in rejected_panel_ids]


def candidate_has_past_no_hire(db: Session, candidate_id: str) -> bool:
    return bool(get_past_no_hire_panels(db, candidate_id))


def _past_no_hire_context(db: Session, panels: List[InterviewPanel]) -> str:
    lines = []
    for panel in panels:
        job_title = None
        if panel.job_id:
            job = db.query(Jobs).filter(Jobs.jobID == panel.job_id).first()
            job_title = job.jobTitle if job else None
        interviews = db.query(Interview).filter(Interview.panel_id == panel.id).all()
        for interview in interviews:
            feedbacks = (
                db.query(InterviewFeedback)
                .filter(InterviewFeedback.interview_id == interview.id, InterviewFeedback.recommendation == "Reject")
                .all()
            )
            for f in feedbacks:
                comment = (f.comments or "").strip()
                lines.append(
                    f"- Round '{panel.round_name}'"
                    + (f" for job '{job_title}'" if job_title else "")
                    + (f": {comment}" if comment else " (no comments recorded)")
                )
    return "\n".join(lines) if lines else "- (no detail available)"


def _default_llm_call(prompt: str, api_key: str) -> str:
    import requests
    resp = requests.post(
        f"{GEMINI_MODEL_URL}?key={api_key}",
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300}},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return re.sub(r"```(?:json)?", "", text).strip()


def _call_llm(prompt: str, llm_call: Optional[Callable[[str], str]]) -> str:
    if llm_call is not None:
        return llm_call(prompt)
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return _default_llm_call(prompt, api_key)


def review_rehire_justification(
    candidate_name: str,
    past_no_hire_context: str,
    justification: str,
    *,
    llm_call: Optional[Callable[[str], str]] = None,
) -> Dict:
    """Never raises. Always returns {"decision": "CLEAR"|"ESCALATE",
    "reasoning": str, "confidence": float}. Any failure (LLM error,
    malformed JSON, missing keys, out-of-range decision) is caught and
    converted to a fail-closed ESCALATE -- this function is the one
    place that posture is enforced, callers never need to re-check it.
    """
    prompt = (
        "You are reviewing a BlitzenX recruiter's request to re-interview a candidate "
        "who was previously given a NO-HIRE (Reject) outcome. Decide whether the "
        "justification given is specific and strong enough to proceed WITHOUT a human "
        "hiring manager's sign-off, or whether it should be escalated for manual "
        "approval. Only CLEAR a justification that gives a concrete, verifiable reason "
        "the past rejection no longer applies (e.g. the candidate has since gained a "
        "specific missing skill or certification, the prior rejection was for a "
        "clearly different role/specialization that does not apply here, or a named "
        "process issue with the original round). Default to ESCALATE for anything "
        "generic, vague, emotional, or unverifiable ('deserves another chance', "
        "'desperate need', 'seemed fine to me'). When uncertain, ESCALATE.\n\n"
        f"Candidate: {candidate_name}\n"
        f"Past no-hire round(s):\n{past_no_hire_context}\n\n"
        f"Recruiter's justification for re-interviewing: {justification}\n\n"
        'Return ONLY valid JSON: {"decision": "CLEAR" or "ESCALATE", '
        '"reasoning": "one or two sentence explanation", "confidence": 0.0-1.0}'
    )

    try:
        raw = _call_llm(prompt, llm_call)
        parsed = json.loads(raw)
        decision = parsed.get("decision")
        if decision not in ("CLEAR", "ESCALATE"):
            raise ValueError(f"Unexpected decision value: {decision!r}")
        confidence = float(parsed.get("confidence", 0.0))
        return {
            "decision": decision,
            "reasoning": str(parsed.get("reasoning", "")).strip() or "(no reasoning provided)",
            "confidence": max(0.0, min(1.0, confidence)),
        }
    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[RehireGuard] AI review failed, failing closed to ESCALATE: {exc}")
        return {"decision": "ESCALATE", "reasoning": FAIL_CLOSED_REASONING, "confidence": 0.0}


def submit_rehire_request(
    db: Session,
    candidate_id: str,
    candidate_name: str,
    round_name: str,
    job_id: Optional[str],
    requested_by: Optional[str],
    justification: str,
    *,
    llm_call: Optional[Callable[[str], str]] = None,
) -> InterviewRehireReview:
    """Creates the review row and runs the AI pass. Never creates the
    InterviewPanel itself -- that only happens once status reaches
    AI_CLEARED (caller creates it) or a hiring manager APPROVEs via
    decide_rehire_review()."""
    past_panels = get_past_no_hire_panels(db, candidate_id)
    context = _past_no_hire_context(db, past_panels)

    review = InterviewRehireReview(
        candidate_id=candidate_id,
        round_name=round_name,
        job_id=job_id,
        requested_by=requested_by,
        justification=justification,
        past_no_hire_panel_ids=[p.id for p in past_panels],
        status="PENDING_HM_APPROVAL",
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    result = review_rehire_justification(candidate_name, context, justification, llm_call=llm_call)
    review.ai_decision = result["decision"]
    review.ai_reasoning = result["reasoning"]
    review.ai_confidence = result["confidence"]
    if result["decision"] == "CLEAR":
        review.status = "AI_CLEARED"
    db.commit()
    db.refresh(review)
    return review


def decide_rehire_review(
    db: Session,
    review_id: int,
    decision: str,
    decided_by: str,
    note: Optional[str] = None,
) -> InterviewRehireReview:
    """Hiring-manager decision on a PENDING_HM_APPROVAL review. Approve
    creates the real InterviewPanel now (R-05 sequencing was already
    checked at request time; re-checking here would need to re-run the
    whole gate for a case this codebase treats as out of scope for a
    first cut -- flagged, not silently ignored). Reject leaves no panel
    ever created."""
    if decision not in ("approve", "reject"):
        raise ValueError(f"decision must be 'approve' or 'reject', got {decision!r}")

    review = db.query(InterviewRehireReview).filter(InterviewRehireReview.id == review_id).first()
    if review is None:
        raise RehireReviewNotFound(f"Rehire review {review_id} not found")
    if review.status != "PENDING_HM_APPROVAL":
        raise RehireReviewAlreadyDecided(
            f"Rehire review {review_id} is already '{review.status}' -- cannot decide again"
        )

    review.decided_by = decided_by
    review.decision_note = note
    from datetime import datetime
    review.decided_at = datetime.utcnow()

    if decision == "approve":
        panel = InterviewPanel(
            candidate_id=review.candidate_id,
            round_name=review.round_name,
            job_id=review.job_id,
        )
        db.add(panel)
        db.flush()
        review.status = "APPROVED"
        review.resulting_panel_id = panel.id
    else:
        review.status = "REJECTED"

    db.commit()
    db.refresh(review)
    return review


def get_pending_rehire_reviews(db: Session) -> List[InterviewRehireReview]:
    return (
        db.query(InterviewRehireReview)
        .filter(InterviewRehireReview.status == "PENDING_HM_APPROVAL")
        .order_by(InterviewRehireReview.created_at.asc())
        .all()
    )
