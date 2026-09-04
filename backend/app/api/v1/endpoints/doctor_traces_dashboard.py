"""Doctor Agent Escalations Dashboard Endpoints

Provides API for monitoring doctor agent traces, escalations, and WROS ticket status.
Frontend SystemHealthDashboard calls these endpoints to display doctor agent activity.
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger

router = APIRouter(prefix="/admin/doctor", tags=["doctor-dashboard"])

@router.get(
    "/traces",
    dependencies=[Depends(require_resource_permission("trace", "view"))]
)
def get_doctor_traces(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get all doctor agent traces for dashboard display.

    Returns doctor traces showing:
    - message_id: Original message that failed
    - attempt_number: Which attempt number (1-5)
    - strategy: Fix strategy attempted (ALTERNATIVE_CONTACT, DATA_CORRECTION, SERVICE_RETRY, ESCALATE_TO_WROS)
    - assigned_to_user: Who the escalation is assigned to (for WROS tickets)
    - status: ACTIVE, RESOLVED, PENDING
    - wros_ticket_id: Link to WROS ticket if created
    - created_at: When trace was created

    Returns:
        {
            "data": {
                "traces": [
                    {
                        "id": "trace-uuid",
                        "message_id": "message-uuid",
                        "attempt_number": 1,
                        "strategy": "ALTERNATIVE_CONTACT",
                        "success": false,
                        "status": "ACTIVE",
                        "assigned_to_user": {"id": "user-id", "name": "Support Team"},
                        "wros_ticket_id": "WROS-12345",
                        "created_at": "2026-08-27T10:00:00"
                    },
                    ...
                ]
            }
        }

    Raises:
        HTTPException: If query fails
    """
    try:
        from app.models.doctor_trace import DoctorTrace

        # Fetch all traces, ordered by created_at DESC (most recent first)
        traces = (
            db.query(DoctorTrace)
            .order_by(DoctorTrace.created_at.desc())
            .limit(500)
            .all()
        )

        trace_list = [
            {
                "id": str(t.id),
                "message_id": str(t.message_id),
                "attempt_number": t.attempt_number,
                "strategy": t.strategy,
                "success": t.success,
                "status": "RESOLVED" if t.success else ("ACTIVE" if t.attempt_number < 3 else "PENDING"),
                "assigned_to_user": {
                    "id": str(t.assigned_to_user_id) if t.assigned_to_user_id else None,
                    "name": t.assigned_to_user.UserName if t.assigned_to_user else "Unassigned"
                } if hasattr(t, 'assigned_to_user') else None,
                "wros_ticket_id": t.wros_ticket_id,
                "error": t.error,
                "fix_applied": t.fix_applied,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in traces
        ]

        return {"data": {"traces": trace_list}}

    except Exception as e:
        logger.error(f"Failed to get doctor traces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get doctor traces: {str(e)}")

@router.get(
    "/traces/by-status/{status}",
    dependencies=[Depends(require_resource_permission("trace", "view"))]
)
def get_doctor_traces_by_status(
    status: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get doctor traces filtered by status (ACTIVE, RESOLVED, PENDING).

    Args:
        status: Filter by status (ACTIVE, RESOLVED, PENDING)

    Returns:
        Same format as get_doctor_traces
    """
    try:

        # Map status to query filter
        status_filter = None
        if status.upper() == "ACTIVE":
            status_filter = (DoctorTrace.success == False) & (DoctorTrace.attempt_number < 3)
        elif status.upper() == "RESOLVED":
            status_filter = DoctorTrace.success == True
        elif status.upper() == "PENDING":
            status_filter = (DoctorTrace.success == False) & (DoctorTrace.attempt_number >= 3)

        if not status_filter:
            raise HTTPException(status_code=400, detail="Invalid status filter")

        traces = (
            db.query(DoctorTrace)
            .filter(status_filter)
            .order_by(DoctorTrace.created_at.desc())
            .limit(500)
            .all()
        )

        trace_list = [
            {
                "id": str(t.id),
                "message_id": str(t.message_id),
                "attempt_number": t.attempt_number,
                "strategy": t.strategy,
                "success": t.success,
                "status": "RESOLVED" if t.success else ("ACTIVE" if t.attempt_number < 3 else "PENDING"),
                "assigned_to_user": {
                    "id": str(t.assigned_to_user_id) if t.assigned_to_user_id else None,
                    "name": t.assigned_to_user.UserName if t.assigned_to_user else "Unassigned"
                } if hasattr(t, 'assigned_to_user') else None,
                "wros_ticket_id": t.wros_ticket_id,
                "error": t.error,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in traces
        ]

        return {"data": {"traces": trace_list}}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to filter doctor traces: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to filter doctor traces: {str(e)}")

@router.post(
    "/traces/{trace_id}/assign",
    dependencies=[Depends(require_resource_permission("trace", "create"))]
)
def assign_escalation(
    trace_id: str,
    assigned_to_user_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Assign a doctor escalation to a support team member.

    Args:
        trace_id: ID of the trace to assign
        assigned_to_user_id: User ID to assign to

    Returns:
        {"status": "success", "message": "Escalation assigned"}
    """
    try:

        trace = db.query(DoctorTrace).filter(DoctorTrace.id == trace_id).first()
        if not trace:
            raise HTTPException(status_code=404, detail="Trace not found")

        trace.assigned_to_user_id = assigned_to_user_id
        db.commit()

        logger.info(f"Escalation assigned: trace_id={trace_id}, assigned_to={assigned_to_user_id}")

        return {"status": "success", "message": "Escalation assigned"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        db.rollback()
        logger.error(f"Failed to assign escalation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to assign escalation: {str(e)}")
