"""Interview round outcomes. Every gate after an interview (next round, offer, rehire guard)
reads a verdict from here instead of guessing from free-text round names and feedback.

Recommendations interviewers give (one vocabulary everywhere):
    No Hire, Not sure, Average, Hire, Must Hire
A round's verdict, computed once its interview is Completed:
    any "No Hire"                -> FAIL
    every recommendation Hire / Must Hire -> PASS
    anything else (mixed, unsure) -> NEEDS_DECISION: the hiring manager decides
A person can always set the verdict (MANUAL); changing an existing PASS/FAIL needs a reason.
Rows are created lazily, so panels from before this existed get verdicts on first read.
"""
import logging
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.interview_verdict import InterviewRoundVerdict
from app.models.user import Interview, InterviewFeedback, InterviewPanel

logger = logging.getLogger(__name__)

RECOMMENDATIONS = ["No Hire", "Not sure", "Average", "Hire", "Must Hire"]
NO_HIRE = {"No Hire", "Reject"}  # "Reject" is the pre-2026 vocabulary still in old rows
HIRE = {"Hire", "Must Hire"}
LEVELS = ("SCREEN", "L1", "L2", "OTHER")
VERDICTS = ("PENDING", "PASS", "FAIL", "NEEDS_DECISION")


class VerdictError(ValueError):
    pass


def infer_level(round_name: Optional[str]) -> str:
    name = re.sub(r"[\s_-]+", " ", (round_name or "").strip().lower())
    if re.match(r"^(hr|screen|recruiter)", name):
        return "SCREEN"
    if re.match(r"^(l ?1|level ?1|tech)", name):
        return "L1"
    if re.match(r"^(l ?2|level ?2|manag|hm\b|hiring manager)", name):
        return "L2"
    return "OTHER"


def ensure_verdict_row(db: Session, panel: InterviewPanel, level: Optional[str] = None) -> InterviewRoundVerdict:
    row = db.query(InterviewRoundVerdict).filter(InterviewRoundVerdict.panel_id == panel.id).first()
    if row is None:
        row = InterviewRoundVerdict(panel_id=panel.id, candidate_id=panel.candidate_id, job_id=panel.job_id,
                                    level=level or infer_level(panel.round_name), verdict="PENDING", source="AUTO")
        db.add(row)
        db.flush()
    elif level and row.level != level:
        row.level = level
    return row


def _recommendations(db: Session, panel_id: int):
    interviews = db.query(Interview).filter(Interview.panel_id == panel_id).all()
    if not any(i.status == "Completed" for i in interviews):
        return None  # round not finished yet
    ids = [i.id for i in interviews]
    return [f.recommendation for f in db.query(InterviewFeedback).filter(InterviewFeedback.interview_id.in_(ids)).all()]


def compute_verdict(db: Session, panel: InterviewPanel) -> InterviewRoundVerdict:
    """Recompute an AUTO verdict from feedback. A MANUAL decision is never overwritten."""
    row = ensure_verdict_row(db, panel)
    if row.source == "MANUAL":
        return row
    recs = _recommendations(db, panel.id)
    if recs is None:
        verdict = "PENDING"
    elif any(r in NO_HIRE for r in recs):
        verdict = "FAIL"
    elif recs and all(r in HIRE for r in recs):
        verdict = "PASS"
    else:
        verdict = "NEEDS_DECISION"
    if verdict != row.verdict:
        logger.info(f"[Verdict] panel {panel.id} ({row.level}) {row.verdict} -> {verdict}")
        row.verdict = verdict
        row.decided_at = datetime.utcnow() if verdict != "PENDING" else None
    return row


def verdict_for_panel(db: Session, panel: InterviewPanel) -> InterviewRoundVerdict:
    return compute_verdict(db, panel)


def record_manual_verdict(db: Session, panel: InterviewPanel, verdict: str, user_id: str,
                          rationale: Optional[str] = None) -> InterviewRoundVerdict:
    if verdict not in ("PASS", "FAIL"):
        raise VerdictError("Verdict must be PASS or FAIL.")
    row = compute_verdict(db, panel)
    if row.verdict in ("PASS", "FAIL") and row.verdict != verdict and not (rationale or "").strip():
        raise VerdictError(f"This round is already {row.verdict}; a reason is required to change it.")
    row.verdict, row.source = verdict, "MANUAL"
    row.decided_by_user_id, row.decided_at, row.rationale = user_id, datetime.utcnow(), rationale
    return row


def set_level(db: Session, panel: InterviewPanel, level: str) -> InterviewRoundVerdict:
    if level not in LEVELS:
        raise VerdictError(f"Level must be one of {', '.join(LEVELS)}.")
    return ensure_verdict_row(db, panel, level)


def candidate_verdicts(db: Session, candidate_id: str, job_id: Optional[str] = None):
    query = db.query(InterviewPanel).filter(InterviewPanel.candidate_id == candidate_id)
    if job_id:
        query = query.filter(InterviewPanel.job_id == job_id)
    panels = query.order_by(InterviewPanel.created_at, InterviewPanel.id).all()
    return [(panel, verdict_for_panel(db, panel)) for panel in panels]


def level_status(db: Session, candidate_id: str, level: str, job_id: Optional[str] = None) -> Optional[str]:
    """Verdict of the latest round at this level (None when there is no such round)."""
    rows = [v for _, v in candidate_verdicts(db, candidate_id, job_id) if v.level == level]
    return rows[-1].verdict if rows else None


def level_passed(db: Session, candidate_id: str, level: str, job_id: Optional[str] = None) -> bool:
    return level_status(db, candidate_id, level, job_id) == "PASS"


def has_failed_round(db: Session, candidate_id: str):
    """Panels (any job) whose verdict is FAIL -- the rehire guard's evidence."""
    return [panel for panel, v in candidate_verdicts(db, candidate_id) if v.verdict == "FAIL"]
