"""
S-037/HRMS-0437 -- Technical Qualification Score
S-038/HRMS-0438 -- Compensation Fit Score
S-039/HRMS-0439 -- Availability Score
S-040/HRMS-0440 -- Overall Candidate Score & Ranking
==================================================================
Prefix: /candidates, /jobs
import logging
Tag:    technical-scoring

GET /candidates/{candidate_id}/jobs/{job_id}/score
    Returns the candidate's technical + compensation + availability +
    overall fit score for the given job. Calculated synchronously on
    first request if not already cached. All four are computed
    independently and each merges its own keys into the same shared
    score_breakdown without overwriting the others' data (see
    compensation_scoring_service's module docstring for the merge
    pattern, and technical_scoring_service's for the bug it fixes).

GET /jobs/{job_id}/candidates/ranked
    Real candidates ranked by overall_score DESC for this job
    (HRMS-0440 Step 2/3). BR-03: rank is computed on read, never stored.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.models.user import Jobs
from app.schemas.technical_scoring import RankedCandidatesResponse, TechnicalScoreResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.availability_scoring_service import calculate_availability_score
from app.services.compensation_scoring_service import calculate_compensation_score
from app.services.overall_scoring_service import calculate_overall_score, get_ranked_candidates
from app.services.technical_scoring_service import CandidateNotFound, JobNotFound, calculate_technical_score

router = APIRouter(tags=["technical-scoring"])


@router.get(
    "/candidates/{candidate_id}/jobs/{job_id}/score",
    response_model=TechnicalScoreResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get a candidate's full fit score for a job (S-037/S-038/S-039/S-040)",
    description=(
        "Technical: skill-match (40%) + experience (35%) + certification "
        "(25%). Compensation: expected CTC vs job budget, 0-100 with "
        "tiers per HRMS-0438. Availability: notice period vs job urgency "
        "or start date, 0-100 per HRMS-0439. Overall: technical (40%) + "
        "compensation (30%) + availability (20%) + resume completeness "
        "(10%) per HRMS-0440 -- BA-approved weights, code constants. "
        "Calculated on first request if not already cached; subsequent "
        "requests return the stored value until the underlying "
        "candidate/job data changes again."
    ),
)
def get_technical_score(candidate_id: str, job_id: str, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    if not tenant_id:
        raise HTTPException(status_code=500, detail="No tenant available.")

    try:
        calculate_technical_score(db, candidate_id, job_id, tenant_id)
        calculate_compensation_score(db, candidate_id, job_id, tenant_id)
        calculate_availability_score(db, candidate_id, job_id, tenant_id)
        result = calculate_overall_score(db, candidate_id, job_id, tenant_id)
    except CandidateNotFound:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")
    except JobNotFound:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    db.commit()
    return TechnicalScoreResponse(**result)


@router.get(
    "/jobs/{job_id}/candidates/ranked",
    response_model=RankedCandidatesResponse,
    dependencies=[Depends(require_resource_permission("jobs", "view"))],
    summary="Get candidates ranked by overall fit score for a job (S-040/HRMS-0440)",
    description=(
        "BR-02: ranking only, never auto-rejects or blocks submission. "
        "BR-03: rank is computed dynamically on every read (ORDER BY "
        "overall_score DESC), never stored as a column."
    ),
)
def get_ranked_candidates_for_job(job_id: str, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    if not tenant_id:
        raise HTTPException(status_code=500, detail="No tenant available.")

    job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    candidates = get_ranked_candidates(db, job_id, tenant_id)
    return RankedCandidatesResponse(job_id=job_id, job_title=job.jobTitle, candidates=candidates, total_count=len(candidates))
