"""
S-350/HRMS-P120 -- HR Intelligence Briefing (Candidate Desire Dashboard)
==================================================================
Prefix: /candidates
Tag:    desire-intelligence

GET  /candidates/{candidate_id}/desire-intelligence
    View: gated behind candidate.view -- per Avinash's explicit
    2026-08-05 direction, this is visible to everyone who can see the
    candidate at all (Recruiter, Resource Manager, HR, BU Head, Partner,
    Super User all feed and/or read it), NOT the spec's literal
    "HR/Director only, hidden from Recruiter" restriction.

POST /candidates/{candidate_id}/desire-intelligence/refresh
    Edit (regenerate narrative + talking points on demand): gated
    behind the new candidate.desire_intelligence.edit permission --
    Partner/BU Head/HR Manager/Super User only, same explicit
    direction. Recruiter and Resource Manager still feed the
    underlying signals through their normal candidate interactions
    (S-347's real signal-collection hooks); they just don't get this
    on-demand refresh control.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.models.candidate import Candidate
from app.models.candidate_desire_profile import CandidateDesireProfile
from app.models.motivation import MotivationOutcome
from app.schemas.desire_intelligence import (
    DesireIntelligenceResponse,
    DesireRankingItem,
    MotivationHistoryItem,
)
from app.services.ai_conversation_service import resolve_default_tenant_id
from app.services.desire_profile_service import build_and_narrate

router = APIRouter(tags=["desire-intelligence"])


def _build_response(db: Session, candidate_id: str) -> DesireIntelligenceResponse:
    profile = db.query(CandidateDesireProfile).filter(CandidateDesireProfile.candidate_id == candidate_id).first()

    history_rows = (
        db.query(MotivationOutcome)
        .filter(MotivationOutcome.candidate_id == candidate_id)
        .order_by(MotivationOutcome.sent_at.desc())
        .limit(20)
        .all()
    )
    motivation_history = [
        MotivationHistoryItem(
            id=row.id, trigger_type=row.trigger_type, desire_category_targeted=row.desire_category_targeted,
            message_preview=(row.message_sent or "")[:80], sent_at=row.sent_at,
            response_within_24h=row.response_within_24h, offer_accepted=row.offer_accepted,
        )
        for row in history_rows
    ]

    if profile is None:
        return DesireIntelligenceResponse(candidate_id=candidate_id, has_profile=False, motivation_history=motivation_history)

    return DesireIntelligenceResponse(
        candidate_id=candidate_id,
        has_profile=True,
        top_desire_category=profile.top_desire_category,
        top_desire_score=profile.top_desire_score,
        desire_ranking=[DesireRankingItem(**item) for item in (profile.desire_ranking or [])],
        primary_fear=profile.primary_fear,
        primary_fear_score=profile.primary_fear_score,
        engagement_level=profile.engagement_level,
        has_competing_offer=profile.has_competing_offer,
        decision_urgency=profile.decision_urgency,
        narrative_summary=profile.narrative_summary,
        narrative_updated_at=profile.narrative_updated_at,
        talking_points=profile.talking_points or [],
        profile_updated_at=profile.profile_updated_at,
        motivation_history=motivation_history,
    )


@router.get(
    "/candidates/{candidate_id}/desire-intelligence",
    response_model=DesireIntelligenceResponse,
    dependencies=[Depends(require_permission("candidate.view"))],
    summary="Get a candidate's Desire Intelligence profile (S-350/HRMS-P120)",
)
def get_desire_intelligence(candidate_id: str, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")
    return _build_response(db, candidate_id)


@router.post(
    "/candidates/{candidate_id}/desire-intelligence/refresh",
    response_model=DesireIntelligenceResponse,
    dependencies=[Depends(require_permission("candidate.desire_intelligence.edit"))],
    summary="Regenerate a candidate's Desire narrative + talking points on demand (S-350 Step 3)",
)
def refresh_desire_intelligence(candidate_id: str, db: Session = Depends(get_db)):
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    tenant_id = resolve_default_tenant_id(db)
    build_and_narrate(db, tenant_id, candidate_id)
    return _build_response(db, candidate_id)
