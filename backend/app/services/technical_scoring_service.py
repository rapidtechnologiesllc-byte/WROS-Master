"""
import logging
S-037/HRMS-0437 -- Technical Qualification Score.

Real architecture adaptations:
- candidate_job_scores: genuinely new table (see its model docstring),
  Integer PK + String(50) UserID-as-tenant_id convention, not the
  spec's UUID assumption.
- Jobs has no required_skills/min_experience_years/domain/
  certifications_preferred columns -- the real recruiter-entered
  fields are jobSkills (free-text Text, comma-separated) and
  jobExperience (free-text String(50), e.g. "5+ years"/"3-5 years").
  Added four new nullable columns to Jobs (see its model's S-037
  comment) and lazily populate them the first time a job is scored --
  parsing jobSkills through the same normalize_skills() candidates use
  (BR-01: canonical-to-canonical matching only, never raw strings) and
  extracting a leading integer from jobExperience via regex. There is
  no recruiter-entered certifications field on Jobs at all --
  certifications_preferred lazily initializes to an empty list (no
  certs required) rather than inventing a source that doesn't exist;
  certification_score is 100 until a real UI to enter this exists.
- "domain" is a real spec-internal inconsistency, not a codebase gap:
  the story's own "What You Are Building"/precondition sections list
  domain match as a fourth scoring input, but Step 2's actual formula,
  every acceptance criterion, and every test case only ever reference
  three weighted components (skill 40% + experience 35% + cert 25% =
  100%). Built to the formula/AC/TC (the part QA actually verifies),
  not the narrative aside -- domain is stored on Jobs for a future
  story to use but is NOT scored here.
- BR-01's own worked example ("Guidewire ClaimCenter" earning partial
  credit against a "Guidewire PolicyCenter" requirement) can't be
  represented with the real synonym library: skill_synonyms.py
  collapses ClaimCenter/PolicyCenter/BillingCenter (and all their
  abbreviations) down to ONE canonical skill, "Guidewire" -- there is
  no sub-module granularity left post-normalization to apply partial
  credit to. Implemented as the AC/TC actually test: full credit per
  matched canonical skill, no sub-module partial credit. Changing the
  synonym library to add sub-module granularity is a real, separate
  Lead-BA-approval-gated decision (same posture as skill_synonyms.py's
  own file header), not made unilaterally here.
- No event bus exists in this codebase -- "publish
  candidate.skills_extracted / candidate.resume_parsed, HRMS-0437
  listens" is adapted to a direct call from the end of
  skill_extraction_service.extract_and_tag_skills() (covers both
  triggers: a fresh resume parse always calls that function, and any
  other skill-update path recalculates too). Only recalculates for
  jobs the candidate is actually linked to -- candidate.job_id (the
  primary link) plus every CandidateJobApplication row for that
  candidate (the real many-to-many junction table) -- never a blind
  fan-out across all jobs. "New job created+linked to demand" and
  "candidate manually linked to job" triggers are NOT wired this round
  -- those touch create_job.py and whatever assigns candidate.job_id,
  both already-shipped call sites, same non-retrofit caution this round
  has applied elsewhere; flagged as a real follow-up, not silently
  faked. recalculate_for_candidate() never raises -- a scoring failure
  for one job must not block the resume/skill pipeline it's wired into,
  nor prevent scoring the candidate's other linked jobs.
"""
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate, CandidateJobApplication
from app.models.candidate_job_score import CandidateJobScore
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.user import Jobs
from app.services.skill_extraction_service import normalize_skills

# Step 2's weights.
SKILL_WEIGHT = 0.40
EXPERIENCE_WEIGHT = 0.35
CERTIFICATION_WEIGHT = 0.25

MISSING_CERT_PENALTY = 25

logger = logging.getLogger(__name__)

class CandidateNotFound(Exception):
    pass


class JobNotFound(Exception):
    pass


def _ensure_job_requirements_parsed(db: Session, job: Jobs) -> None:
    """Lazily populates the structured requirement columns the first
    time this job is scored. See module docstring."""
    if job.required_skills_canonical is not None:
        return

    raw_skills = [s.strip() for s in re.split(r"[,;]", job.jobSkills or "") if s.strip()]
    normalized = normalize_skills(raw_skills)
    job.required_skills_canonical = [item["canonical"] for item in normalized]

    match = re.search(r"\d+", job.jobExperience or "")
    job.min_experience_years = int(match.group()) if match else 0

    job.certifications_preferred = []  # no real source field on Jobs -- see module docstring

    db.add(job)
    db.flush()


def _skill_match_score(required_skills: List[str], candidate_skills: set) -> Dict:
    if not required_skills:
        return {"score": 100, "matched": [], "missing": []}
    matched = [s for s in required_skills if s in candidate_skills]
    missing = [s for s in required_skills if s not in candidate_skills]
    return {"score": round(len(matched) / len(required_skills) * 100), "matched": matched, "missing": missing}


def _experience_score(candidate_years: float, min_years: int) -> int:
    """BR-02: more than 2 years below the requirement is capped at 20,
    regardless of other factors -- the tiered formula already enforces
    this by construction (the >2-years-below branch IS the floor)."""
    if min_years <= 0 or candidate_years >= min_years:
        return 100
    shortfall = min_years - candidate_years
    if shortfall <= 1:
        return 70
    if shortfall <= 2:
        return 40
    return 20


def _certification_score(preferred_certs: List[str], candidate_cert_names: set) -> int:
    if not preferred_certs:
        return 100
    missing_count = sum(1 for c in preferred_certs if c.lower() not in candidate_cert_names)
    return max(0, 100 - missing_count * MISSING_CERT_PENALTY)


def calculate_technical_score(db: Session, candidate_id: str, job_id: str, tenant_id: str) -> Dict:
    """Step 2. Returns the full CandidateJobScore payload, including
    score_breakdown. Upserts (query-then-update, no ON CONFLICT -- SQL
    Server, same pattern every upsert this round uses)."""
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if candidate is None:
        raise CandidateNotFound(f"Candidate {candidate_id!r} not found.")
    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if job is None:
        raise JobNotFound(f"Job {job_id!r} not found.")

    _ensure_job_requirements_parsed(db, job)

    candidate_skills = {
        t.skill_canonical for t in
        db.query(CandidateSkillTag).filter(CandidateSkillTag.tenant_id == tenant_id, CandidateSkillTag.candidate_id == candidate_id).all()
    }

    resume = db.query(CandidateResumeParsed).filter(CandidateResumeParsed.candidate_id == candidate_id).first()
    if resume and resume.total_experience_years is not None:
        candidate_years = resume.total_experience_years
    elif candidate.total_experience_months is not None:
        candidate_years = candidate.total_experience_months / 12.0
    else:
        candidate_years = 0.0

    candidate_cert_names = set()
    if resume and resume.certifications:
        for cert in resume.certifications:
            name = cert.get("name") if isinstance(cert, dict) else cert
            if name:
                candidate_cert_names.add(str(name).strip().lower())

    skill_result = _skill_match_score(job.required_skills_canonical or [], candidate_skills)
    experience_score = _experience_score(candidate_years, job.min_experience_years or 0)
    certification_score = _certification_score(job.certifications_preferred or [], candidate_cert_names)

    technical_score = round(
        skill_result["score"] * SKILL_WEIGHT + experience_score * EXPERIENCE_WEIGHT + certification_score * CERTIFICATION_WEIGHT
    )

    breakdown = {
        "skill_match_pct": skill_result["score"],
        "experience_score": experience_score,
        "certification_score": certification_score,
        "matched_skills": skill_result["matched"],
        "missing_skills": skill_result["missing"],
    }

    existing = (
        db.query(CandidateJobScore)
        .filter(CandidateJobScore.tenant_id == tenant_id, CandidateJobScore.candidate_id == candidate_id, CandidateJobScore.job_id == job_id)
        .first()
    )
    if existing:
        existing.technical_score = technical_score
        # Merge, not overwrite -- score_breakdown is a column SHARED with
        # compensation_scoring_service (S-038); a full replace here would
        # silently erase that service's keys on every technical rescore.
        # Key sets don't collide (skill_match_pct/experience_score/
        # certification_score/matched_skills/missing_skills vs
        # expected_ctc_paise/budget_max_paise/pct_over_budget), so a flat
        # merge is sufficient -- no namespacing needed.
        existing.score_breakdown = {**(existing.score_breakdown or {}), **breakdown}
        existing.calculated_at = datetime.utcnow()
        db.add(existing)
        record = existing
    else:
        record = CandidateJobScore(
            tenant_id=tenant_id, candidate_id=candidate_id, job_id=job_id,
            technical_score=technical_score, score_breakdown=breakdown, calculated_at=datetime.utcnow(),
        )
        db.add(record)
    db.flush()

    return {
        "candidate_id": candidate_id, "job_id": job_id,
        "technical_score": record.technical_score, "compensation_score": record.compensation_score,
        "availability_score": record.availability_score, "overall_score": record.overall_score,
        "score_breakdown": record.score_breakdown, "calculated_at": record.calculated_at,
    }


def linked_job_ids(db: Session, candidate: Candidate) -> List[str]:
    """Public (not underscore-prefixed) -- shared with
    compensation_scoring_service (S-038), which scores the same real
    candidate-job linkage rather than re-deriving it independently."""
    job_ids = set()
    if candidate.job_id:
        job_ids.add(candidate.job_id)
    applications = db.query(CandidateJobApplication).filter(CandidateJobApplication.candidate_id == candidate.candidateID).all()
    job_ids.update(a.job_id for a in applications)
    return list(job_ids)


def recalculate_for_candidate(db: Session, candidate: Candidate, tenant_id: str) -> List[Dict]:
    """BR-03. Recalculates technical_score for every job this candidate
    is actually linked to (candidate.job_id + CandidateJobApplication
    rows). Never raises -- a failure scoring one job is logged and
    skipped, never blocks the caller (the skill-extraction pipeline)."""
    results = []
    for job_id in linked_job_ids(db, candidate):
        try:
            results.append(calculate_technical_score(db, candidate.candidateID, job_id, tenant_id))
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[TechnicalScoring] Failed to recalculate score for candidate {candidate.candidateID!r} / job {job_id!r}: {exc}")
    db.commit()
    return results
