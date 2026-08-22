"""HRMS-0537 (S-383) — Check-In Cadence REST Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.checkin_cadence_service import configure_checkin_cadence, get_checkin_schedule, schedule_next_checkin

router = APIRouter(prefix="/checkin", tags=["checkin"])


@router.post("/configure")
async def configure(org_level: str, frequency_days: int, enabled: bool = True, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Configure check-in cadence."""
    return configure_checkin_cadence(db, org_level, frequency_days, enabled)


@router.get("/schedule/{employee_id}")
async def get_schedule(employee_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get check-in schedule."""
    return get_checkin_schedule(db, employee_id)


@router.post("/schedule/{employee_id}")
async def schedule(employee_id: str, manager_id: str, notes: str = "", db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Schedule next check-in."""
    return schedule_next_checkin(db, employee_id, manager_id, notes)
