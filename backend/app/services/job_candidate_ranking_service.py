"""The one rule for "which candidates fit this job, best first". Used by Flash's sourcing run
(SourceCandidatesHandler), Flash's job search (flash_service.find_candidates_for_job) and,
later, Flash missions.

Pool: the job's tenant only, not rejected or hired; with a viewer, only the candidates that
viewer may see (apply_bu_scope_to_candidate_query); for an onsite or hybrid job, candidates
whose location matches the job's.

Hard gates, every time: the company-wide 5-year floor (check_experience_eligibility; unverified
experience fails) and the job's own minimum (check_job_experience).

Skills: SkillMatchingService.score_skills on canonical names. A candidate qualifies at
settings.FLASH_MATCH_MIN_SCORE or above with no required skill missing.

Order: score, then experience, both descending; then the earliest-created candidate; then id
(so ties are stable).
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.user import Jobs, Users
from app.services.candidate_pipeline_stage import pipeline_stage_in
from app.services.skill_matching_service import SkillMatchingService
from app.services.submission_service import MIN_EXPERIENCE_MONTHS, check_experience_eligibility, check_job_experience

logger = logging.getLogger(__name__)


@dataclass
class RankedCandidate:
    candidate_id: str
    name: str
    score: int
    matched: List[str] = field(default_factory=list)
    missing_mandatory: List[str] = field(default_factory=list)
    experience_months: int = 0


def candidate_pool(db: Session, job: Jobs, *, viewer: Optional[Users] = None, exclude_ids: Iterable[str] = ()):
    """The candidates a job may draw from, before the experience and skill gates."""
    if job.tenant_id is None:
        raise ValueError(f"Job {job.jobID} has no tenant; candidates cannot be ranked for it")
    query = db.query(Candidate).filter(
        Candidate.tenant_id == job.tenant_id,
        ~pipeline_stage_in("REJECTED", "HIRED"),
        # the 5-year floor narrows the pool in SQL; check_experience_eligibility below is the rule
        Candidate.total_experience_months >= MIN_EXPERIENCE_MONTHS,
    )
    exclude = [i for i in exclude_ids if i]
    if exclude:
        query = query.filter(~Candidate.candidateID.in_(exclude))
    if viewer is not None:
        if viewer.tenant_id != job.tenant_id:
            raise ValueError(f"User {viewer.UserID} is not in job {job.jobID}'s tenant")
        from app.core.bu_scope import apply_bu_scope_to_candidate_query

        query = apply_bu_scope_to_candidate_query(db, query, viewer)
    if (job.work_location or "REMOTE").upper() != "REMOTE" and (job.jobLocation or "").strip():
        query = query.filter(Candidate.candidateCurrentLocation.ilike(f"%{job.jobLocation.strip()}%"))
    return query


def rank_candidates_for_job(
    db: Session, job: Jobs, *, viewer: Optional[Users] = None, exclude_ids: Iterable[str] = (), limit: int = 20,
) -> List[RankedCandidate]:
    """The job's qualifying candidates, best first, at most `limit`."""
    job_skills = SkillMatchingService.job_skills(job)
    if not job_skills:
        logger.warning(f"[Ranking] Job {job.jobID} lists no skills; no candidate can qualify")
        return []

    pool = {c.candidateID: c for c in candidate_pool(db, job, viewer=viewer, exclude_ids=exclude_ids).all()}
    if not pool:
        return []
    tags = {}
    for tag in db.query(CandidateSkillTag).filter(CandidateSkillTag.tenant_id == str(job.tenant_id),
                                                   CandidateSkillTag.candidate_id.in_(list(pool))).all():
        tags.setdefault(tag.candidate_id, []).append(tag)

    mode = job.job_skills_boolean_mode or "AND"
    ranked = []
    for candidate in pool.values():
        if not check_experience_eligibility(candidate)["is_eligible"]:
            continue
        if not check_job_experience(candidate, job)["allowed"]:
            continue
        result = SkillMatchingService.score_skills(
            job_skills, SkillMatchingService.candidate_skills(db, candidate, tags.get(candidate.candidateID, [])),
            mode=mode)
        if not result["can_proceed"]:
            continue
        ranked.append((candidate, RankedCandidate(
            candidate_id=candidate.candidateID,
            name=" ".join(p for p in [candidate.candidateFirstName, candidate.candidateLastName] if p)
            or candidate.candidateID,
            score=result["score"], matched=result["matched"], missing_mandatory=result["missing_mandatory"],
            experience_months=candidate.total_experience_months,
        )))

    ranked.sort(key=lambda pair: (-pair[1].score, -pair[1].experience_months,
                                  pair[0].candidateCreatedAt or datetime.max, pair[0].candidateID))
    logger.info(f"[Ranking] Job {job.jobID}: {len(ranked)} of {len(pool)} candidates qualify")
    return [r for _, r in ranked[:limit]]
