"""
S-039/HRMS-0439 -- Availability Score.

Real architecture adaptations:
- candidate_job_scores.availability_score already exists (S-037), left
  NULL/unpopulated on purpose for "the later stories that own those" --
  this story is that later story. No new score table needed.
- candidates.notice_period_days does not exist -- same situation S-038
  found for expected_ctc: the real normalized value lives in
  candidate_memory_facts (category=AVAILABILITY, key=notice_period_days),
  but the only LIVE producer is facts_extraction_service.extract_facts()
  (S-022), which stores whatever raw string Gemini extracted (e.g. "30
  days"), not a pre-normalized integer. This service always runs the
  fact_value through response_parser_service.normalize_notice_period_days()
  (a pure, reusable, already-written function) rather than trusting it
  as already-normalized -- same posture, same follow-up risk note, as
  compensation_scoring_service's handling of expected_ctc.
- jobs.required_start_date does not exist as a spec-named column, but
  Jobs.startDate (Date, nullable) is the real, already-existing
  equivalent -- reused as-is, not duplicated.
- jobs.urgency did not exist at all -- added as a new nullable column
  (see its model comment) via this story's migration.
- Candidate.country (the spec's literal ask, for local-date math) does
  not exist -- Candidate.timezone (String(64), default "Asia/Kolkata")
  is the real, already-live equivalent, already used for exactly this
  purpose by conversation_inactivity_service's own local-time
  computation. Reused the same ZoneInfo-based conversion here rather
  than importing that module's private _to_local() helper.
- "Account for continent holidays" appears in the xlsx summary column
  but nowhere in the docx body -- no BR, no AC, no TC anywhere
  discusses holiday-calendar logic (Step 2 only ever discusses
  timezone). A real xlsx-vs-docx discrepancy, not silently built or
  silently ignored -- flagged in the canonical sheet, not implemented,
  since there's no real spec content to build against and no holiday-
  calendar data source exists anywhere in this codebase.
- Every tiered bucket set in the spec has an ambiguous shared boundary
  as literally worded (e.g. "31-60" and "60+" both literally include
  60). TC-002 (notice=60, IMMEDIATE -> 30) resolves this: the "+"
  tier means STRICTLY GREATER THAN the stated number, and the
  preceding range is inclusive on both ends. Implemented that way
  throughout (>, not >=, for every "+" tier) -- same "resolve via the
  worked example, not the ambiguous prose" call S-037/S-038 both made.
- score_breakdown is a column SHARED with technical_scoring_service
  (S-037) and compensation_scoring_service (S-038) -- this service
  flat-MERGES its own keys (notice_period_days/branch/urgency_used/
  days_until_start) rather than overwriting the whole column, same
  fix already applied to the other two services.
- No event bus -- recalculation wired as a direct call from the end of
  facts_extraction_service.extract_facts(), gated on
  "notice_period_days" actually being among this turn's extracted
  fact_keys (same conditional-trigger posture S-038 used for
  expected_ctc, not S-037's unconditional trigger). Reuses
  technical_scoring_service.linked_job_ids() (the real, public, shared
  candidate-job linkage helper) rather than re-deriving it. Never
  raises -- a scoring failure for one job is logged and skipped, same
  defensive posture as the other two scoring services.
"""
from datetime import date, datetime, timezone as dt_timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_memory import CandidateMemoryFact
from app.models.user import Jobs
from app.services.response_parser_service import normalize_notice_period_days
from app.services.technical_scoring_service import CandidateNotFound, JobNotFound, linked_job_ids

NEUTRAL_SCORE = 50  # BR-01: null notice period, or no comparison point (no urgency, no start date)


def _local_today(tz_name: str) -> date:
    tz = ZoneInfo(tz_name or "Asia/Kolkata")
    return datetime.now(dt_timezone.utc).astimezone(tz).date()


def _get_notice_period_days(db: Session, candidate_id: str, tenant_id: str) -> Optional[int]:
    fact = (
        db.query(CandidateMemoryFact)
        .filter(
            CandidateMemoryFact.tenant_id == tenant_id, CandidateMemoryFact.candidate_id == candidate_id,
            CandidateMemoryFact.fact_category == "AVAILABILITY", CandidateMemoryFact.fact_key == "notice_period_days",
            CandidateMemoryFact.is_active == True,
        )
        .order_by(CandidateMemoryFact.extracted_at.desc())
        .first()
    )
    if fact is None:
        return None
    return normalize_notice_period_days(fact.fact_value)  # parse failure -> None -> neutral, same as "null"


def _score_by_start_date(notice_days: int, days_until_start: int) -> int:
    if notice_days <= days_until_start:
        return 100
    over = notice_days - days_until_start
    if over <= 14:
        return 70
    if over <= 30:
        return 40
    return 15


def _score_by_urgency(notice_days: int, urgency: str) -> int:
    if urgency == "IMMEDIATE":
        if notice_days == 0:
            return 100
        if notice_days <= 14:
            return 85
        if notice_days <= 30:
            return 60
        if notice_days <= 60:
            return 30
        return 10
    if urgency == "HIGH":
        if notice_days <= 30:
            return 100
        if notice_days <= 60:
            return 70
        return 40
    if urgency == "NORMAL":
        if notice_days <= 60:
            return 100
        if notice_days <= 90:
            return 80
        return 50
    if urgency == "FLEXIBLE":
        return 90  # BR-02: even at 0 notice, FLEXIBLE never reaches 100
    return NEUTRAL_SCORE  # unknown urgency value -- treat as no comparison point


def calculate_availability_score(db: Session, candidate_id: str, job_id: str, tenant_id: str) -> Dict:
    """Step 1/Step 2. Upserts availability_score and flat-merges into
    score_breakdown -- see module docstring."""
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        raise CandidateNotFound(f"Candidate {candidate_id!r} not found.")
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if job is None:
        raise JobNotFound(f"Job {job_id!r} not found.")

    notice_days = _get_notice_period_days(db, candidate_id, tenant_id)

    breakdown = {"notice_period_days": notice_days}

    if notice_days is None:  # BR-01
        score = NEUTRAL_SCORE
        breakdown["branch"] = "no_notice_period"
    elif job.startDate is not None:
        days_until_start = (job.startDate - _local_today(candidate.timezone)).days
        score = _score_by_start_date(notice_days, days_until_start)
        breakdown["branch"] = "start_date"
        breakdown["days_until_start"] = days_until_start
    elif job.urgency is not None:
        score = _score_by_urgency(notice_days, job.urgency)
        breakdown["branch"] = "urgency"
        breakdown["urgency_used"] = job.urgency
    else:
        score = NEUTRAL_SCORE  # no start date and no urgency -- no comparison point
        breakdown["branch"] = "no_comparison_point"

    existing = (
        db.query(CandidateJobScore)
        .filter(CandidateJobScore.tenant_id == tenant_id, CandidateJobScore.candidate_id == candidate_id, CandidateJobScore.job_id == job_id)
        .first()
    )
    if existing:
        existing.availability_score = score
        existing.score_breakdown = {**(existing.score_breakdown or {}), **breakdown}  # merge, not overwrite -- see module docstring
        existing.calculated_at = datetime.utcnow()
        db.add(existing)
        record = existing
    else:
        record = CandidateJobScore(
            tenant_id=tenant_id, candidate_id=candidate_id, job_id=job_id,
            availability_score=score, score_breakdown=breakdown, calculated_at=datetime.utcnow(),
        )
        db.add(record)
    db.flush()

    return {
        "candidate_id": candidate_id, "job_id": job_id,
        "technical_score": record.technical_score, "compensation_score": record.compensation_score,
        "availability_score": record.availability_score, "overall_score": record.overall_score,
        "score_breakdown": record.score_breakdown, "calculated_at": record.calculated_at,
    }


def recalculate_for_candidate(db: Session, candidate: Candidate, tenant_id: str) -> List[Dict]:
    """Recalculates availability fit for every job this candidate is
    actually linked to. Never raises -- see module docstring."""
    results = []
    for job_id in linked_job_ids(db, candidate):
        try:
            results.append(calculate_availability_score(db, candidate.candidateID, job_id, tenant_id))
        except Exception as exc:
            logger.warning(f"[AvailabilityScoring] Failed to recalculate score for candidate {candidate.candidateID!r} / job {job_id!r}: {exc}")
    db.commit()
    return results
