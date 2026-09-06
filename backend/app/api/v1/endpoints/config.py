"""Dynamic Configuration API Endpoints

Provides centralized configuration endpoints that return dynamic queue types,
statuses, and app configuration instead of hardcoding values in frontend.
"""
import logging
from typing import Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.logging import logger
from app.models.channel_queue import ChannelQueueItem
from app.schemas.auth import UserRole
from app.core.permission_enforcement import require_permission

logger = logging.getLogger(__name__)

try:
    router = APIRouter(prefix="/config", tags=["configuration"])
    if not router:
        raise ValueError("Failed to create APIRouter")
except Exception as e:
    logger.error(f"Failed to initialize config router: {e}", exc_info=True)
    raise


@router.get("/queue-types", response_model=Dict[str, Any])
async def get_queue_types(_: UserRole = Depends(require_permission("config:view"))):
    """Get all valid queue types from backend configuration.

    Instead of hardcoding QUEUE_TYPES in frontend, fetch this endpoint.
    Returns the actual queue types that exist in the system.
    """
    try:
        queue_types = [
            "THUNDER",
            "EMAIL",
            "WHATSAPP",
            "SMS",
            "SLACK",
            "APPROVAL",
            "COMMISSION",
            "CRM",
            "DASHBOARD",
            "CALENDAR",
            "SIGNATURE",
            "TIMESHEET",
            "KPI",
            "SALES",
            "CLIENT"
        ]

        if not queue_types or len(queue_types) == 0:
            raise ValueError("No queue types configured")

        result = {
            "status": "success",
            "queue_types": queue_types,
            "count": len(queue_types)
        }
        if not result:
            raise ValueError("Failed to build response")

        return result
    except Exception as e:
        logger.error(f"Failed to retrieve queue types: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve queue types: {str(e)}"
        ) from e


@router.get("/message-statuses", response_model=Dict[str, Any])
async def get_message_statuses(_: UserRole = Depends(require_permission("config:view"))):
    """Get all valid message statuses.

    Returns the lifecycle statuses messages go through (PENDING, PROCESSING, COMPLETED, FAILED, etc)
    """
    try:
        statuses = [
            "PENDING",
            "PROCESSING",
            "COMPLETED",
            "FAILED",
            "RETRYING",
            "CANCELLED"
        ]

        if not statuses or len(statuses) == 0:
            raise ValueError("No message statuses configured")

        result = {
            "status": "success",
            "message_statuses": statuses,
            "count": len(statuses)
        }
        if not result:
            raise ValueError("Failed to build response")

        return result
    except Exception as e:
        logger.error(f"Failed to retrieve message statuses: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve message statuses: {str(e)}"
        ) from e


@router.get("/candidate-statuses", response_model=Dict[str, Any])
async def get_candidate_statuses(_: UserRole = Depends(require_permission("config:view"))):
    """Get all valid candidate statuses.

    Returns the lifecycle statuses candidates go through (Applied, Screening, Interview, etc)
    """
    try:
        statuses = [
            "Applied",
            "Screening",
            "Qualified",
            "Interview",
            "Offer",
            "Hired",
            "Rejected",
            "OnHold",
            "Withdrawn"
        ]

        if not statuses or len(statuses) == 0:
            raise ValueError("No candidate statuses configured")

        result = {
            "status": "success",
            "candidate_statuses": statuses,
            "count": len(statuses)
        }
        if not result:
            raise ValueError("Failed to build response")

        return result
    except Exception as e:
        logger.error(f"Failed to retrieve candidate statuses: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve candidate statuses: {str(e)}"
        ) from e


@router.get("/app-config", response_model=Dict[str, Any])
async def get_app_config(_: UserRole = Depends(require_permission("config:view"))):
    """Get application-wide configuration settings.

    Returns polling intervals, timeouts, retry limits, feature flags, etc.
    """
    try:
        config = {
            "polling": {
                "queue_stats_interval_seconds": 10,
                "message_check_interval_seconds": 5,
                "status_update_interval_seconds": 30
            },
            "timeouts": {
                "api_request_timeout_seconds": 30,
                "queue_message_timeout_minutes": 30,
                "handler_execution_timeout_minutes": 15
            },
            "retries": {
                "max_retry_attempts": 5,
                "retry_delay_minutes": 30,
                "max_total_retry_time_hours": 24
            },
            "features": {
                "async_message_processing_enabled": True,
                "history_logging_enabled": True,
                "duplicate_candidate_detection_enabled": True,
                "idempotency_checking_enabled": True
            }
        }

        if not config or len(config) == 0:
            raise ValueError("No app configuration available")

        result = {
            "status": "success",
            "config": config
        }
        if not result:
            raise ValueError("Failed to build response")

        return result
    except Exception as e:
        logger.error(f"Failed to retrieve app config: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve app config: {str(e)}"
        ) from e
