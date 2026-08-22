"""HRMS-0513 (S-352) — Core Eligibility Gate REST Endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.core_eligibility_service import (
    initiate_core_eligibility_review,
    submit_rm_recommendation,
    submit_bu_head_decision,
    get_core_eligibility_review,
)

router = APIRouter(prefix="/core-eligibility", tags=["core-eligibility"])


@router.post("/initiate")
async def initiate_review(employee_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Initiate core eligibility review for employee."""
    return initiate_core_eligibility_review(db, employee_id, current_user)


@router.patch("/{review_id}/rm-recommend")
async def recommend(review_id: str, recommendation: str, notes: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """RM submits recommendation."""
    return submit_rm_recommendation(db, review_id, recommendation, notes)


@router.patch("/{review_id}/bu-decide")
async def decide(review_id: str, decision: str, notes: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """BU Head makes final decision."""
    return submit_bu_head_decision(db, review_id, decision, notes)


@router.get("/{review_id}")
async def get_review(review_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get core eligibility review."""
    return get_core_eligibility_review(db, review_id)
