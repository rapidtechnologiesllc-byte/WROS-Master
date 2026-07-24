"""
S-037/HRMS-0437 -- Technical Qualification Score
==================================================================
Prefix: /candidates
Tag:    technical-scoring

GET /candidates/{candidate_id}/jobs/{job_id}/score
    Returns the candidate's technical fit score for the given job.
    Calculated synchronously on first request if not already cached.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.technical_scoring import TechnicalScoreResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.technical_scoring_service import CandidateNotFound, JobNotFound, calculate_technical_score

router = APIRouter(prefix="/candidates", tags=["technical-scoring"])


@router.get(
    "/{candidate_id}/jobs/{job_id}/score",
    response_model=TechnicalScoreResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="Get a candidate's technical fit score for a job (S-037/HRMS-0437)",
    description=(
        "Skill-match (40%) + experience (35%) + certification (25%) "
        "formula, 0-100. Calculated on first request if not already "
        "cached; subsequent requests return the stored value until the "
        "candidate's skills change again."
    ),
)
def get_technical_score(candidate_id: str, job_id: str, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    if not tenant_id:
        raise HTTPException(status_code=500, detail="No tenant available.")

    try:
        result = calculate_technical_score(db, candidate_id, job_id, tenant_id)
    except CandidateNotFound:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")
    except JobNotFound:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    db.commit()
    return TechnicalScoreResponse(**result)
