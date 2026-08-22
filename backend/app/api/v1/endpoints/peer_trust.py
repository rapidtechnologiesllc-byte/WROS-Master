"""HRMS-0520 (S-368) — Peer Trust Pulse REST Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.peer_trust_pulse_service import create_peer_survey, submit_peer_response, get_pulse_results

router = APIRouter(prefix="/peer-trust", tags=["peer-trust"])


@router.post("/survey/{employee_id}/{week}")
async def create_survey(employee_id: str, week: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Create peer trust pulse survey."""
    return create_peer_survey(db, employee_id, week)


@router.post("/survey/{survey_id}/respond")
async def respond(survey_id: str, responses: dict, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Submit peer response."""
    return submit_peer_response(db, survey_id, current_user, responses)


@router.get("/results/{employee_id}/{week}")
async def get_results(employee_id: str, week: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get peer trust results."""
    return get_pulse_results(db, employee_id, week)
