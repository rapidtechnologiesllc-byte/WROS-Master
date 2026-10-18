"""System health monitoring endpoint (integrates Doctor + Healer + Architect)"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
import logging

from app.core.dependencies import require_resource_permission
from app.services.integrated_architecture_system import get_integrated_system

router = APIRouter(
    prefix="/system",
    tags=["system-health"],
)

logger = logging.getLogger(__name__)


@router.get(
    "/health",
    dependencies=[Depends(require_resource_permission("system-health", "view"))],
)
async def get_system_health() -> Dict[str, Any]:
    """
    Get complete system health status
    Includes: Doctor findings + Healer actions + Architect specs
    
    This is read-only - no manual intervention needed.
    All recovery is automatic via the Integrated Architecture System.
    """
    try:
        orchestrator = get_integrated_system()
        status = orchestrator.get_system_status()
        
        return {
            "status": "healthy" if status["critical_issues"] == 0 else "degraded",
            "cycle": status["cycle"],
            "components": {
                "doctor": {
                    "description": "Real-time health monitoring",
                    "issues_detected": status["doctor_issues"],
                    "critical_issues": status["critical_issues"],
                    "last_diagnosis": status["last_diagnosis"]
                },
                "healer": {
                    "description": "Automatic recovery system",
                    "recent_recoveries": status["recent_recoveries"],
                    "status": "active" if status["recent_recoveries"] >= 0 else "inactive"
                },
                "architect": {
                    "description": "Prevention and code fix recommendations",
                    "cycle": status["cycle"],
                    "status": "analyzing" if status["running"] else "idle"
                }
            },
            "system": {
                "running": status["running"],
                "cycle_number": status["cycle"],
                "last_check": status["last_diagnosis"]
            },
            "note": "All issues are being monitored and recovered automatically. No manual action required."
        }
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))
