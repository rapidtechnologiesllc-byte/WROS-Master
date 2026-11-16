"""The recruiter agent's search for each job: write the search criteria when the job goes live, capture the
candidates who match, and write to each of them personally.

ensure_criteria(job)       the job's boolean search, written once from its skills (every known name of each
                           skill, mandatory skills joined by the job's AND / OR rule). A recruiter's edit wins.
capture_for_job(job)       candidates in the job's pool (job_candidate_ranking_service.candidate_pool: tenant,
                           not rejected or hired, location) who pass the hiring rules every job applies (the
                           5-year floor, the job's own minimum, employment type by country) and match the
                           criteria on skills, title or resume. Each is recorded once (JobSearchMatch).
reach_out(job)             the best captured matches not yet written to get one personal email each
                           (role_outreach_service: consent, contactability, Thunder's stop, send window and caps
                           all apply; the client is never named). At most JOB_OUTREACH_PER_RUN per job per run.
run_capture_job            the scheduled job: every open job, capture then reach out. Replies are read by
                           Thunder, which books the call itself; Flash missions take the interviews from there.

Rules only. A job with no skills and no title words cannot have criteria; that is logged, never guessed.
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.constants.skill_synonyms import SKILL_SYNONYMS
from app.core.config import settings
from app.models.candidate import Candidate
from app.models.client_update import RoleOutreach
from app.models.job_search import JobSearchCriteria, JobSearchMatch
from app.models.user import Jobs, Users
from app.services.boolean_search_service import BooleanQueryError, CompiledQuery, documents_for, synonyms_for

logger = logging.getLogger(__name__)

OPEN_JOB_STATUSES = ("active", "public")
TITLE_NOISE = {"senior", "junior", "lead", "sr", "jr", "the", "and", "for", "with", "of", "a", "an", "ii", "iii"}


class JobSearchError(ValueError):
    pass


# ---- criteria -------------------------------------------------------------------------------------

def _quoted(name: str) -> str:
    return '"' + " ".join(name.replace('"', " ").split()) + '"'


def _skill_group(name: str, synonyms: Optional[Dict[str, List[str]]] = None) -> str:
    """One skill with every name it goes by: ("Guidewire" OR "GW" OR ...); with the tenant's synonyms (synonyms_for)
    the names the team added are in it too."""
    if synonyms is not None:
        names = [name, *synonyms.get(name.lower(), [])]
    else:
        names = [name, *next((others for known, others in SKILL_SYNONYMS.items() if known.lower() == name.lower()), [])]
    unique = list(dict.fromkeys(_quoted(n) for n in names if n.strip()))
    return unique[0] if len(unique) == 1 else "(" + " OR ".join(unique) + ")"


def generate_query(job: Jobs, synonyms: Optional[Dict[str, List[str]]] = None) -> str:
    """The boolean search for a job, from its skills; with none, from the words of its title."""
    from app.services.skill_matching_service import SkillMatchingService

    skills = SkillMatchingService.job_skills(job)
    mandatory = [s["name"] for s in skills if s.get("mandatory", True)] or [s["name"] for s in skills]
    if mandatory:
        joiner = " OR " if (job.job_skills_boolean_mode or "AND").upper() == "OR" else " AND "
        return joiner.join(_skill_group(name, synonyms) for name in mandatory)
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9+#.]*", job.jobTitle or "") if w.lower() not in TITLE_NOISE]
    if not words:
        raise JobSearchError(f"Job {job.jobID} lists no skills and its title has no searchable words.")
    return _quoted(" ".join(words))


def ensure_criteria(db: Session, job: Jobs) -> JobSearchCriteria:
    """The job's criteria, written from the job the first time. Flushes; the caller commits."""
    criteria = db.get(JobSearchCriteria, job.jobID)
    if criteria is None:
        query = CompiledQuery(generate_query(job, synonyms_for(db, job.tenant_id))).text
        criteria = JobSearchCriteria(job_id=job.jobID, tenant_id=job.tenant_id, boolean_query=query, generated_query=query)
        db.add(criteria)
        db.flush()
        logger.info(f"[JobSearch] {job.jobID}: criteria written: {query}")
    return criteria


def save_criteria(db: Session, job: Jobs, user: Users, query: str) -> JobSearchCriteria:
    """A recruiter's own search for the job. Raises BooleanQueryError when it cannot be read."""
    criteria = ensure_criteria(db, job)
    criteria.boolean_query = CompiledQuery(query).text
    criteria.edited_by, criteria.edited_at = user.UserID, datetime.utcnow()
    db.flush()
    logger.info(f"[JobSearch] {job.jobID}: criteria edited by {user.UserID}: {criteria.boolean_query}")
    return criteria


def reset_criteria(db: Session, job: Jobs) -> JobSearchCriteria:
    """Back to the system's version, rewritten from the job as it is now."""
    criteria = ensure_criteria(db, job)
    query = CompiledQuery(generate_query(job, synonyms_for(db, job.tenant_id))).text
    criteria.boolean_query = criteria.generated_query = query
    criteria.edited_by = criteria.edited_at = None
    db.flush()
    return criteria


def rewrite_system_criteria(db: Session, tenant_id) -> int:
    """After the team changes a skill's other names: every job's system version is written again with them, and
    jobs still on the system's version search with it. A recruiter's own search is left as they wrote it.
    Flushes; returns how many jobs now search differently."""
    if tenant_id is None:
        return 0
    synonyms = synonyms_for(db, tenant_id)
    changed = 0
    rows = (db.query(JobSearchCriteria, Jobs).join(Jobs, Jobs.jobID == JobSearchCriteria.job_id)
            .filter(JobSearchCriteria.tenant_id == tenant_id).all())
    for criteria, job in rows:
        try:
            query = CompiledQuery(generate_query(job, synonyms)).text
        except (JobSearchError, BooleanQueryError) as exc:
            logger.error(f"[JobSearch] {job.jobID}: system search not rewritten: {exc}")
            continue
        criteria.generated_query = query
        if criteria.edited_by is None and criteria.boolean_query != query:
            criteria.boolean_query = query
            changed += 1
    db.flush()
    logger.info(f"[JobSearch] tenant {tenant_id}: synonyms changed, {changed} job search(es) rewritten")
    return changed


# ---- capture --------------------------------------------------------------------------------------

def capture_for_job(db: Session, job: Jobs, now: Optional[datetime] = None) -> List[JobSearchMatch]:
    """Record every candidate who newly matches the job's criteria. Flushes; returns the new matches."""
    from app.services.employment_type_policy import interview_check
    from app.services.job_candidate_ranking_service import candidate_pool
    from app.services.submission_service import check_experience_eligibility, check_job_experience

    now = now or datetime.utcnow()
    criteria = ensure_criteria(db, job)
    compiled = CompiledQuery(criteria.boolean_query, synonyms_for(db, job.tenant_id))
    known = [row[0] for row in db.query(JobSearchMatch.candidate_id).filter(JobSearchMatch.job_id == job.jobID).all()]
    pool = [c for c in candidate_pool(db, job, exclude_ids=known).filter(Candidate.merged_into_id.is_(None)).all()
            if check_experience_eligibility(c)["is_eligible"] and check_job_experience(c, job)["allowed"]
            and interview_check(c)["allowed"]]
    documents = documents_for(db, pool)
    captured = []
    for candidate in pool:
        match = compiled.match(documents[candidate.candidateID])
        if match is None:
            continue
        row = JobSearchMatch(tenant_id=job.tenant_id, job_id=job.jobID, candidate_id=candidate.candidateID,
                             score=match.score, found=match.found, snippet=match.snippet or None, status="CAPTURED")
        db.add(row)
        captured.append(row)
    criteria.last_run_at = now
    db.flush()
    logger.info(f"[JobSearch] {job.jobID}: {len(captured)} new match(es) of {len(pool)} eligible candidate(s)")
    return captured


# ---- outreach -------------------------------------------------------------------------------------

def reach_out(db: Session, job: Jobs, now: Optional[datetime] = None, *, brain=None) -> int:
    """Write to the best captured matches not yet written to; returns how many emails were queued. Commits."""
    from app.services.role_outreach_service import queue_role_outreach
    from app.services.thunder_pause_service import is_thunder_paused

    now = now or datetime.utcnow()
    if not settings.JOB_AUTO_OUTREACH:
        return 0
    if is_thunder_paused(db):
        logger.info(f"[JobSearch] {job.jobID}: Thunder is paused; captured matches wait")
        return 0
    waiting = (db.query(JobSearchMatch).filter(JobSearchMatch.job_id == job.jobID, JobSearchMatch.status == "CAPTURED")
               .order_by(JobSearchMatch.score.desc(), JobSearchMatch.id).limit(settings.JOB_OUTREACH_PER_RUN).all())
    if not waiting:
        return 0
    by_candidate = {m.candidate_id: m for m in waiting}
    queued = queue_role_outreach(db, job, [{"candidate_id": m.candidate_id, "recency_score": m.score} for m in waiting],
                                 brain=brain)
    for outreach in db.query(RoleOutreach).filter(RoleOutreach.job_id == job.jobID,
                                                  RoleOutreach.candidate_id.in_(list(by_candidate))).all():
        match = by_candidate[outreach.candidate_id]
        if outreach.status == "SKIPPED":
            match.status, match.note = "SKIPPED", outreach.note
        else:
            match.status, match.contacted_at = "CONTACTED", now
    db.commit()
    return queued


# ---- the scheduled job ----------------------------------------------------------------------------

def _open_jobs(db: Session, since: datetime) -> List[Jobs]:
    return (db.query(Jobs).filter(Jobs.jobStatus.in_(OPEN_JOB_STATUSES), Jobs.is_deleted.isnot(True),
                                  Jobs.tenant_id.isnot(None), Jobs.jobCreatedAt >= since)
            .order_by(Jobs.jobCreatedAt).all())


def backlog_guard(db: Session, now: datetime) -> None:
    """Before the first run: on jobs opened before the recent window, candidates who already match are recorded
    as found earlier and never written to, so switching this on cannot email a backlog about an old job."""
    recent = now - timedelta(days=settings.FLASH_AUTO_MISSION_DAYS)
    held = 0
    for job in _open_jobs(db, now - timedelta(days=settings.JOB_SEARCH_ACTIVE_DAYS)):
        if job.jobCreatedAt >= recent:
            continue
        try:
            with db.begin_nested():
                for match in capture_for_job(db, job, now):
                    match.status, match.note = "SKIPPED", "matched before automatic outreach was switched on"
                    held += 1
        except (JobSearchError, BooleanQueryError, ValueError) as exc:
            logger.error(f"[JobSearch] backlog guard: job {job.jobID} skipped: {exc}", exc_info=True)
    db.commit()
    logger.info(f"[JobSearch] first run at {now:%Y-%m-%d %H:%M} UTC: {held} earlier match(es) recorded, not written to")


def run_capture_job(db: Session, now: Optional[datetime] = None, *, brain=None) -> Dict:
    """Every open job: capture who matches, then write to the best of them. One job failing never stops the rest."""
    now = now or datetime.utcnow()
    result = {"jobs": 0, "captured": 0, "emails_queued": 0, "failed": 0}
    for job in _open_jobs(db, now - timedelta(days=settings.JOB_SEARCH_ACTIVE_DAYS)):
        job_id = job.jobID
        try:
            captured = capture_for_job(db, job, now)
            db.commit()
            result["jobs"] += 1
            result["captured"] += len(captured)
            result["emails_queued"] += reach_out(db, job, now, brain=brain)
        except Exception as exc:
            db.rollback()
            result["failed"] += 1
            logger.error(f"[JobSearch] job {job_id} failed: {exc}", exc_info=True)
    logger.info(f"[JobSearch] {result}")
    return result


# ---- reading --------------------------------------------------------------------------------------

def criteria_view(db: Session, job: Jobs) -> Dict:
    criteria = ensure_criteria(db, job)
    counts = {status: 0 for status in ("CAPTURED", "CONTACTED", "SKIPPED")}
    for status, in db.query(JobSearchMatch.status).filter(JobSearchMatch.job_id == job.jobID).all():
        counts[status] = counts.get(status, 0) + 1
    editor = db.get(Users, criteria.edited_by) if criteria.edited_by else None
    return {"job_id": job.jobID, "query": criteria.boolean_query, "generated_query": criteria.generated_query,
            "edited": criteria.edited_by is not None, "edited_by_name": editor.UserName if editor else None,
            "edited_at": criteria.edited_at, "last_run_at": criteria.last_run_at,
            "matches": {"captured": counts["CAPTURED"], "contacted": counts["CONTACTED"], "skipped": counts["SKIPPED"],
                        "total": sum(counts.values())}}


def matches_view(db: Session, job: Jobs, limit: int = 200) -> List[Dict]:
    rows = (db.query(JobSearchMatch, Candidate).join(Candidate, Candidate.candidateID == JobSearchMatch.candidate_id)
            .filter(JobSearchMatch.job_id == job.jobID)
            .order_by(JobSearchMatch.score.desc(), JobSearchMatch.id).limit(min(max(limit, 1), 500)).all())
    return [{"candidate_id": c.candidateID,
             "name": " ".join(p for p in (c.candidateFirstName, c.candidateLastName) if p) or c.candidateID,
             "title": c.candidateJobTitle, "location": c.candidateCurrentLocation,
             "experience_years": round(c.total_experience_months / 12, 1) if c.total_experience_months else None,
             "score": m.score, "found": m.found or {}, "snippet": m.snippet, "status": m.status, "note": m.note,
             "captured_at": m.created_at, "contacted_at": m.contacted_at} for m, c in rows]
