"""HRMS-0531 (S-375) — Employee Scorecard REST Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.employee_scorecard_service import calculate_employee_scorecard, get_scorecard_trend

router = APIRouter(prefix="/scorecard", tags=["scorecard"])


@router.get("/{employee_id}")
async def get_scorecard(employee_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get employee scorecard."""
    return calculate_employee_scorecard(db, employee_id)


@router.get("/{employee_id}/trend")
async def get_trend(employee_id: str, days: int = 90, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get scorecard trend."""
    return get_scorecard_trend(db, employee_id, days)
