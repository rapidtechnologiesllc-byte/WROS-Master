"""HRMS-1401 (S-379) — M365 SSO REST Endpoints"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.m365_sso_service import initiate_m365_sso, validate_m365_token, get_m365_user_profile

router = APIRouter(prefix="/m365", tags=["m365"])


@router.post("/auth/initiate")
async def initiate_auth(user_email: str, db: Session = Depends(get_db)):
    """Initiate M365 SSO."""
    return initiate_m365_sso(db, user_email)


@router.post("/auth/validate")
async def validate_token(token: str, db: Session = Depends(get_db)):
    """Validate M365 token."""
    return validate_m365_token(db, token)


@router.get("/profile/{m365_user_id}")
async def get_profile(m365_user_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get M365 user profile."""
    return get_m365_user_profile(db, m365_user_id)
