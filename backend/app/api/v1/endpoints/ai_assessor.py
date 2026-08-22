"""HRMS-0518 (S-357) — AI Assessment REST Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.ai_assessor_service import assess_core_eligibility, get_assessment_report

router = APIRouter(prefix="/ai-assessor", tags=["ai-assessor"])


@router.post("/assess/{employee_id}")
async def assess(employee_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """AI assessment of employee core eligibility."""
    return assess_core_eligibility(db, employee_id, {})


@router.get("/report/{employee_id}")
async def get_report(employee_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get AI assessment report."""
    return get_assessment_report(db, employee_id)
