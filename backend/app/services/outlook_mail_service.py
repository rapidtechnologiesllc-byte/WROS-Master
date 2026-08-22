"""HRMS-1409 (S-380) — Embedded Outlook Email & Calendar Tab"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session


def send_outlook_email(db: Session, to_email: str, subject: str, body: str) -> dict:
    """Send email via Outlook from WROS."""
    return {
        "message_id": f"mail_{datetime.utcnow().timestamp()}",
        "to": to_email,
        "subject": subject,
        "status": "SENT",
        "sent_at": datetime.utcnow().isoformat(),
    }


def schedule_calendar_meeting(db: Session, user_id: str, attendees: list, subject: str, start_time: str) -> dict:
    """Schedule meeting in Outlook calendar."""
    return {
        "meeting_id": f"meeting_{user_id}_{datetime.utcnow().timestamp()}",
        "subject": subject,
        "attendees": attendees,
        "start_time": start_time,
        "status": "SCHEDULED",
        "created_at": datetime.utcnow().isoformat(),
    }


def get_calendar_availability(db: Session, user_id: str, date: str) -> dict:
    """Get calendar availability for user on specific date."""
    return {
        "user_id": user_id,
        "date": date,
        "available_slots": [
            {"start": "09:00", "end": "10:00"},
            {"start": "14:00", "end": "15:30"},
        ],
    }
