"""HRMS-0534 (S-378) — Specialty Release Approval REST Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.specialty_release_service import request_specialty_release, approve_release, get_release_status

router = APIRouter(prefix="/specialty-release", tags=["specialty-release"])


@router.post("/request")
async def request_release(employee_id: str, client_id: str, reason: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Request specialty release."""
    return request_specialty_release(db, employee_id, client_id, reason)


@router.patch("/{release_id}/approve")
async def approve(release_id: str, notes: str = "", db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Approve release."""
    return approve_release(db, release_id, current_user, notes)


@router.get("/{release_id}")
async def get_status(release_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get release status."""
    return get_release_status(db, release_id)
