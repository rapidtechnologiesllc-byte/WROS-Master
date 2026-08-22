"""HRMS-1410 (S-381) — Teams Chat REST Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.teams_chat_service import send_teams_message, get_teams_notifications, create_teams_channel

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("/message")
async def send_message(message: str, channel: str = "general", db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Send Teams message."""
    return send_teams_message(db, current_user, message, channel)


@router.get("/notifications")
async def get_notifications(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get Teams notifications."""
    return get_teams_notifications(db, current_user)


@router.post("/channel")
async def create_channel(channel_name: str, members: list, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Create Teams channel."""
    return create_teams_channel(db, channel_name, members)
