"""Spartan Phalanx Orchestration - Coordinates all systems via Message Queue + SLM"""
import logging
import json
from typing import Any, Dict, Optional, List
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.services.message_queue_service import MessageQueueService
from app.services.finance_service import FinanceService
from app.services.timesheet_bulk_service import TimesheetBulkService
from app.services.job_management_service import JobManagementService
from app.services.demand_management_service import DemandManagementService
from app.services.kpi_service import KPIService

class SpartanOrchestrationService:
    """Master orchestrator for Spartan Phalanx formations"""

    # Phalanx Formations
    RECRUITMENT_PHALANX = {
        "name": "recruitment",
        "shield_agents": ["Thunder", "AI Recruiter", "Interview Scheduler", "Offer Generator"],
        "protected_agents": ["Flash", "HR Onboarding", "Reference Checker"],
        "kpis": ["candidates_sourced", "time_to_hire", "offer_acceptance_rate"],
        "min_integrity": 85
    }

    RESOURCE_MANAGEMENT_PHALANX = {
        "name": "resource_management",
        "shield_agents": ["Resource Allocator", "Timesheet Manager", "Utilization Optimizer"],
        "protected_agents": ["Project Manager", "Resource Forecaster", "Demand Fulfiller"],
        "kpis": ["resource_utilization", "timesheet_approval_rate", "demand_fulfillment"],
        "min_integrity": 85
    }

    FINANCE_PHALANX = {
        "name": "finance",
        "shield_agents": ["Invoice Manager", "Revenue Recognizer", "Cash Flow Manager"],
        "protected_agents": ["CFO Dashboard", "Financial Reporting", "Compliance Checker"],
        "kpis": ["invoice_approval_rate", "revenue_recognition_rate", "payment_collection_rate"],
        "min_integrity": 85
    }

    @staticmethod
    def queue_recruitment_operation(
        db: Session,
        operation: str,  # "CANDIDATE_INTAKE", "INTERVIEW_SCHEDULE", "OFFER_CREATE", "HIRE"
        payload: Dict[str, Any],
        priority: str = "NORMAL"
    ) -> Dict[str, Any]:
        """Queue a recruitment operation through Message Queue"""
        try:
            message = {
                "type": f"recruitment.{operation.lower()}",
                "operation": operation,
                "payload": payload,
                "phalanx": "recruitment",
                "timestamp": datetime.utcnow().isoformat(),
                "priority": priority
            }

            queue_result = MessageQueueService.enqueue(
                db=db,
                message_type=f"recruitment.{operation.lower()}",
                payload=json.dumps(message),
                priority=priority,
                resource_id=payload.get("candidate_id") or payload.get("job_id")
            )

            logger.info(f"Recruitment operation queued: {operation}, message_id={queue_result['message_id']}")
            return queue_result

        except Exception as e:
            logger.error(f"Failed to queue recruitment operation: {e}", exc_info=True)
            raise

    @staticmethod
    def queue_resource_operation(
        db: Session,
        operation: str,  # "ALLOCATION_CREATE", "TIMESHEET_SUBMIT", "DEMAND_FULFILL"
        payload: Dict[str, Any],
        priority: str = "NORMAL"
    ) -> Dict[str, Any]:
        """Queue a resource management operation"""
        try:
            message = {
                "type": f"resource.{operation.lower()}",
                "operation": operation,
                "payload": payload,
                "phalanx": "resource_management",
                "timestamp": datetime.utcnow().isoformat(),
                "priority": priority
            }

            queue_result = MessageQueueService.enqueue(
                db=db,
                message_type=f"resource.{operation.lower()}",
                payload=json.dumps(message),
                priority=priority,
                resource_id=payload.get("employee_id") or payload.get("project_id")
            )

            logger.info(f"Resource operation queued: {operation}, message_id={queue_result['message_id']}")
            return queue_result

        except Exception as e:
            logger.error(f"Failed to queue resource operation: {e}", exc_info=True)
            raise

    @staticmethod
    def queue_finance_operation(
        db: Session,
        operation: str,  # "INVOICE_CREATE", "INVOICE_APPROVE", "REVENUE_RECOGNIZE"
        payload: Dict[str, Any],
        priority: str = "NORMAL"
    ) -> Dict[str, Any]:
        """Queue a finance operation"""
        try:
            message = {
                "type": f"finance.{operation.lower()}",
                "operation": operation,
                "payload": payload,
                "phalanx": "finance",
                "timestamp": datetime.utcnow().isoformat(),
                "priority": priority
            }

            queue_result = MessageQueueService.enqueue(
                db=db,
                message_type=f"finance.{operation.lower()}",
                payload=json.dumps(message),
                priority=priority,
                resource_id=payload.get("invoice_id") or payload.get("opportunity_id")
            )

            logger.info(f"Finance operation queued: {operation}, message_id={queue_result['message_id']}")
            return queue_result

        except Exception as e:
            logger.error(f"Failed to queue finance operation: {e}", exc_info=True)
            raise

    @staticmethod
    def process_queued_operation(
        db: Session,
        message_id: str,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a queued operation (called by message processor/SLM)"""
        try:
            operation = message_data.get("operation")
            payload = message_data.get("payload", {})
            phalanx = message_data.get("phalanx")

            result = None

            # Route to appropriate service based on phalanx
            if phalanx == "recruitment":
                result = SpartanOrchestrationService._process_recruitment_operation(
                    db, operation, payload
                )
            elif phalanx == "resource_management":
                result = SpartanOrchestrationService._process_resource_operation(
                    db, operation, payload
                )
            elif phalanx == "finance":
                result = SpartanOrchestrationService._process_finance_operation(
                    db, operation, payload
                )

            logger.info(f"Operation processed: {operation}, result_status={result.get('status') if result else 'unknown'}")
            return result or {"status": "unknown", "message_id": message_id}

        except Exception as e:
            logger.error(f"Failed to process queued operation: {e}", exc_info=True)
            return {"status": "error", "error": str(e), "message_id": message_id}

    @staticmethod
    def _process_recruitment_operation(
        db: Session,
        operation: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process recruitment operation"""
        try:
            if operation == "CANDIDATE_INTAKE":
                return {"status": "success", "operation": operation, "candidate_id": payload.get("candidate_id")}
            elif operation == "INTERVIEW_SCHEDULE":
                return {"status": "success", "operation": operation, "interview_id": payload.get("interview_id")}
            elif operation == "OFFER_CREATE":
                return {"status": "success", "operation": operation, "offer_id": payload.get("offer_id")}
            elif operation == "HIRE":
                return {"status": "success", "operation": operation, "employee_id": payload.get("employee_id")}
            return {"status": "unknown", "operation": operation}
        except Exception as e:
            logger.error(f"Recruitment operation failed: {e}")
            return {"status": "error", "operation": operation, "error": str(e)}

    @staticmethod
    def _process_resource_operation(
        db: Session,
        operation: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process resource operation"""
        try:
            if operation == "ALLOCATION_CREATE":
                return {"status": "success", "operation": operation, "allocation_id": payload.get("allocation_id")}
            elif operation == "TIMESHEET_SUBMIT":
                return {"status": "success", "operation": operation, "timesheet_id": payload.get("timesheet_id")}
            elif operation == "DEMAND_FULFILL":
                return {"status": "success", "operation": operation, "demand_id": payload.get("demand_id")}
            return {"status": "unknown", "operation": operation}
        except Exception as e:
            logger.error(f"Resource operation failed: {e}")
            return {"status": "error", "operation": operation, "error": str(e)}

    @staticmethod
    def _process_finance_operation(
        db: Session,
        operation: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process finance operation"""
        try:
            if operation == "INVOICE_CREATE":
                result = FinanceService.create_invoice(
                    db=db,
                    opportunity_id=payload.get("opportunity_id"),
                    amount=payload.get("amount"),
                    currency=payload.get("currency", "USD"),
                    created_by=payload.get("created_by", "SLM_SYSTEM")
                )
                return {"status": "success", "operation": operation, "invoice_id": result.get("id")}
            elif operation == "INVOICE_APPROVE":
                result = FinanceService.approve_invoice(
                    db=db,
                    invoice_id=payload.get("invoice_id"),
                    approved_by=payload.get("approved_by", "SLM_SYSTEM")
                )
                return {"status": "success", "operation": operation, "invoice_id": result.get("id")}
            elif operation == "REVENUE_RECOGNIZE":
                result = FinanceService.recognize_revenue(
                    db=db,
                    invoice_id=payload.get("invoice_id"),
                    amount=payload.get("amount")
                )
                return {"status": "success", "operation": operation, "revenue_id": result.get("revenue_id")}
            return {"status": "unknown", "operation": operation}
        except Exception as e:
            logger.error(f"Finance operation failed: {e}")
            return {"status": "error", "operation": operation, "error": str(e)}

    @staticmethod
    def check_phalanx_integrity(
        db: Session,
        phalanx: str
    ) -> Dict[str, Any]:
        """Check Phalanx formation integrity (health score)"""
        try:
            phalanx_config = None
            if phalanx == "recruitment":
                phalanx_config = SpartanOrchestrationService.RECRUITMENT_PHALANX
            elif phalanx == "resource_management":
                phalanx_config = SpartanOrchestrationService.RESOURCE_MANAGEMENT_PHALANX
            elif phalanx == "finance":
                phalanx_config = SpartanOrchestrationService.FINANCE_PHALANX

            if not phalanx_config:
                return {"phalanx": phalanx, "integrity": 0, "status": "unknown"}

            # Calculate health score from KPIs
            health_result = KPIService.get_phalanx_health_score(db, phalanx, "weekly")

            integrity = health_result.get("health_score", 0)
            status = "HEALTHY" if integrity >= phalanx_config["min_integrity"] else "DEGRADED" if integrity >= 70 else "BROKEN"

            return {
                "phalanx": phalanx,
                "integrity": integrity,
                "status": status,
                "min_threshold": phalanx_config["min_integrity"],
                "shield_agents": phalanx_config["shield_agents"],
                "protected_agents": phalanx_config["protected_agents"],
                "kpis": phalanx_config["kpis"]
            }

        except Exception as e:
            logger.error(f"Failed to check phalanx integrity: {e}", exc_info=True)
            return {"phalanx": phalanx, "integrity": 0, "status": "error"}

    @staticmethod
    def get_spartan_formation_status(
        db: Session
    ) -> Dict[str, Any]:
        """Get overall Spartan Phalanx formation status"""
        try:
            formations = []
            for phalanx_name in ["recruitment", "resource_management", "finance"]:
                status = SpartanOrchestrationService.check_phalanx_integrity(db, phalanx_name)
                formations.append(status)

            avg_integrity = sum(f.get("integrity", 0) for f in formations) / len(formations) if formations else 0

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "formations": formations,
                "overall_integrity": round(avg_integrity, 2),
                "status": "STRONG" if avg_integrity >= 85 else "WEAKENING" if avg_integrity >= 70 else "FAILING"
            }

        except Exception as e:
            logger.error(f"Failed to get formation status: {e}", exc_info=True)
            raise
