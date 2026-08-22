"""HRMS-0527 (S-371) — Curtis Rule Engine REST Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.curtis_rule_engine_service import evaluate_partner_intent, get_partner_risk_profile

router = APIRouter(prefix="/curtis-rule", tags=["curtis-rule"])


@router.post("/evaluate/{partner_id}")
async def evaluate(partner_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Evaluate partner intent."""
    return evaluate_partner_intent(db, partner_id)


@router.get("/risk-profile/{partner_id}")
async def get_risk(partner_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get partner risk profile."""
    return get_partner_risk_profile(db, partner_id)
