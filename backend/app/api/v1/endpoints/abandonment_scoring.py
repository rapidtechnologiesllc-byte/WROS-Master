"""
S-046/HRMS-0446 -- Candidate Abandonment Prediction
==================================================================
Prefix: /candidates
import logging
Tag:    abandonment-scoring

GET /candidates/{candidate_id}/abandonment-score
    Returns the candidate's current abandonment risk score (0-100),
    calculated synchronously on request against live data (see
    abandonment_scoring_service module docstring for the 4-component
    formula). No stored HRMS-0406 Status Card backend exists in this
    codebase -- this endpoint is the real, queryable substitute a
    future Status Card would read from.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_resource_permission
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation
from app.schemas.abandonment_scoring import AbandonmentScoreResponse
from app.services.abandonment_scoring_service import calculate_abandonment_score
from app.services.ai_conversation_service import resolve_default_tenant_id

router = APIRouter(tags=["abandonment-scoring"])


@router.get(
    "/candidates/{candidate_id}/abandonment-score",
    response_model=AbandonmentScoreResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get a candidate's abandonment risk score (S-046/HRMS-0446)",
    description=(
        "0-100 formula-based score (not ML, per spec): response rate (30%) "
        "+ sentiment trend (25%) + days since last reply (25%) + follow-up "
        "count (20%). is_flagged=true at score>=70 (BR-01)."
    ),
)
def get_abandonment_score(candidate_id: str, db: Session = Depends(get_db)):
    tenant_id = resolve_default_tenant_id(db)
    if not tenant_id:
        raise HTTPException(status_code=500, detail="No tenant available.")

    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    conversation = (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id)
        .order_by(CandidateConversation.id.desc())
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail=f"No conversation found for candidate '{candidate_id}'.")

    result = calculate_abandonment_score(db, candidate_id, conversation.tenant_id, conversation)
    return AbandonmentScoreResponse(
        candidate_id=candidate_id, abandonment_score=result["abandonment_score"],
        score_components=result["score_components"], is_flagged=result["is_flagged"], calculated_at=result["calculated_at"],
    )
