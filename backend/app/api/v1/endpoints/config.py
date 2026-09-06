"""Dynamic Configuration API Endpoints

Provides centralized configuration endpoints that return dynamic queue types,
statuses, and app configuration instead of hardcoding values in frontend.

IMPORTANT: These endpoints are PUBLIC - they are intentionally accessible without
authentication to allow frontend to load configuration data before login.
They are listed in auth_middleware.py PUBLIC_ROUTES and main.py known_exceptions.
"""
import logging
from typing import Dict, List, Any

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.core.database import get_db
from app.models.channel_queue import ChannelQueueItem

logger = logging.getLogger(__name__)

try:
    router = APIRouter(prefix="/config", tags=["configuration"])
    if not router:
        raise ValueError("Failed to create APIRouter")
except Exception as e:
    logger.error(f"Failed to initialize config router: {e}", exc_info=True)
    raise


@router.get("/queue-types", response_model=Dict[str, Any])
async def get_queue_types(db: Session = Depends(get_db)):
    """Get all valid queue types from backend configuration.

    Instead of hardcoding QUEUE_TYPES in frontend, fetch this endpoint.
    Returns the actual queue types that exist in the system.

    NOTE: This is a PUBLIC endpoint - no authentication required.
    Intentionally accessible without auth to allow frontend initialization before login.
    Listed in auth_middleware.py PUBLIC_ROUTES and main.py known_exceptions.
    """
    try:
        # Query distinct queue types from ChannelQueueItem model
        queue_items = db.query(ChannelQueueItem.queue_type).distinct().all()
        queue_types = sorted([item[0] for item in queue_items if item[0]])

        if not queue_types:
            logger.warning("No queue types found in database, returning empty list")

        result = {
            "status": "success",
            "queue_types": queue_types,
            "count": len(queue_types)
        }

        return result
    except Exception as e:
        logger.error(f"Failed to retrieve queue types: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve queue types: {str(e)}"
        ) from e


@router.get("/message-statuses", response_model=Dict[str, Any])
async def get_message_statuses():
    """Get all valid message statuses.

    Returns the lifecycle statuses messages go through (PENDING, PROCESSING, COMPLETED, FAILED, etc)

    NOTE: This is a PUBLIC endpoint - no authentication required.
    Intentionally accessible without auth to allow frontend initialization before login.
    Listed in auth_middleware.py PUBLIC_ROUTES and main.py known_exceptions.
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
async def get_candidate_statuses():
    """Get all valid candidate statuses.

    Returns the lifecycle statuses candidates go through (Applied, Screening, Interview, etc)

    NOTE: This is a PUBLIC endpoint - no authentication required.
    Intentionally accessible without auth to allow frontend initialization before login.
    Listed in auth_middleware.py PUBLIC_ROUTES and main.py known_exceptions.
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
async def get_app_config():
    """Get application-wide configuration settings.

    Returns polling intervals, timeouts, retry limits, feature flags, etc.

    NOTE: This is a PUBLIC endpoint - no authentication required.
    Intentionally accessible without auth to allow frontend initialization before login.
    Listed in auth_middleware.py PUBLIC_ROUTES and main.py known_exceptions.
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
