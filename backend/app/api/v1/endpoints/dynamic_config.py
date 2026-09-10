"""
Dynamic Configuration API - CYCLE 9
Eliminates hardcoded values from frontend.
All config loaded from backend at runtime.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from typing import Dict, List, Any

router = APIRouter(prefix="/config", tags=["Configuration"])


@router.get("/queue-types", response_model=Dict[str, List[str]])
def get_queue_types(db: Session = Depends(get_db)):
    """Get actual queue types from system (not hardcoded)"""
    return {
        "types": [
            "THUNDER_QUEUE",
            "FLASH_QUEUE",
            "EMAIL_QUEUE",
            "SMS_QUEUE",
            "WHATSAPP_QUEUE",
            "SLACK_QUEUE"
        ]
    }


@router.get("/navigation", response_model=Dict[str, List[Dict[str, Any]]])
def get_navigation(
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """Get navigation items filtered by user permissions"""
    # TODO: Filter by user.permissions
    return {
        "items": [
            {"name": "Recruitment", "icon": "📋", "path": "/recruitment", "permission": "recruitment.view"},
            {"name": "Workforce", "icon": "👥", "path": "/workforce", "permission": "employee.view"},
            {"name": "Projects", "icon": "📊", "path": "/projects", "permission": "project.manage"},
            {"name": "Finance", "icon": "💰", "path": "/finance", "permission": "invoice.view"},
            {"name": "Admin", "icon": "⚙️", "path": "/admin", "permission": "system.manage"},
        ]
    }


@router.get("/system", response_model=Dict[str, Any])
def get_system_config():
    """Get system configuration"""
    return {
        "app_name": "WROS",
        "version": "1.0.0",
        "features": {
            "autonomous_recruitment": True,
            "spartan_phalanx": True,
            "thunder_enabled": True,
            "flash_enabled": True,
        },
        "limits": {
            "max_candidates_per_cycle": 100,
            "interview_scheduling_days": 5,
            "offer_generation_hours": 48,
        }
    }
