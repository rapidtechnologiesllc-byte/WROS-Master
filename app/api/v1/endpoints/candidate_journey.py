"""
S-059/HRMS-0459 -- Candidate Journey Dashboard
==================================================================
Prefix: /candidates
Tag:    candidate-journey

GET /candidates/{candidate_id}/journey
    Auth: gated behind the existing candidate.view permission -- this
    is standard candidate-profile visibility, the same gate every
    other candidate-detail read in this codebase already uses; no new
    permission needed (contrast with S-053's offer.readiness_check,
    which existed because of a real, specific RBAC gap this story
    doesn't have).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.schemas.candidate_journey import CandidateJourneyResponse
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.candidate_journey_service import CandidateNotFound, get_candidate_journey

router = APIRouter(tags=["candidate-journey"])


@router.get(
    "/candidates/{candidate_id}/journey",
    response_model=CandidateJourneyResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="Get a candidate's 7-stage pipeline journey (S-059/HRMS-0459)",
    description=(
        "Derives Engaged/Qualifying/Screened/Interview/Offer/Preboarding/Joined "
        "stage status from real, already-built artifacts (conversation, scores, "
        "interviews, offer, joining readiness, employee conversion) -- this "
        "codebase has no literal state-history table or 10-value pipeline enum."
    ),
)
def get_journey(candidate_id: str, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    try:
        return get_candidate_journey(db, candidate_id, tenant_id)
    except CandidateNotFound:
        raise HTTPException(status_code=404, detail=f"Candidate {candidate_id!r} not found.")
