"""The job workspace: everything the screen shows about one job, read and saved through one shape, and the
candidates on the job with the stage each one is really in.

job_view         every field the screen shows, with the names of the people and the client. The same shape is
                 returned after a save, so nothing on the screen falls back to a dash.
apply_extras     the fields the older update route does not know (position type, priority, work mode, minimum
                 experience, how skills combine). A change of skills also rewrites the structured skills the
                 matching reads, and the job's search criteria when nobody has edited them by hand.
job_candidates   everyone connected to the job (applied, on its hiring pipeline, submitted to the client, or
                 found by the recruiter agent's search), each in one stage read from the hiring pipeline, with a
                 count per stage. The counts and the list come from the same rows, so they always agree.
"""
import json
import logging
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateJobApplication, CandidateStatus
from app.models.demand import EMPLOYMENT_TYPES, URGENCY_LEVELS, WORK_LOCATIONS
from app.models.hiring_pipeline import CLOSED_STAGES, HiringPipeline
from app.models.job_search import JobSearchCriteria, JobSearchMatch
from app.models.submission import Submission
from app.models.user import Jobs, Users

logger = logging.getLogger(__name__)

# The stages the screen shows, in hiring order, and the pipeline stages each one covers
STAGES = ("Sourced", "Recruiter Screening", "L1 Interview", "L2 Interview", "Offer", "Pre-Onboarding", "Hired", "Closed")
STAGE_OF = {"SCREEN": "Recruiter Screening", "L1": "L1 Interview", "L2": "L2 Interview", "OFFER": "Offer",
            "ACCEPTED": "Offer", "ONBOARDING": "Pre-Onboarding", "BGV": "Pre-Onboarding", "BENCH": "Hired",
            "SUBMITTED": "Hired", "CLIENT_SELECTED": "Hired", "CLIENT_ONBOARDING": "Hired", "ALLOCATED": "Hired",
            **{stage: "Closed" for stage in CLOSED_STAGES}}
BOOLEAN_MODES = ("AND", "OR")


class JobWorkspaceError(ValueError):
    pass


def _user_name(db: Session, user_id: Optional[str]) -> Optional[str]:
    user = db.get(Users, user_id) if user_id else None
    return (user.UserName or user.UserEmail) if user is not None else None


def job_view(db: Session, job: Jobs) -> Dict:
    from app.models.client import Client
    from app.models.opportunity import Opportunity
    from app.models.org_structure import Department

    client = db.get(Client, job.client_id) if job.client_id else None
    opportunity = db.get(Opportunity, job.opportunity_id) if job.opportunity_id else None
    department = db.get(Department, job.department_id) if job.department_id else None
    return {
        "job_id": job.jobID, "job_title": job.jobTitle, "job_description": job.jobDescription,
        "job_skills": job.jobSkills, "job_skills_boolean_mode": job.job_skills_boolean_mode or "AND",
        "job_experience": job.jobExperience,
        "min_experience_years": float(job.min_experience_years) if job.min_experience_years is not None else None,
        "job_location": job.jobLocation, "work_location": job.work_location, "employment_type": job.employment_type,
        "urgency": job.urgency, "salary_range": job.salaryRange, "job_status": job.jobStatus,
        "confirmation_status": job.confirmation_status, "no_of_positions": job.noOfPositions,
        "positions_filled": job.positions_filled or 0, "start_date": job.startDate, "end_date": job.endDate,
        "job_created_at": job.jobCreatedAt,
        "company_name": job.companyName, "company_type": job.companyType, "client_id": job.client_id,
        "client_name": client.company_name if client is not None else None,
        "opportunity_id": job.opportunity_id, "opportunity_stage": opportunity.stage if opportunity is not None else None,
        "project_id": job.project_id, "business_unit": job.business_unit_id,
        "department_id": job.department_id, "department_name": department.name if department is not None else None,
        "contact_person": job.contactPerson, "contact_person_name": _user_name(db, job.contactPerson),
        "hiring_manager_id": job.hiringManagerID, "hiring_manager_name": _user_name(db, job.hiringManagerID),
        "recuriter_id": job.recuriterID, "recruiter_name": _user_name(db, job.recuriterID),
        "options": {"employment_types": list(EMPLOYMENT_TYPES), "urgency_levels": list(URGENCY_LEVELS),
                    "work_locations": list(WORK_LOCATIONS), "boolean_modes": list(BOOLEAN_MODES)},
    }


def validate_edit(job: Jobs, fields: Dict) -> None:
    """Refuse a save that would leave the job wrong, before anything is written."""
    if "job_title" in fields and not (fields["job_title"] or "").strip():
        raise JobWorkspaceError("A job needs a title.")
    if fields.get("no_of_positions") is not None and fields["no_of_positions"] < 1:
        raise JobWorkspaceError("A job has at least one position.")
    if fields.get("no_of_positions") is not None and fields["no_of_positions"] < (job.positions_filled or 0):
        raise JobWorkspaceError(f"{job.positions_filled} position(s) are already filled: the total cannot be lower.")
    start: Optional[date] = fields.get("start_date", job.startDate)
    end: Optional[date] = fields.get("end_date", job.endDate)
    if start and end and end < start:
        raise JobWorkspaceError("The end date is before the start date.")
    if fields.get("employment_type") is not None and fields["employment_type"] not in EMPLOYMENT_TYPES:
        raise JobWorkspaceError(f"Position type must be one of {', '.join(EMPLOYMENT_TYPES)}.")
    if fields.get("urgency") and fields["urgency"] not in URGENCY_LEVELS:
        raise JobWorkspaceError(f"Priority must be one of {', '.join(URGENCY_LEVELS)}.")
    if fields.get("job_skills_boolean_mode") is not None and fields["job_skills_boolean_mode"] not in BOOLEAN_MODES:
        raise JobWorkspaceError("Skills combine with AND (all of them) or OR (any of them).")
    work_location = fields.get("work_location")
    if work_location is not None:
        if work_location not in WORK_LOCATIONS:
            raise JobWorkspaceError(f"Work mode must be one of {', '.join(WORK_LOCATIONS)}.")
        location = fields.get("job_location", job.jobLocation) or ""
        if work_location != "REMOTE" and (not location.strip() or location.strip().lower() == "remote"):
            raise JobWorkspaceError("An onsite or hybrid job needs its location.")
    if fields.get("min_experience_years") is not None and fields["min_experience_years"] < 0:
        raise JobWorkspaceError("Experience cannot be negative.")
    if "job_skills" in fields and not [s for s in (fields["job_skills"] or "").split(",") if s.strip()]:
        raise JobWorkspaceError("List at least one skill: candidates are matched and searched by them.")


def _sync_skills(job: Jobs) -> None:
    """The structured skills the matching reads, kept in step with the skills text; what was recorded about a
    skill that stays (years, mandatory, primary) is kept."""
    known = {str(item.get("name", "")).strip().lower(): item
             for item in (job.required_skills_canonical or []) if isinstance(item, dict)}
    names, seen = [], set()
    for raw in (job.jobSkills or "").split(","):
        name = raw.strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    job.required_skills_canonical = [known.get(name.lower(), {"name": name}) for name in names]
    job.required_skills = json.dumps(names)


def apply_extras(db: Session, job: Jobs, fields: Dict, *, skills_changed: bool) -> None:
    """Write the fields the older update route does not handle. Flushes; the caller commits."""
    from app.services import job_search_service as job_search
    from app.services.boolean_search_service import BooleanQueryError

    for name in ("employment_type", "work_location", "job_skills_boolean_mode", "min_experience_years"):
        if fields.get(name) is not None:
            setattr(job, name, fields[name])
    if "urgency" in fields:
        job.urgency = fields["urgency"] or None
    mode_changed = fields.get("job_skills_boolean_mode") is not None
    if skills_changed:
        _sync_skills(job)
    db.flush()
    if skills_changed or mode_changed:
        criteria = db.get(JobSearchCriteria, job.jobID)
        if criteria is not None and criteria.edited_by is None:  # the system's version follows the job
            try:
                job_search.reset_criteria(db, job)
            except (job_search.JobSearchError, BooleanQueryError) as exc:
                logger.error(f"[JobWorkspace] {job.jobID}: search criteria not rewritten: {exc}", exc_info=True)


# ---- candidates on the job ------------------------------------------------------------------------

def _stage(pipelines: List[HiringPipeline], job_id: str, own_job: bool) -> str:
    """One stage for a candidate on this job: their open pipeline (for this job, or with no job when the
    candidate belongs to this job), else a closed one for this job, else Sourced."""
    relevant = [p for p in pipelines if p.job_id == job_id or (p.job_id is None and own_job)]
    current = next((p for p in relevant if p.closed_at is None), None)
    if current is None and relevant:
        current = max(relevant, key=lambda p: p.id)
    return STAGE_OF.get(current.stage, "Sourced") if current is not None else "Sourced"


def job_candidates(db: Session, user: Users, job: Jobs) -> Dict:
    from app.core.bu_scope import apply_bu_scope_to_candidate_query

    job_id = job.jobID
    applied = {a.candidate_id: a for a in db.query(CandidateJobApplication).filter(CandidateJobApplication.job_id == job_id).all()}
    submitted = {s.candidate_id: s for s in db.query(Submission).filter(Submission.demand_id == job_id).all()}
    matched = {m.candidate_id: m for m in db.query(JobSearchMatch).filter(JobSearchMatch.job_id == job_id).all()}
    on_pipeline = {row[0] for row in db.query(HiringPipeline.candidate_id).filter(HiringPipeline.job_id == job_id).all()}
    own = {row[0] for row in db.query(Candidate.candidateID).filter(Candidate.job_id == job_id).all()}
    ids = set(applied) | set(submitted) | set(matched) | on_pipeline | own
    empty = {"job_id": job_id, "stages": list(STAGES), "counts": {stage: 0 for stage in STAGES}, "total": 0, "candidates": []}
    if not ids:
        return empty
    base = db.query(Candidate).filter(Candidate.candidateID.in_(ids), Candidate.merged_into_id.is_(None))
    if user.tenant_id is not None:
        base = base.filter(Candidate.tenant_id == user.tenant_id)
    candidates = apply_bu_scope_to_candidate_query(db, base, user).all()
    visible = [c.candidateID for c in candidates]
    if not visible:
        return empty
    pipelines: Dict[str, List[HiringPipeline]] = {}
    for pipeline in db.query(HiringPipeline).filter(HiringPipeline.candidate_id.in_(visible)).all():
        pipelines.setdefault(pipeline.candidate_id, []).append(pipeline)
    statuses = dict(db.query(CandidateStatus.candidateID, CandidateStatus.piplineStatus)
                    .filter(CandidateStatus.candidateID.in_(visible)).all())
    recruiter_ids = {c.assigned_recruiter_id for c in candidates if c.assigned_recruiter_id}
    recruiters = dict(db.query(Users.UserID, Users.UserName).filter(Users.UserID.in_(recruiter_ids)).all()) if recruiter_ids else {}

    rows = []
    for candidate in candidates:
        cid = candidate.candidateID
        stage = _stage(pipelines.get(cid, []), job_id, cid in own)
        match, application, submission = matched.get(cid), applied.get(cid), submitted.get(cid)
        how = ("Submitted to client" if submission is not None else "Applied" if application is not None or cid in own
               else "On the hiring pipeline" if cid in on_pipeline else "Found by search")
        added = [d for d in (application.applied_at if application else None, match.created_at if match else None,
                             candidate.candidateCreatedAt if cid in own else None) if d is not None]
        rows.append({
            "candidate_id": cid,
            "name": " ".join(p for p in (candidate.candidateFirstName, candidate.candidateLastName) if p) or cid,
            "email": candidate.candidateEmail, "phone": candidate.candidateMobile, "title": candidate.candidateJobTitle,
            "location": candidate.candidateCurrentLocation,
            "experience_years": round(candidate.total_experience_months / 12, 1) if candidate.total_experience_months else None,
            "stage": stage, "status": statuses.get(cid), "how": how,
            "search_match": {"found": match.found or {}, "status": match.status, "note": match.note,
                             "contacted_at": match.contacted_at} if match is not None else None,
            "submission_status": submission.status if submission is not None else None,
            "recruiter_name": recruiters.get(candidate.assigned_recruiter_id),
            "added_at": min(added) if added else None,
        })
    order = {stage: index for index, stage in enumerate(STAGES)}
    rows.sort(key=lambda r: (order[r["stage"]], r["name"].lower(), r["candidate_id"]))
    counts = {stage: 0 for stage in STAGES}
    for row in rows:
        counts[row["stage"]] += 1
    return {"job_id": job_id, "stages": list(STAGES), "counts": counts, "total": len(rows), "candidates": rows}
