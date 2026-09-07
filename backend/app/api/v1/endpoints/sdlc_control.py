"""SDLC Control Endpoints

On-demand autonomous SDLC cycle execution.
Allows manual triggering of audit → develop → test → fix → deploy cycle.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import require_resource_permission, get_db
from app.services.autonomous_sdlc_service import (
    run_autonomous_sdlc_cycle,
    AutonomousSDLCError,
)

router = APIRouter(prefix="/sdlc", tags=["sdlc"])
logger = logging.getLogger(__name__)


@router.post(
    "/run-cycle",
    dependencies=[Depends(require_resource_permission("system", "manage"))],
)
def trigger_sdlc_cycle(db: Session = Depends(get_db)):
    """
    Manually trigger autonomous SDLC cycle.

    Runs: audit → develop → test → fix → deploy

    Returns:
        {
            "status": "success|no_changes|error",
            "phase": "audit|develop|test|fix|deploy",
            "issues_found": int,
            "issues_fixed": int,
            "tests_passed": int,
            "changes_deployed": bool,
            "timestamp": str
        }
    """
    try:
        logger.info("[SDLC Control] User triggered autonomous SDLC cycle")
        result = run_autonomous_sdlc_cycle()

        if result.get("status") == "error":
            logger.error(f"[SDLC Control] Cycle failed: {result}")
            raise HTTPException(
                status_code=500,
                detail=f"SDLC cycle failed at {result.get('phase')} phase: {result.get('error')}"
            )

        logger.info(f"[SDLC Control] Cycle completed: {result}")
        return result

    except AutonomousSDLCError as e:
        logger.error(f"[SDLC Control] SDLC error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SDLC Control] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/status",
    dependencies=[Depends(require_resource_permission("system", "view"))],
)
def get_sdlc_status(db: Session = Depends(get_db)):
    """
    Get current SDLC cycle status and health metrics.

    Returns:
        {
            "scheduler_running": bool,
            "next_cycle": str (ISO 8601),
            "last_cycle": {
                "timestamp": str,
                "status": str,
                "issues_found": int,
                "issues_fixed": int
            },
            "queues": {
                "pending_messages": int,
                "workers_active": int
            }
        }
    """
    try:
        from app.core.scheduler import scheduler
        from sqlalchemy import text

        # Get scheduler status
        scheduler_running = scheduler.running if hasattr(scheduler, "running") else False

        # Get queue status
        db_result = db.execute(text(
            "SELECT COUNT(*) FROM app_schema.message_queue WHERE status='pending'"
        ))
        pending_messages = db_result.scalar() or 0

        return {
            "scheduler_running": scheduler_running,
            "last_cycle_status": "Not tracked yet",
            "queues": {
                "pending_messages": pending_messages,
                "workers_active": 0,  # Would need Celery inspect for exact count
            },
            "next_cycle_in_seconds": 90,  # Default 90-second interval
        }

    except Exception as e:
        logger.error(f"[SDLC Control] Status check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/audit",
    dependencies=[Depends(require_resource_permission("system", "view"))],
)
def run_audit_only(db: Session = Depends(get_db)):
    """
    Run AUDIT phase only (no fixes or deployment).

    Checks:
    - Database connection
    - Redis broker
    - Message queue status
    - API endpoints

    Returns audit findings without applying fixes.
    """
    try:
        from app.services.autonomous_sdlc_service import _audit_system_health

        logger.info("[SDLC Control] User triggered audit phase only")
        result = _audit_system_health()

        return {
            "phase": "audit",
            "timestamp": result.get("timestamp"),
            "issues_found": len(result.get("issues", [])),
            "issues": result.get("issues", []),
            "critical_issues": result.get("critical_issues", 0),
        }

    except Exception as e:
        logger.error(f"[SDLC Control] Audit failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/test",
    dependencies=[Depends(require_resource_permission("system", "view"))],
)
def run_tests_only(db: Session = Depends(get_db)):
    """
    Run TEST phase only (no fixes or deployment).

    Tests:
    - API health endpoint
    - Queue configuration
    - Database connection

    Returns test results.
    """
    try:
        from app.services.autonomous_sdlc_service import _run_verification_tests

        logger.info("[SDLC Control] User triggered test phase only")
        result = _run_verification_tests()

        return {
            "phase": "test",
            "all_tests_passed": result.get("all_tests_passed"),
            "passed": result.get("passed"),
            "failed": result.get("failed"),
            "endpoints_tested": result.get("endpoints_tested"),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"[SDLC Control] Test failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


from datetime import datetime
