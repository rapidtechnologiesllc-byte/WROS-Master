"""
Doctor Agent Traces API Endpoints

Provides admin dashboard access to Doctor Agent diagnostic history.
Allows inspection of all fix attempts, strategies tried, and escalations.

Endpoints:
- GET /admin/doctor/messages/{message_id}/traces - Get traces for a specific message
- GET /admin/doctor/failed-messages - Get all escalated messages
- GET /admin/doctor/dashboard - Dashboard summary
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin_role
from app.models.doctor_trace import DoctorTrace
from app.services.doctor_service import DoctorService
from app.core.logging import logger


router = APIRouter(prefix="/admin/doctor", tags=["Doctor Agent"])


class DoctorTraceResponse:
    """Response schema for doctor trace"""
    def __init__(self, trace: DoctorTrace):
        self.id = trace.id
        self.message_id = trace.message_id
        self.attempt_number = trace.attempt_number
        self.strategy_name = trace.strategy_name
        self.success = trace.success
        self.error_message = trace.error_message
        self.fix_applied = trace.fix_applied
        self.timestamp = trace.timestamp.isoformat() if trace.timestamp else None
        self.ticket_id = trace.ticket_id


@router.get("/messages/{message_id}/traces")
def get_doctor_traces(
    message_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_role),
) -> dict:
    """
    Get all doctor traces for a specific message.

    Shows complete diagnostic history: all attempts, strategies tried, fixes applied.

    Response:
    {
        "message_id": "msg_123",
        "total_attempts": 3,
        "escalated": true,
        "ticket_id": 456,
        "traces": [
            {
                "attempt_number": 1,
                "strategy_name": "SMS",
                "success": false,
                "error_message": "Phone number not found",
                "fix_applied": "Alternative contacts identified: [phone, linkedin]",
                "timestamp": "2026-08-27T10:30:00"
            },
            ...
        ]
    }
    """
    try:
        doctor = DoctorService(db)
        traces = doctor.get_traces_for_message(message_id)

        if not traces:
            raise HTTPException(status_code=404, detail=f"No traces found for message {message_id}")

        escalated = any(t.strategy_name == "ESCALATE_TO_WROS" for t in traces)
        ticket_id = next((t.ticket_id for t in traces if t.ticket_id), None)

        return {
            "message_id": message_id,
            "total_attempts": len(traces),
            "escalated": escalated,
            "ticket_id": ticket_id,
            "traces": [
                {
                    "attempt_number": t.attempt_number,
                    "strategy_name": t.strategy_name,
                    "success": t.success,
                    "error_message": t.error_message,
                    "fix_applied": t.fix_applied,
                    "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                }
                for t in traces
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching doctor traces for {message_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching doctor traces")


@router.get("/failed-messages")
def get_failed_messages(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_role),
) -> dict:
    """
    Get all messages that escalated to WROS after doctor exhausted all strategies.

    Response:
    {
        "total": 5,
        "messages": [
            {
                "message_id": "msg_123",
                "attempts": 3,
                "ticket_id": 456,
                "escalated_at": "2026-08-27T10:30:00",
                "traces": [
                    {"attempt": 1, "strategy": "SMS", "success": false, "error": "..."},
                    ...
                ]
            },
            ...
        ]
    }
    """
    try:
        doctor = DoctorService(db)
        failed_messages = doctor.get_failed_messages(limit=limit)

        return {
            "total": len(failed_messages),
            "messages": failed_messages
        }

    except Exception as e:
        logger.error(f"Error fetching failed messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching failed messages")


@router.get("/dashboard")
def get_doctor_dashboard(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_role),
) -> dict:
    """
    Get Doctor Agent dashboard summary.

    Shows:
    - Total messages processed
    - Successful self-heals (resolved by doctor)
    - Escalations to WROS
    - Top error types
    - Top strategies used

    Response:
    {
        "total_messages": 1234,
        "resolved_by_doctor": 1100,
        "escalated_to_wros": 134,
        "resolution_rate": 89.1,
        "top_error_types": [
            {"error_type": "EMAIL_DELIVERY_FAILED", "count": 50, "resolved": 40},
            ...
        ],
        "top_strategies": [
            {"strategy": "SERVICE_RETRY", "used": 500, "success": 450},
            ...
        ]
    }
    """
    try:
        # Query statistics
        all_traces = db.query(DoctorTrace).all()

        if not all_traces:
            return {
                "total_messages": 0,
                "resolved_by_doctor": 0,
                "escalated_to_wros": 0,
                "resolution_rate": 0.0,
                "top_error_types": [],
                "top_strategies": [],
            }

        # Count unique messages
        message_ids = set(t.message_id for t in all_traces)
        total_messages = len(message_ids)

        # Count resolved vs escalated
        resolved = len([m for m in message_ids if any(t.message_id == m and t.success for t in all_traces)])
        escalated = len([m for m in message_ids if any(t.message_id == m and t.strategy_name == "ESCALATE_TO_WROS" for t in all_traces)])

        # Resolution rate
        resolution_rate = (resolved / total_messages * 100) if total_messages > 0 else 0.0

        # Top strategies
        strategy_stats = {}
        for trace in all_traces:
            if trace.strategy_name not in strategy_stats:
                strategy_stats[trace.strategy_name] = {"used": 0, "success": 0}
            strategy_stats[trace.strategy_name]["used"] += 1
            if trace.success:
                strategy_stats[trace.strategy_name]["success"] += 1

        top_strategies = [
            {
                "strategy": name,
                "used": stats["used"],
                "success": stats["success"],
                "success_rate": (stats["success"] / stats["used"] * 100) if stats["used"] > 0 else 0
            }
            for name, stats in sorted(strategy_stats.items(), key=lambda x: x[1]["used"], reverse=True)[:5]
        ]

        return {
            "total_messages": total_messages,
            "resolved_by_doctor": resolved,
            "escalated_to_wros": escalated,
            "resolution_rate": round(resolution_rate, 1),
            "top_strategies": top_strategies,
        }

    except Exception as e:
        logger.error(f"Error generating doctor dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error generating dashboard")
