"""
import logging
S-040/HRMS-0440 -- Overall Candidate Score & Ranking.

Real architecture adaptations:
- candidate_job_scores.overall_score/score_breakdown already exist
  (S-037), left NULL/unpopulated on purpose -- every one of S-037/
  S-038/S-039's own docstrings literally names "HRMS-0440 and friends"
  as the story that owns them. No new table/migration needed.
- Real spec-vs-xlsx discrepancy found and flagged, not silently
  resolved: the xlsx summary column names the 4th input as
  "communication," but the docx body, Step 1's formula, the UI
  tooltip, the integrations table, the data-mapping table, and TC-001's
  own worked example (32+30+18+7=87) all consistently use
  candidate.resume_completeness_score instead -- built to the
  self-consistent docx formula (and its own "Depends On: HRMS-0430"
  line), not the one-word xlsx summary artifact. No missing 4th input
  to fake here: resume_completeness_score already exists and is
  already live (S-030).
- candidates.id/candidates.name (the spec's literal join columns) do
  not exist -- real PK is candidateID (String), real name is built
  from candidateFirstName/candidateLastName (no single name column).
- BR-03 (rank is never stored) -- get_ranked_candidates() assigns rank
  in Python after ordering, never persisted as a column.
- Step 4's "after any component UPDATE, recalculate overall_score" has
  no event bus to hook into (same as every other story this round).
  Rather than having each of the three component services import this
  one (which would create a real circular-import risk --
  technical_scoring_service/compensation_scoring_service/
  availability_scoring_service are all imported BY this module), the
  recalc trigger is wired at the two real producer call sites that
  already call all three services' recalculate_for_candidate():
  skill_extraction_service.extract_and_tag_skills() (technical) and
  facts_extraction_service.extract_facts() (compensation/availability,
  conditional). calculate_overall_score() itself always reads the
  CURRENT (freshly-committed) component values from candidate_job_scores,
  so calling it any time after a component update reflects that update
  correctly -- satisfying TC-003 without needing the three component
  services to know this one exists.
- score_breakdown is the column SHARED with all three component
  services -- this service flat-MERGES its own keys
  (resume_completeness_score/weights) rather than overwriting the
  whole column, same fix already applied to the other three.
"""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_job_score import CandidateJobScore
from app.services.availability_scoring_service import calculate_availability_score
from app.services.compensation_scoring_service import calculate_compensation_score
from app.services.technical_scoring_service import CandidateNotFound, JobNotFound, calculate_technical_score, linked_job_ids

# BR-01: BA-approved product decision, code constant -- any change
# requires Lead BA written approval + code review, not a config value.
WEIGHTS = {"technical": 0.40, "compensation": 0.30, "availability": 0.20, "resume_completeness": 0.10}


def _candidate_display_name(candidate: Candidate) -> str:
    parts = [candidate.candidateFirstName, candidate.candidateLastName]
    name = " ".join(p for p in parts if p).strip()
    return name or candidate.candidateEmail


def calculate_overall_score(db: Session, candidate_id: str, job_id: str, tenant_id: str) -> Dict:
    """Step 1. If any component is missing, calculates it first (each
    component function already upserts and returns the fresh record).
    Flat-merges into score_breakdown -- see module docstring."""
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        raise CandidateNotFound(f"Candidate {candidate_id!r} not found.")

    existing = (
        db.query(CandidateJobScore)
        .filter(CandidateJobScore.tenant_id == tenant_id, CandidateJobScore.candidate_id == candidate_id, CandidateJobScore.job_id == job_id)
        .first()
    )

    if existing is None or existing.technical_score is None:
        calculate_technical_score(db, candidate_id, job_id, tenant_id)
    if existing is None or existing.compensation_score is None:
        calculate_compensation_score(db, candidate_id, job_id, tenant_id)
    if existing is None or existing.availability_score is None:
        calculate_availability_score(db, candidate_id, job_id, tenant_id)

    record = (
        db.query(CandidateJobScore)
        .filter(CandidateJobScore.tenant_id == tenant_id, CandidateJobScore.candidate_id == candidate_id, CandidateJobScore.job_id == job_id)
        .first()
    )
    if record is None:
        raise JobNotFound(f"Job {job_id!r} not found.")  # one of the 3 calls above would have raised first if candidate/job invalid

    resume_score = candidate.resume_completeness_score or 0

    overall = round(
        record.technical_score * WEIGHTS["technical"] + record.compensation_score * WEIGHTS["compensation"]
        + record.availability_score * WEIGHTS["availability"] + resume_score * WEIGHTS["resume_completeness"]
    )

    breakdown = {"resume_completeness_score": resume_score, "weights": WEIGHTS}
    record.overall_score = overall
    record.score_breakdown = {**(record.score_breakdown or {}), **breakdown}  # merge, not overwrite -- see module docstring
    record.calculated_at = datetime.utcnow()
    db.add(record)
    db.flush()

    return {
        "candidate_id": candidate_id, "job_id": job_id,
        "technical_score": record.technical_score, "compensation_score": record.compensation_score,
        "availability_score": record.availability_score, "overall_score": record.overall_score,
        "score_breakdown": record.score_breakdown, "calculated_at": record.calculated_at,
    }


def recalculate_for_candidate(db: Session, candidate: Candidate, tenant_id: str) -> List[Dict]:
    """Recalculates overall_score for every job this candidate is
    actually linked to. Never raises -- same defensive posture as the
    three component services."""
    results = []
    for job_id in linked_job_ids(db, candidate):
        try:
            results.append(calculate_overall_score(db, candidate.candidateID, job_id, tenant_id))
        except Exception as exc:
           logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[OverallScoring] Failed to recalculate overall score for candidate {candidate.candidateID!r} / job {job_id!r}: {exc}")
    db.commit()
    return results


def get_ranked_candidates(db: Session, job_id: str, tenant_id: str) -> List[Dict]:
    """Step 2. BR-03: rank is computed here, in Python, after ordering
    -- never persisted as a column."""
    rows = (
        db.query(CandidateJobScore, Candidate)
        .join(Candidate, CandidateJobScore.candidate_id == Candidate.candidateID)
        .filter(CandidateJobScore.tenant_id == tenant_id, CandidateJobScore.job_id == job_id)
        .order_by(CandidateJobScore.overall_score.desc().nullslast())
        .all()
    )

    ranked = []
    for index, (score_row, candidate) in enumerate(rows, start=1):
        ranked.append({
            "rank": index,
            "candidate_id": candidate.candidateID,
            "candidate_name": _candidate_display_name(candidate),
            "overall_score": score_row.overall_score,
            "technical_score": score_row.technical_score,
            "compensation_score": score_row.compensation_score,
            "availability_score": score_row.availability_score,
            "resume_completeness_score": candidate.resume_completeness_score,
            "score_breakdown": score_row.score_breakdown,
        })
    return ranked
