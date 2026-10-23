"""Panel vs Flash: does Flash's match score agree with what the interview panel decided?

Flash scores a candidate for a job before the interview (CandidateJobScore.technical_score,
0-100). The panel then recommends Hire / Hold / Reject (InterviewFeedback.recommendation). For a
completed interview this compares the two:
  Flash says "advance" when its score >= FLASH_ADVANCE_SCORE, else "reject"
  the panel says "advance" on a Hire majority, "reject" on a Reject majority, else "undecided"
  agree = both advance or both reject (None when either side has no opinion)
The summary is the calibration report: agreement rate and the interviews where they disagreed,
so the matching can be tuned against real panel outcomes.
"""
from collections import Counter
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate_job_score import CandidateJobScore
from app.models.user import Interview, InterviewFeedback, InterviewPanel


def _panel_view(feedback: List[InterviewFeedback]) -> Dict:
    votes = Counter((f.recommendation or "").strip().lower() for f in feedback if f.recommendation)
    if not votes:
        return {"verdict": None, "votes": {}, "avg_technical_score": None}
    hire, reject = votes.get("hire", 0), votes.get("reject", 0)
    verdict = "advance" if hire > reject and hire >= votes.get("hold", 0) else \
        "reject" if reject > hire and reject >= votes.get("hold", 0) else "undecided"
    scores = [f.technical_score for f in feedback if f.technical_score is not None]
    return {"verdict": verdict, "votes": dict(votes),
            "avg_technical_score": round(sum(scores) / len(scores), 1) if scores else None}


def compare_interview(db: Session, interview: Interview, advance_score: int) -> Dict:
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first() if interview.panel_id else None
    job_id = panel.job_id if panel else None
    score = db.query(CandidateJobScore).filter(CandidateJobScore.candidate_id == interview.candidate_id,
                                               CandidateJobScore.job_id == job_id).first() if job_id else None
    flash_score = score.technical_score if score else None
    flash_verdict = None if flash_score is None else ("advance" if flash_score >= advance_score else "reject")
    panel_view = _panel_view(db.query(InterviewFeedback).filter(InterviewFeedback.interview_id == interview.id).all())
    decided = panel_view["verdict"] in ("advance", "reject")
    return {
        "interview_id": interview.id, "candidate_id": interview.candidate_id, "job_id": job_id,
        "round": panel.round_name if panel else None,
        "flash_score": flash_score, "flash_verdict": flash_verdict,
        "panel_verdict": panel_view["verdict"], "panel_votes": panel_view["votes"],
        "panel_avg_technical_score": panel_view["avg_technical_score"],
        "agree": (flash_verdict == panel_view["verdict"]) if flash_verdict and decided else None,
    }


def calibration_summary(db: Session, interviews: List[Interview], advance_score: int) -> Dict:
    rows = [compare_interview(db, i, advance_score) for i in interviews]
    compared = [r for r in rows if r["agree"] is not None]
    agreed = sum(1 for r in compared if r["agree"])
    return {
        "advance_score": advance_score,
        "interviews": len(rows), "compared": len(compared), "agreed": agreed,
        "agreement_pct": round(agreed / len(compared) * 100, 1) if compared else None,
        "flash_too_optimistic": sum(1 for r in compared if r["flash_verdict"] == "advance" and not r["agree"]),
        "flash_too_strict": sum(1 for r in compared if r["flash_verdict"] == "reject" and not r["agree"]),
        "disagreements": [r for r in compared if not r["agree"]],
    }
