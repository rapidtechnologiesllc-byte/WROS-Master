"""
Monitoring Status Endpoints

Exposes health and status of queue monitoring system.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from app.services.stuck_message_monitor_service import get_monitor_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


@router.get("/stuck-messages")
def get_stuck_message_status() -> Dict[str, Any]:
    """
    Get current stuck message monitoring status.

    Returns:
    - running: Is monitoring active?
    - last_check: When was last check performed?
    - stuck_detected: How many stuck messages found in last cycle?
    - healed_count: How many recovered in last cycle?
    - root_causes: What caused them to get stuck?
    - cycles_completed: Total monitoring cycles run
    """
    try:
        service = get_monitor_service()
        status = service.get_current_status()
        return {
            "status": "ok",
            "data": status
        }
    except Exception as e:
        logger.error(f"[Monitoring] Failed to get stuck message status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get monitoring status")


@router.get("/stuck-messages/history")
def get_stuck_message_history() -> Dict[str, Any]:
    """
    Get stuck message monitoring history (last 10 cycles).

    Returns:
    - last_check: Latest check timestamp
    - cycles_completed: Total cycles run
    - recent_healed: Last 10 recovered messages
    - recent_failed: Last 10 messages moved to dead-letter queue
    - recent_root_causes: Last 10 root causes identified
    """
    try:
        service = get_monitor_service()
        history = service.get_history()
        return {
            "status": "ok",
            "data": history
        }
    except Exception as e:
        logger.error(f"[Monitoring] Failed to get history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get monitoring history")


@router.get("/health")
def get_monitoring_health() -> Dict[str, Any]:
    """
    Get monitoring service health (is it running?).

    Returns:
    - running: Is monitoring active?
    - cycles_completed: Total cycles run (should be increasing)
    - last_check: When was the last check?
    """
    try:
        service = get_monitor_service()
        status = service.get_current_status()

        return {
            "status": "healthy" if status["running"] else "stopped",
            "running": status["running"],
            "cycles_completed": status["cycles_completed"],
            "last_check": status["last_check"]
        }
    except Exception as e:
        logger.error(f"[Monitoring] Health check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e)
        }
