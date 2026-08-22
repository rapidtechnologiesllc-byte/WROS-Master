"""HRMS-1409 (S-380) — Outlook Integration REST Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.outlook_mail_service import send_outlook_email, schedule_calendar_meeting, get_calendar_availability

router = APIRouter(prefix="/outlook", tags=["outlook"])


@router.post("/email")
async def send_email(to_email: str, subject: str, body: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Send Outlook email."""
    return send_outlook_email(db, to_email, subject, body)


@router.post("/calendar/schedule")
async def schedule_meeting(attendees: list, subject: str, start_time: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Schedule calendar meeting."""
    return schedule_calendar_meeting(db, current_user, attendees, subject, start_time)


@router.get("/calendar/availability/{date}")
async def get_availability(date: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get calendar availability."""
    return get_calendar_availability(db, current_user, date)
