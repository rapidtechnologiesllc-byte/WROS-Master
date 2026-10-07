"""
SLM Export API Endpoints

These endpoints are queried by:
- P&L agents (Revenue, Cost, Margin, Budget, Bonus)
- Recruitment agents (Sourcing, Screening, Interview)
- Workforce agents (Allocation, Utilization, Skill Gap)
- FLASH orchestrator

Latency SLA: <5 min (loose coupling, daily batch OK)
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, date as date_type
import logging

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services.slm_export_service import SLMExportService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/slm/export",
    tags=["SLM Export"],
    dependencies=[Depends(get_db)]
)



@router.get("/health")
def slm_export_health(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Health check for SLM export service."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "SLM Export",
        "last_export": datetime.utcnow().isoformat() + "Z"
    }
