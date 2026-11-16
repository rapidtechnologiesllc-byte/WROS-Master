"""Boolean search over candidates, and each job's search criteria and captured candidates.

GET  /candidate-search?q=...                 candidates the caller may see who match (skills, title, resume)
GET  /jobs/{job_id}/search-criteria           the job's boolean search (written by the system when first read)
PUT  /jobs/{job_id}/search-criteria           a recruiter's own search for the job
POST /jobs/{job_id}/search-criteria/reset     back to the system's version, rewritten from the job
GET  /jobs/{job_id}/search-matches            candidates the agent captured for the job and what it did
POST /jobs/{job_id}/search-matches/run        capture and reach out now (what the hourly job does)
GET/POST/DELETE /candidate-search/saved       your saved searches (a run with saved_id records when and how many)
GET/PUT/DELETE /skill-synonyms                 the other names a skill goes by, added by the team
"""
from datetime import date, datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.data_scope import visible_job_or_404
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.services import job_search_service as job_search
from app.services import job_workspace_service as workspace
from app.services.boolean_search_service import BooleanQueryError, search_candidates

router = APIRouter(tags=["job-search"])


class SearchResult(BaseModel):
    candidate_id: str
    name: str
    title: Optional[str]
    location: Optional[str]
    experience_years: Optional[float]
    score: int
    found: Dict[str, List[str]]
    snippet: Optional[str]
    has_resume: bool


class SearchResponse(BaseModel):
    query: str
    searched: int
    total: int
    results: List[SearchResult]
    expanded: Dict[str, List[str]] = {}  # each word and every name it also found
    term_counts: Dict[str, int] = {}      # how many candidates each word finds on its own
    suggestions: List[str] = []           # how to change a search that finds nothing or too much


class SavedSearchIn(BaseModel):
    name: str
    query: str
    min_experience_years: Optional[float] = None
    location: Optional[str] = None
    model_config = ConfigDict(extra="forbid")


class SavedSearchItem(BaseModel):
    id: int
    name: str
    query: str
    min_experience_years: Optional[float] = None
    location: Optional[str] = None
    last_run_at: Optional[datetime] = None
    last_result_count: Optional[int] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class SynonymIn(BaseModel):
    skill: str
    other_names: List[str]
    model_config = ConfigDict(extra="forbid")


class SynonymItem(BaseModel):
    skill: str
    other_names: List[str]
    built_in: List[str] = []  # names the platform already knows (not editable here)
    added: List[str] = []     # names the team added
    updated_by_name: Optional[str] = None
    updated_at: Optional[datetime] = None


class MatchCounts(BaseModel):
    captured: int
    contacted: int
    skipped: int
    total: int


class CriteriaResponse(BaseModel):
    job_id: str
    query: str
    generated_query: str
    edited: bool
    edited_by_name: Optional[str]
    edited_at: Optional[datetime]
    last_run_at: Optional[datetime]
    matches: MatchCounts


class CriteriaEdit(BaseModel):
    query: str


class MatchRow(BaseModel):
    candidate_id: str
    name: str
    title: Optional[str]
    location: Optional[str]
    experience_years: Optional[float]
    score: int
    found: Dict[str, List[str]]
    snippet: Optional[str]
    status: str
    note: Optional[str]
    captured_at: Optional[datetime]
    contacted_at: Optional[datetime]


class MatchesResponse(BaseModel):
    job_id: str
    matches: List[MatchRow]


class RunResponse(BaseModel):
    captured: int
    emails_queued: int
    criteria: CriteriaResponse


@router.get("/candidate-search", response_model=SearchResponse,
            summary="Boolean search over candidates' skills, titles and resumes (AND, OR, NOT, brackets, \"phrases\")",
            dependencies=[Depends(require_resource_permission("candidates", "view"))])
def boolean_candidate_search(
    q: str = Query(..., description='e.g. guidewire AND (policycenter OR "claim center") NOT tester'),
    min_experience_years: Optional[float] = Query(default=None),
    location: Optional[str] = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50),
    saved_id: Optional[int] = Query(default=None, description="one of your saved searches: its last run is recorded"),
    db: Session = Depends(get_db),
    user: Users = Depends(get_current_internal_user),
):
    from app.services.search_library_service import record_run

    try:
        result = search_candidates(db, user, q, min_experience_years=min_experience_years, location=location,
                                   include_archived=include_archived, limit=limit)
    except BooleanQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if saved_id is not None:
        record_run(db, user, saved_id, result["total"])
    return result


@router.get("/candidate-search/saved", response_model=List[SavedSearchItem],
            dependencies=[Depends(require_resource_permission("candidates", "view"))])
def list_saved_searches(db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    from app.services.search_library_service import saved_searches

    return saved_searches(db, user)


@router.post("/candidate-search/saved", response_model=SavedSearchItem, status_code=201,
             dependencies=[Depends(require_resource_permission("candidates", "view"))])
def save_search(body: SavedSearchIn, db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    """Keep a search to run again; the same name replaces your earlier one."""
    from app.services.search_library_service import save_search as save

    try:
        return save(db, user, name=body.name, query=body.query, min_experience_years=body.min_experience_years,
                    location=body.location)
    except BooleanQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/candidate-search/saved/{saved_id}", status_code=204,
               dependencies=[Depends(require_resource_permission("candidates", "view"))])
def delete_saved_search(saved_id: int, db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    from app.services.search_library_service import delete_saved

    if not delete_saved(db, user, saved_id):
        raise HTTPException(status_code=404, detail="Saved search not found.")


@router.get("/skill-synonyms", response_model=List[SynonymItem],
            dependencies=[Depends(require_resource_permission("candidates", "view"))])
def list_skill_synonyms(db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    """Every skill with other names: the platform's and the ones your team added."""
    from app.services.search_library_service import synonym_library

    return synonym_library(db, user.tenant_id)


@router.put("/skill-synonyms", response_model=SynonymItem,
            dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def save_skill_synonym(body: SynonymIn, db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    """The names your team adds for a skill (replaces what was added before; the platform's own names stay)."""
    from app.services.search_library_service import SynonymError, save_synonym

    try:
        return save_synonym(db, user, body.skill, body.other_names)
    except SynonymError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/skill-synonyms/{skill}", status_code=204,
               dependencies=[Depends(require_resource_permission("candidates", "edit"))])
def delete_skill_synonym(skill: str, db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    from app.services.search_library_service import delete_synonym

    if not delete_synonym(db, user, skill):
        raise HTTPException(status_code=404, detail="Your team has added no names for that skill.")


def _criteria(db: Session, job) -> Dict:
    try:
        view = job_search.criteria_view(db, job)
    except job_search.JobSearchError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"{exc} Add the skills the job needs, then open this again.")
    db.commit()
    return view


@router.get("/jobs/{job_id}/search-criteria", response_model=CriteriaResponse,
            dependencies=[Depends(require_resource_permission("jobs", "view"))])
def get_search_criteria(job_id: str, db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    return _criteria(db, visible_job_or_404(db, user, job_id, f"Job '{job_id}'"))


@router.put("/jobs/{job_id}/search-criteria", response_model=CriteriaResponse,
            dependencies=[Depends(require_resource_permission("jobs", "edit"))])
def save_search_criteria(job_id: str, body: CriteriaEdit, db: Session = Depends(get_db),
                         user: Users = Depends(get_current_internal_user)):
    job = visible_job_or_404(db, user, job_id, f"Job '{job_id}'")
    try:
        job_search.save_criteria(db, job, user, body.query)
    except BooleanQueryError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except job_search.JobSearchError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    return _criteria(db, job)


@router.post("/jobs/{job_id}/search-criteria/reset", response_model=CriteriaResponse,
             dependencies=[Depends(require_resource_permission("jobs", "edit"))])
def reset_search_criteria(job_id: str, db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    job = visible_job_or_404(db, user, job_id, f"Job '{job_id}'")
    try:
        job_search.reset_criteria(db, job)
    except job_search.JobSearchError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"{exc} Add the skills the job needs first.")
    return _criteria(db, job)


@router.get("/jobs/{job_id}/search-matches", response_model=MatchesResponse,
            dependencies=[Depends(require_resource_permission("jobs", "view")),
                          Depends(require_resource_permission("candidates", "view"))])
def list_search_matches(job_id: str, db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    job = visible_job_or_404(db, user, job_id, f"Job '{job_id}'")
    return {"job_id": job.jobID, "matches": job_search.matches_view(db, job)}


@router.post("/jobs/{job_id}/search-matches/run", response_model=RunResponse,
             summary="Capture the candidates who match now and write to the best of them",
             dependencies=[Depends(require_resource_permission("jobs", "edit"))])
def run_search_now(job_id: str, db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    job = visible_job_or_404(db, user, job_id, f"Job '{job_id}'")
    if (job.jobStatus or "").lower() not in job_search.OPEN_JOB_STATUSES:
        raise HTTPException(status_code=409, detail="This job is not open, so nobody is searched for or written to.")
    try:
        captured = job_search.capture_for_job(db, job)
        db.commit()
    except (job_search.JobSearchError, BooleanQueryError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    queued = job_search.reach_out(db, job)
    return {"captured": len(captured), "emails_queued": queued, "criteria": _criteria(db, job)}


# ---------------------------------------------------------------------------
# The job workspace: one shape to read and save the job, and the candidates on it by their real stage
# ---------------------------------------------------------------------------

class WorkspaceEdit(BaseModel):
    """Only the fields being saved are sent; anything else on the job is left alone."""
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    job_skills: Optional[str] = None
    job_skills_boolean_mode: Optional[str] = None
    job_experience: Optional[str] = None
    min_experience_years: Optional[float] = None
    job_location: Optional[str] = None
    work_location: Optional[str] = None
    employment_type: Optional[str] = None
    urgency: Optional[str] = None  # "" clears
    salary_range: Optional[str] = None
    no_of_positions: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    client_id: Optional[str] = None
    contact_person: Optional[str] = None
    hiring_manager_id: Optional[str] = None
    recuriter_id: Optional[str] = None
    department_id: Optional[str] = None

    # an unknown field is a screen/API mismatch: reject it instead of silently dropping data
    model_config = ConfigDict(extra="forbid")


EXTRA_FIELDS = ("job_skills_boolean_mode", "min_experience_years", "work_location", "employment_type", "urgency")


@router.get("/jobs/{job_id}/workspace", summary="Everything the job workspace shows about the job",
            dependencies=[Depends(require_resource_permission("jobs", "view"))])
def get_job_workspace(job_id: str, db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    return workspace.job_view(db, visible_job_or_404(db, user, job_id, f"Job '{job_id}'"))


@router.put("/jobs/{job_id}/workspace", summary="Save any of the job's fields; returns the job as the screen shows it",
            dependencies=[Depends(require_resource_permission("jobs", "edit"))])
def save_job_workspace(job_id: str, body: WorkspaceEdit, db: Session = Depends(get_db),
                       user: Users = Depends(get_current_internal_user)):
    from app.api.v1.endpoints.create_job import update_job
    from app.schemas.user import JobUpdateRequest

    job = visible_job_or_404(db, user, job_id, f"Job '{job_id}'")
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="Nothing to save.")
    try:
        workspace.validate_edit(job, fields)
    except workspace.JobWorkspaceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    skills_changed = "job_skills" in fields and (fields["job_skills"] or "") != (job.jobSkills or "")
    # the older route owns its fields (client matching, project checks, emails to a new hiring manager or recruiter)
    update_job(job_id, JobUpdateRequest(**{k: v for k, v in fields.items() if k not in EXTRA_FIELDS}), db, user)
    job = visible_job_or_404(db, user, job_id, f"Job '{job_id}'")
    workspace.apply_extras(db, job, fields, skills_changed=skills_changed)
    db.commit()
    db.refresh(job)
    return workspace.job_view(db, job)


@router.get("/jobs/{job_id}/candidates", summary="Everyone on the job with the stage each is in, and a count per stage",
            dependencies=[Depends(require_resource_permission("jobs", "view")),
                          Depends(require_resource_permission("candidates", "view"))])
def list_job_candidates(job_id: str, db: Session = Depends(get_db), user: Users = Depends(get_current_internal_user)):
    return workspace.job_candidates(db, user, visible_job_or_404(db, user, job_id, f"Job '{job_id}'"))
