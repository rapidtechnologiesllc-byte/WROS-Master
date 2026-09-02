"""System Health & Phalanx Integrity Endpoints

Provides real-time health metrics and Spartan Phalanx formation integrity.
Shows which systems are strong (protecting neighbors) vs weak (need support).
"""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger

router = APIRouter(prefix="/admin", tags=["health"])


@router.get("/health")
    dependencies=[Depends(require_resource_permission("health", "view"))]
def get_system_health(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get overall system health status and Phalanx formation integrity.

    Returns:
        {
            "data": {
                "database_status": "healthy",
                "queue_status": "healthy",
                "slm_status": "healthy",
                "doctor_status": "active",

                "phalanx_formations": {
                    "recruitment": {
                        "integrity": 87,  # 0-100%
                        "status": "HEALTHY",
                        "agents": [
                            {
                                "position": 1,
                                "name": "Thunder",
                                "shield_strength": 95,
                                "protecting": "Recruitment Agent",
                                "status": "OPERATIONAL"
                            },
                            ...
                        ]
                    },
                    "resource_management": {...},
                    "finance": {...}
                },

                "alerts": [
                    "Recruitment Phalanx integrity at 75%: Interview Reminder shows warning signs",
                    "Doctor Agent escalations: 3 ACTIVE, 1 PENDING"
                ],

                "timestamp": "2026-08-27T10:00:00Z"
            }
        }
    """
    try:
        # Database health
        db_status = "healthy"
        try:
            db.execute(text("SELECT 1"))
            db_status = "healthy"
        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Database health check failed: {e}")
            db_status = "error"

        # Queue health (check if queue tables exist and are accessible)
        queue_status = "healthy"
        try:
            from app.models.message_queue import MessageQueue
            pending_count = db.query(MessageQueue).filter(
                MessageQueue.status == "PENDING"
            ).count()

            # If pending queue is too large, flag as degraded
            if pending_count > 1000:
                queue_status = "warning"
            else:
                queue_status = "healthy"
        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.error(f"Queue health check failed: {e}")
            queue_status = "unknown"

        # SLM Service status (check if SLM models exist)
        slm_status = "healthy"
        try:
            # Check if any SLM processing records exist recently
            from app.models.candidate import Candidate
            recent_parsed = db.query(Candidate).filter(
                Candidate.resume_data.isnot(None)
            ).count()

            if recent_parsed > 0:
                slm_status = "healthy"
            else:
                slm_status = "unknown"
        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"SLM health check inconclusive: {e}")
            slm_status = "unknown"

        # Doctor Agent status (check for recent escalations)
        doctor_status = "active"
        doctor_escalations = 0
        try:
            from app.models.doctor_trace import DoctorTrace
            recent_traces = db.query(DoctorTrace).filter(
                DoctorTrace.attempt_number >= 3,
                DoctorTrace.success == False
            ).count()

            doctor_escalations = recent_traces
            doctor_status = "active" if recent_traces >= 0 else "inactive"
        except Exception as e:
           logger.error(f"Error: {str(e)}", exc_info=True)
            logger.warning(f"Doctor agent status check inconclusive: {e}")
            doctor_status = "unknown"

        # Phalanx Formations (mock data - wire to actual phalanx models)
        phalanx_formations = {
            "recruitment": {
                "integrity": 87,
                "status": "HEALTHY",
                "agents": [
                    {
                        "position": 1,
                        "name": "Thunder",
                        "shield_strength": 95,
                        "protecting": "Recruitment Agent",
                        "status": "OPERATIONAL"
                    },
                    {
                        "position": 2,
                        "name": "Recruitment Agent",
                        "shield_strength": 88,
                        "protecting": "Interview Reminder",
                        "status": "OPERATIONAL"
                    },
                    {
                        "position": 3,
                        "name": "Interview Reminder",
                        "shield_strength": 75,
                        "protecting": "HR Agent",
                        "status": "DEGRADED"  # Shows warning
                    },
                ]
            },
            "resource_management": {
                "integrity": 92,
                "status": "HEALTHY",
                "agents": [
                    {
                        "position": 1,
                        "name": "Employee Creation",
                        "shield_strength": 94,
                        "protecting": "Resource Manager",
                        "status": "OPERATIONAL"
                    },
                    {
                        "position": 2,
                        "name": "Resource Manager",
                        "shield_strength": 91,
                        "protecting": "Utilization",
                        "status": "OPERATIONAL"
                    },
                ]
            },
            "finance": {
                "integrity": 89,
                "status": "HEALTHY",
                "agents": [
                    {
                        "position": 1,
                        "name": "Opportunity Pipeline",
                        "shield_strength": 90,
                        "protecting": "CFO Agent",
                        "status": "OPERATIONAL"
                    },
                ]
            }
        }

        # Generate alerts
        alerts = []

        if db_status != "healthy":
            alerts.append(f"⚠️ Database status: {db_status}")

        if queue_status == "warning":
            alerts.append("⚠️ Message Queue: Pending items exceeding threshold (>1000)")

        if doctor_escalations > 0:
            alerts.append(f"🚨 Doctor Agent: {doctor_escalations} active escalations to WROS")

        if phalanx_formations["recruitment"]["integrity"] < 85:
            alerts.append("🚨 Recruitment Phalanx integrity degrading: Interview Reminder showing weakness")

        return {
            "data": {
                "database_status": db_status,
                "queue_status": queue_status,
                "slm_status": slm_status,
                "doctor_status": doctor_status,
                "doctor_escalations": doctor_escalations,

                "phalanx_formations": phalanx_formations,

                "alerts": alerts,

                "timestamp": logger.timestamp() if hasattr(logger, 'timestamp') else None,
            }
        }

    except Exception as e:        logger.error(f"Failed to get system health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get system health: {str(e)}")


@router.get("/phalanx/{phalanx_name}/integrity")
    dependencies=[Depends(require_resource_permission("phalanx", "view"))]
def get_phalanx_integrity(
    phalanx_name: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get detailed integrity analysis for a specific phalanx formation.

    Args:
        phalanx_name: recruitment, resource_management, or finance

    Returns:
        {
            "data": {
                "phalanx": "recruitment",
                "formation_integrity": 87,
                "status": "HEALTHY",
                "agents": [
                    {
                        "position": 1,
                        "name": "Thunder",
                        "shield_strength": 95,
                        "left_neighbor": None,
                        "right_neighbor": "Recruitment Agent",
                        "vulnerabilities": ["Rate limiting", "False positives"],
                        "shield_metrics": {
                            "success_rate": 0.95,
                            "latency_ms": 1200,
                            "quality_score": 0.92
                        }
                    },
                    ...
                ]
            }
        }
    """
    try:
        # TODO: Wire to actual AgentPhalanxFormation model queries

        phalanx_map = {
            "recruitment": {
                "formation_integrity": 87,
                "status": "HEALTHY",
                "agents": [
                    {
                        "position": 1,
                        "name": "Thunder",
                        "shield_strength": 95,
                        "left_neighbor": None,
                        "right_neighbor": "Recruitment Agent",
                        "vulnerabilities": ["Rate limiting", "False positives"],
                    },
                    {
                        "position": 2,
                        "name": "Recruitment Agent",
                        "shield_strength": 88,
                        "left_neighbor": "Thunder",
                        "right_neighbor": "Interview Reminder",
                        "vulnerabilities": ["Job description accuracy", "Candidate sourcing"],
                    },
                    {
                        "position": 3,
                        "name": "Interview Reminder",
                        "shield_strength": 75,
                        "left_neighbor": "Recruitment Agent",
                        "right_neighbor": "HR Agent",
                        "vulnerabilities": ["Scheduling delays", "Calendar integrations"],
                    },
                ]
            },
            "resource_management": {
                "formation_integrity": 92,
                "status": "HEALTHY",
                "agents": []
            },
            "finance": {
                "formation_integrity": 89,
                "status": "HEALTHY",
                "agents": []
            }
        }

        if phalanx_name.lower() not in phalanx_map:
            raise HTTPException(status_code=404, detail=f"Phalanx '{phalanx_name}' not found")

        result = phalanx_map[phalanx_name.lower()]
        result["phalanx"] = phalanx_name.lower()

        return {"data": result}

    except HTTPException:
        raise
    except Exception as e:        logger.error(f"Failed to get phalanx integrity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get phalanx integrity: {str(e)}")
