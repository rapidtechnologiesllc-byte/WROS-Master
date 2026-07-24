"""
S-037/HRMS-0437 -- Technical Qualification Score
S-038/HRMS-0438 -- Compensation Fit Score
==================================================================
Prefix: /candidates
Tag:    technical-scoring

GET /candidates/{candidate_id}/jobs/{job_id}/score
    Returns the candidate's technical + compensation fit score for the
    given job. Calculated synchronously on first request if not already
    cached. compensation_score/technical_score are computed
    independently (each merges into the same shared score_breakdown
    without overwriting the other's data -- see
    compensation_scoring_service's module docstring); availability_score/
    overall_score remain NULL until a later story computes them.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.technical_scoring import TechnicalScoreResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.compensation_scoring_service import calculate_compensation_score
from app.services.technical_scoring_service import CandidateNotFound, JobNotFound, calculate_technical_score

router = APIRouter(prefix="/candidates", tags=["technical-scoring"])


@router.get(
    "/{candidate_id}/jobs/{job_id}/score",
    response_model=TechnicalScoreResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="Get a candidate's technical + compensation fit score for a job (S-037/S-038)",
    description=(
        "Technical: skill-match (40%) + experience (35%) + certification "
        "(25%). Compensation: expected CTC vs job budget, 0-100 with "
        "tiers per HRMS-0438. Calculated on first request if not already "
        "cached; subsequent requests return the stored value until the "
        "candidate's skills or expected salary change again."
    ),
)
def get_technical_score(candidate_id: str, job_id: str, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    if not tenant_id:
        raise HTTPException(status_code=500, detail="No tenant available.")

    try:
        calculate_technical_score(db, candidate_id, job_id, tenant_id)
        result = calculate_compensation_score(db, candidate_id, job_id, tenant_id)
    except CandidateNotFound:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")
    except JobNotFound:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    db.commit()
    return TechnicalScoreResponse(**result)
