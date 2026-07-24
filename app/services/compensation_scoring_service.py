"""
S-038/HRMS-0438 -- Compensation Fit Score.

Real architecture adaptations:
- candidate_job_scores.compensation_score already exists (S-037), left
  NULL/unpopulated on purpose for "the later stories that own those" --
  this story is that later story. No new score table needed.
- candidates.expected_ctc does not exist -- there is no normalized
  numeric column on Candidate at all (see response_parser_service's own
  module docstring: the spec's assumed columns were never added, to
  avoid corrupting the real candidateExpectedSalary display-string
  column everywhere else in the app reads it as text). The real
  normalized value lives in candidate_memory_facts
  (category=SALARY, key=expected_ctc) -- but the only LIVE producer of
  that fact today is facts_extraction_service.extract_facts() (S-022,
  wired into every candidate reply), which stores whatever raw string
  Gemini extracted (e.g. "24 LPA"), NOT a pre-normalized integer.
  response_parser_service.parse_field_response() (S-026) COULD write an
  already-normalized integer-as-string instead, but it is not wired
  into any live path yet -- so in this codebase's actual current state,
  the fact_value is always a raw human string. This service therefore
  always runs the fact_value through response_parser_service.normalize_salary()
  (a pure, reusable, already-written function) rather than trusting it
  as already-normalized. If parse_field_response() is ever wired into a
  live path later, writing a pre-normalized integer, that would double-
  normalize here -- flagged as a real follow-up risk to revisit at that
  point, not fixed preemptively for a path that doesn't exist yet.
- Currency-unit convention (a genuine, unresolved product question,
  flagged rather than silently assumed): normalize_salary() returns
  paise for LPA/lakh phrasing (and for any bare number with no unit --
  its own documented default) or cents for $/k phrasing, with no
  currency tag persisted alongside the value. Job budgets
  (jobs.salaryRange, e.g. "18-22 LPA") are parsed the same way this
  service assumes LPA phrasing throughout, since every real salaryRange
  value observed in this codebase uses that format -- so both sides of
  the comparison land in paise. A candidate whose expected_ctc was
  captured in USD ($/k phrasing) would produce cents, not paise,
  creating a real unit mismatch against a paise-valued budget. This is
  a real, unresolved architecture question (which base currency this
  platform's compensation scoring assumes) -- not silently patched.
- jobs.budget_min/budget_max do not exist on the real Jobs model --
  same lazy-parse-from-free-text posture as S-037's job-requirement
  columns (jobs.salaryRange is recruiter-typed free text, e.g.
  "18-22 LPA"; parsed into two paise integers the first time a job's
  compensation is scored).
- Step 1's "expected_ctc < budget_min by >30% -> score=70" rule is a
  real spec-internal inconsistency, not a codebase gap: it is logically
  unreachable given the rule ordering (the first rule,
  "expected_ctc <= budget_max -> 100", already covers every candidate
  below budget_min, since budget_min <= budget_max by definition, so
  the under-budget-min branch can never fire). It also appears in no
  Acceptance Criterion and no Test Case -- the same "narrated but never
  actually in the formula/AC/TC" pattern S-036/S-037 both had.
  Implemented per the AC/TC (first-match-wins ordering), not the
  unreachable narrative rule; documented here rather than silently
  dropped.
- score_breakdown is a SHARED JSON column with technical_scoring_service
  (S-037) -- this service flat-MERGES its own keys
  (expected_ctc_paise/budget_max_paise/pct_over_budget) into whatever
  breakdown already exists rather than overwriting the whole column, so
  running one score calculation never erases the other's data. Key sets
  don't collide with technical_scoring_service's
  (skill_match_pct/experience_score/certification_score/matched_skills/
  missing_skills), so no namespacing is needed -- technical_scoring_service
  was fixed the same way alongside this story (see its own comment).
- candidate_job_flags: genuinely new table (see its model docstring).
  Step 2's ">20% over budget_max" case inserts/updates exactly one
  open COMPENSATION_MISMATCH flag per (tenant, candidate, job) --
  query-then-upsert, not a DB unique constraint (SQL Server, same
  pattern every upsert this round uses). BR-02: never auto-rejects --
  this is purely an advisory flag for a human recruiter.
- No event bus exists in this codebase -- recalculation is wired as a
  direct call from the end of facts_extraction_service.extract_facts(),
  gated on "expected_ctc" actually being among the fact_keys extracted
  this turn (unlike S-037's unconditional skill-update trigger, salary
  changes are comparatively rare within extract_facts()'s broad fact
  stream, so recalculating on every unrelated fact would be wasteful).
  Reuses technical_scoring_service's real candidate-job linkage
  (candidate.job_id + CandidateJobApplication) rather than duplicating
  that lookup. Never raises -- a scoring failure for one job is logged
  and skipped, same defensive posture as S-037's recalculate_for_candidate().
"""
import re
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_job_flag import CandidateJobFlag
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_memory import CandidateMemoryFact
from app.models.user import Jobs
from app.services.response_parser_service import normalize_salary
from app.services.technical_scoring_service import CandidateNotFound, JobNotFound, linked_job_ids

# Step 1's tiers, in first-match-wins order (see module docstring on the
# unreachable under-budget-min rule).
OVER_BUDGET_TIER_10_PCT = 70
OVER_BUDGET_TIER_20_PCT = 40
OVER_BUDGET_TIER_ABOVE = 10
NEUTRAL_SCORE = 50  # BR-01: null expected_ctc or no budget set

MISMATCH_FLAG_THRESHOLD_PCT = 20


def _ensure_job_budget_parsed(db: Session, job: Jobs) -> None:
    """Lazily populates budget_min/budget_max the first time this job's
    compensation is scored. See module docstring on the LPA/paise
    convention."""
    if job.budget_min is not None or job.budget_max is not None:
        return

    numbers = re.findall(r"\d+(?:\.\d+)?", job.salaryRange or "")
    if not numbers:
        job.budget_min, job.budget_max = None, None
    else:
        values = sorted(int(round(float(n) * 100000 * 100)) for n in numbers)  # LPA -> paise
        job.budget_min = values[0]
        job.budget_max = values[-1]

    db.add(job)
    db.flush()


def _get_expected_ctc_paise(db: Session, candidate_id: str, tenant_id: str) -> Optional[int]:
    fact = (
        db.query(CandidateMemoryFact)
        .filter(
            CandidateMemoryFact.tenant_id == tenant_id, CandidateMemoryFact.candidate_id == candidate_id,
            CandidateMemoryFact.fact_category == "SALARY", CandidateMemoryFact.fact_key == "expected_ctc",
            CandidateMemoryFact.is_active == True,
        )
        .order_by(CandidateMemoryFact.extracted_at.desc())
        .first()
    )
    if fact is None:
        return None
    return normalize_salary(fact.fact_value)  # BR-01: parse failure -> None -> neutral, same as "null"


def _compensation_score(expected_ctc: Optional[int], budget_max: Optional[int]) -> Dict:
    """Step 1. Returns {score, pct_over_budget}. First-match-wins order
    per the AC/TC -- see module docstring."""
    if expected_ctc is None or budget_max is None:  # BR-01
        return {"score": NEUTRAL_SCORE, "pct_over_budget": None}

    if expected_ctc <= budget_max:
        return {"score": 100, "pct_over_budget": 0.0}

    pct_over = (expected_ctc - budget_max) / budget_max * 100
    if pct_over <= 10:
        return {"score": OVER_BUDGET_TIER_10_PCT, "pct_over_budget": round(pct_over, 1)}
    if pct_over <= 20:
        return {"score": OVER_BUDGET_TIER_20_PCT, "pct_over_budget": round(pct_over, 1)}
    return {"score": OVER_BUDGET_TIER_ABOVE, "pct_over_budget": round(pct_over, 1)}


def _upsert_mismatch_flag(db: Session, tenant_id: str, candidate_id: str, job_id: str, pct_over: float) -> None:
    """Step 2. BR-02: advisory only, never auto-rejects."""
    existing = (
        db.query(CandidateJobFlag)
        .filter(
            CandidateJobFlag.tenant_id == tenant_id, CandidateJobFlag.candidate_id == candidate_id,
            CandidateJobFlag.job_id == job_id, CandidateJobFlag.flag_type == "COMPENSATION_MISMATCH",
            CandidateJobFlag.is_resolved == False,
        )
        .first()
    )
    message = f"Candidate's expected compensation is {pct_over:.0f}% over this role's budget."
    if existing:
        existing.message = message
        db.add(existing)
    else:
        db.add(CandidateJobFlag(
            tenant_id=tenant_id, candidate_id=candidate_id, job_id=job_id,
            flag_type="COMPENSATION_MISMATCH", message=message, severity="HIGH",
        ))
    db.flush()


def calculate_compensation_score(db: Session, candidate_id: str, job_id: str, tenant_id: str) -> Dict:
    """Reuses candidate_job_scores (S-037) -- upserts compensation_score
    and MERGES a "compensation" key into score_breakdown (never
    overwrites the whole column, see module docstring)."""
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        raise CandidateNotFound(f"Candidate {candidate_id!r} not found.")
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if job is None:
        raise JobNotFound(f"Job {job_id!r} not found.")

    _ensure_job_budget_parsed(db, job)

    expected_ctc = _get_expected_ctc_paise(db, candidate_id, tenant_id)
    result = _compensation_score(expected_ctc, job.budget_max)

    if result["pct_over_budget"] is not None and result["pct_over_budget"] > MISMATCH_FLAG_THRESHOLD_PCT:
        _upsert_mismatch_flag(db, tenant_id, candidate_id, job_id, result["pct_over_budget"])

    breakdown = {
        "expected_ctc_paise": expected_ctc, "budget_max_paise": job.budget_max,
        "pct_over_budget": result["pct_over_budget"],
    }

    existing = (
        db.query(CandidateJobScore)
        .filter(CandidateJobScore.tenant_id == tenant_id, CandidateJobScore.candidate_id == candidate_id, CandidateJobScore.job_id == job_id)
        .first()
    )
    if existing:
        existing.compensation_score = result["score"]
        existing.score_breakdown = {**(existing.score_breakdown or {}), **breakdown}  # merge, not overwrite -- see module docstring
        existing.calculated_at = datetime.utcnow()
        db.add(existing)
        record = existing
    else:
        record = CandidateJobScore(
            tenant_id=tenant_id, candidate_id=candidate_id, job_id=job_id,
            compensation_score=result["score"], score_breakdown=breakdown,
            calculated_at=datetime.utcnow(),
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
    """Recalculates compensation fit for every job this candidate is
    actually linked to. Never raises -- see module docstring."""
    results = []
    for job_id in linked_job_ids(db, candidate):
        try:
            results.append(calculate_compensation_score(db, candidate.candidateID, job_id, tenant_id))
        except Exception as exc:
            logger.warning(f"[CompensationScoring] Failed to recalculate score for candidate {candidate.candidateID!r} / job {job_id!r}: {exc}")
    db.commit()
    return results
