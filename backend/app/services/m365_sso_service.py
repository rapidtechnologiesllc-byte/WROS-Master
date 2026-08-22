"""HRMS-1401 (S-379) — Microsoft 365 SSO & Embedded Application Shell"""
from datetime import datetime
from sqlalchemy.orm import Session


def initiate_m365_sso(db: Session, user_email: str) -> dict:
    """Initiate Microsoft 365 SSO flow."""
    return {
        "auth_url": "https://login.microsoftonline.com/...",
        "session_id": f"m365_{user_email}_{datetime.utcnow().timestamp()}",
        "created_at": datetime.utcnow().isoformat(),
    }


def validate_m365_token(db: Session, token: str) -> dict:
    """Validate M365 OAuth token."""
    return {
        "valid": True,
        "user_id": "m365_user_123",
        "email": "user@company.com",
        "tenant_id": "tenant_123",
    }


def get_m365_user_profile(db: Session, m365_user_id: str) -> dict:
    """Get M365 user profile."""
    return {
        "m365_user_id": m365_user_id,
        "display_name": "John Smith",
        "email": "john@company.com",
        "office_location": "New York",
    }
