"""Module Integration Service - Wires all endpoints to create message queue entries.

Every business event should trigger queue message creation. This service provides
easy-to-use methods for all modules to enqueue their events.

Modules that integrate:
- Recruitment: candidate_created, interview_scheduled, offer_generated, etc.
- Timesheet: timesheet_submitted, approved, rejected
- KPI: kpi_updated, target_achieved, target_missed
- Sales: deal_created, closed, lost, proposal_sent
- Client: client_created, contacted, onboarded
- HR: employee_joined, review_scheduled
- Project: task_assigned, completed
- Finance: invoice_created, payment_due
- Approval: approval_requested, action
- Commission: commission_calculated

Implements FAIL FAST: All methods raise exceptions on error.
"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from app.core.logging import logger

logger = logging.getLogger(__name__)


class ModuleIntegration:
    """Easy integration methods for all modules to create queue messages."""

    @staticmethod
    def _enqueue(
        message_type: str,
        payload: Dict[str, Any],
        resource_id: Optional[str] = None,
        created_by: str = "system",
        db: Optional[Session] = None,
    ) -> str:
        """
        Internal method to enqueue a message.

        Args:
            message_type: Type of event
            payload: Event payload
            resource_id: Optional resource ID for audit trail
            created_by: User or system creating the message
            db: Database session

        Returns:
            Message ID

        Raises:
            RuntimeError: If enqueue fails
        """
        if db is None:
            raise ValueError("Database session required")

        try:
            from app.services.message_queue_service import MessageQueueService

            message_id = MessageQueueService.enqueue(
                message_type=message_type,
                payload=payload,
                resource_id=resource_id,
                created_by=created_by,
                db=db,
            )

            logger.info(f"Enqueued {message_type}: {message_id}")
            return message_id

        except Exception as e:
            logger.error(f"Failed to enqueue {message_type}: {e}", exc_info=True)
            raise RuntimeError(f"Failed to enqueue {message_type}: {str(e)}")

    # ===== RECRUITMENT EVENTS =====

    @staticmethod
    def candidate_created(candidate_id: str, candidate_data: Dict[str, Any], db: Optional[Session] = None) -> str:
        """Candidate added to system."""
        return ModuleIntegration._enqueue(
            message_type="candidate_created",
            payload={
                "candidate_id": candidate_id,
                "candidate_name": candidate_data.get("candidate_name"),
                "email": candidate_data.get("candidate_email"),
                "phone": candidate_data.get("candidate_phone"),
                "job_id": candidate_data.get("job_id"),
                "source": candidate_data.get("source"),
                "timestamp": datetime.utcnow().isoformat(),
            },
            resource_id=candidate_id,
            db=db,
        )

    @staticmethod
    def interview_scheduled(
        interview_id: str,
        candidate_id: str,
        job_id: str,
        interview_data: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> str:
        """Interview scheduled for candidate."""
        return ModuleIntegration._enqueue(
            message_type="interview_scheduled",
            payload={
                "interview_id": interview_id,
                "candidate_id": candidate_id,
                "job_id": job_id,
                "interview_date": interview_data.get("interview_date"),
                "interview_time": interview_data.get("interview_time"),
                "interview_type": interview_data.get("interview_type"),
                "platform": interview_data.get("platform"),
                "hiring_manager": interview_data.get("hiring_manager_id"),
                "timestamp": datetime.utcnow().isoformat(),
            },
            resource_id=interview_id,
            db=db,
        )

    @staticmethod
    def offer_generated(
        offer_id: str,
        candidate_id: str,
        job_id: str,
        offer_data: Dict[str, Any],
        db: Optional[Session] = None,
    ) -> str:
        """Offer letter generated for candidate."""
        return ModuleIntegration._enqueue(
            message_type="offer_generated",
            payload={
                "offer_id": offer_id,
                "candidate_id": candidate_id,
                "job_id": job_id,
                "position": offer_data.get("position"),
                "salary": offer_data.get("salary"),
                "start_date": offer_data.get("start_date"),
                "offer_status": "generated",
                "timestamp": datetime.utcnow().isoformat(),
            },
            resource_id=offer_id,
            db=db,
        )

    @staticmethod
    def offer_accepted(offer_id: str, candidate_id: str, db: Optional[Session] = None) -> str:
        """Candidate accepted offer."""
        return ModuleIntegration._enqueue(
            message_type="offer_accepted",
            payload={
                "offer_id": offer_id,
                "candidate_id": candidate_id,
                "accepted_at": datetime.utcnow().isoformat(),
            },
            resource_id=offer_id,
            db=db,
        )

    @staticmethod
    def candidate_hired(candidate_id: str, employee_id: str, hire_data: Dict[str, Any], db: Optional[Session] = None) -> str:
        """Candidate converted to employee."""
        return ModuleIntegration._enqueue(
            message_type="candidate_hired",
            payload={
                "candidate_id": candidate_id,
                "employee_id": employee_id,
                "position": hire_data.get("position"),
                "joining_date": hire_data.get("joining_date"),
                "department": hire_data.get("department"),
                "hired_at": datetime.utcnow().isoformat(),
            },
            resource_id=employee_id,
            db=db,
        )

    # ===== TIMESHEET EVENTS =====

    @staticmethod
    def timesheet_submitted(timesheet_id: str, employee_id: str, timesheet_data: Dict[str, Any], db: Optional[Session] = None) -> str:
        """Timesheet submitted by employee."""
        return ModuleIntegration._enqueue(
            message_type="timesheet_submitted",
            payload={
                "timesheet_id": timesheet_id,
                "employee_id": employee_id,
                "week_ending": timesheet_data.get("week_ending"),
                "total_hours": timesheet_data.get("total_hours"),
                "submitted_at": datetime.utcnow().isoformat(),
            },
            resource_id=timesheet_id,
            db=db,
        )

    @staticmethod
    def timesheet_approved(timesheet_id: str, approved_by: str, db: Optional[Session] = None) -> str:
        """Timesheet approved."""
        return ModuleIntegration._enqueue(
            message_type="timesheet_approved",
            payload={
                "timesheet_id": timesheet_id,
                "approved_by": approved_by,
                "approved_at": datetime.utcnow().isoformat(),
            },
            resource_id=timesheet_id,
            db=db,
        )

    @staticmethod
    def timesheet_rejected(timesheet_id: str, rejected_by: str, reason: str, db: Optional[Session] = None) -> str:
        """Timesheet rejected."""
        return ModuleIntegration._enqueue(
            message_type="timesheet_rejected",
            payload={
                "timesheet_id": timesheet_id,
                "rejected_by": rejected_by,
                "reason": reason,
                "rejected_at": datetime.utcnow().isoformat(),
            },
            resource_id=timesheet_id,
            db=db,
        )

    # ===== KPI/PERFORMANCE EVENTS =====

    @staticmethod
    def kpi_updated(kpi_id: str, user_id: str, kpi_data: Dict[str, Any], db: Optional[Session] = None) -> str:
        """KPI updated."""
        return ModuleIntegration._enqueue(
            message_type="kpi_updated",
            payload={
                "kpi_id": kpi_id,
                "user_id": user_id,
                "kpi_name": kpi_data.get("kpi_name"),
                "current_value": kpi_data.get("current_value"),
                "target_value": kpi_data.get("target_value"),
                "updated_at": datetime.utcnow().isoformat(),
            },
            resource_id=kpi_id,
            db=db,
        )

    @staticmethod
    def target_achieved(kpi_id: str, user_id: str, db: Optional[Session] = None) -> str:
        """Target achieved."""
        return ModuleIntegration._enqueue(
            message_type="target_achieved",
            payload={
                "kpi_id": kpi_id,
                "user_id": user_id,
                "achieved_at": datetime.utcnow().isoformat(),
            },
            resource_id=kpi_id,
            db=db,
        )

    @staticmethod
    def target_missed(kpi_id: str, user_id: str, shortfall: float, db: Optional[Session] = None) -> str:
        """Target missed."""
        return ModuleIntegration._enqueue(
            message_type="target_missed",
            payload={
                "kpi_id": kpi_id,
                "user_id": user_id,
                "shortfall": shortfall,
                "missed_at": datetime.utcnow().isoformat(),
            },
            resource_id=kpi_id,
            db=db,
        )

    # ===== SALES EVENTS =====

    @staticmethod
    def deal_created(deal_id: str, client_id: str, deal_data: Dict[str, Any], db: Optional[Session] = None) -> str:
        """Deal created."""
        return ModuleIntegration._enqueue(
            message_type="deal_created",
            payload={
                "deal_id": deal_id,
                "client_id": client_id,
                "deal_name": deal_data.get("deal_name"),
                "amount": deal_data.get("amount"),
                "expected_close": deal_data.get("expected_close"),
                "created_at": datetime.utcnow().isoformat(),
            },
            resource_id=deal_id,
            db=db,
        )

    @staticmethod
    def deal_closed(deal_id: str, revenue: float, db: Optional[Session] = None) -> str:
        """Deal closed/won."""
        return ModuleIntegration._enqueue(
            message_type="deal_closed",
            payload={
                "deal_id": deal_id,
                "revenue": revenue,
                "closed_at": datetime.utcnow().isoformat(),
            },
            resource_id=deal_id,
            db=db,
        )

    @staticmethod
    def deal_lost(deal_id: str, reason: str, db: Optional[Session] = None) -> str:
        """Deal lost."""
        return ModuleIntegration._enqueue(
            message_type="deal_lost",
            payload={
                "deal_id": deal_id,
                "lost_reason": reason,
                "lost_at": datetime.utcnow().isoformat(),
            },
            resource_id=deal_id,
            db=db,
        )

    @staticmethod
    def proposal_sent(proposal_id: str, client_id: str, deal_id: str, db: Optional[Session] = None) -> str:
        """Proposal sent to client."""
        return ModuleIntegration._enqueue(
            message_type="proposal_sent",
            payload={
                "proposal_id": proposal_id,
                "client_id": client_id,
                "deal_id": deal_id,
                "sent_at": datetime.utcnow().isoformat(),
            },
            resource_id=proposal_id,
            db=db,
        )

    # ===== CLIENT EVENTS =====

    @staticmethod
    def client_created(client_id: str, client_data: Dict[str, Any], db: Optional[Session] = None) -> str:
        """New client created."""
        return ModuleIntegration._enqueue(
            message_type="client_created",
            payload={
                "client_id": client_id,
                "client_name": client_data.get("client_name"),
                "industry": client_data.get("industry"),
                "location": client_data.get("location"),
                "created_at": datetime.utcnow().isoformat(),
            },
            resource_id=client_id,
            db=db,
        )

    @staticmethod
    def client_contacted(client_id: str, contact_type: str, db: Optional[Session] = None) -> str:
        """Client contacted."""
        return ModuleIntegration._enqueue(
            message_type="client_contacted",
            payload={
                "client_id": client_id,
                "contact_type": contact_type,
                "contacted_at": datetime.utcnow().isoformat(),
            },
            resource_id=client_id,
            db=db,
        )

    @staticmethod
    def client_onboarded(client_id: str, db: Optional[Session] = None) -> str:
        """Client onboarded."""
        return ModuleIntegration._enqueue(
            message_type="client_onboarded",
            payload={
                "client_id": client_id,
                "onboarded_at": datetime.utcnow().isoformat(),
            },
            resource_id=client_id,
            db=db,
        )

    # ===== HR EVENTS =====

    @staticmethod
    def employee_joined(employee_id: str, employee_data: Dict[str, Any], db: Optional[Session] = None) -> str:
        """Employee joined company."""
        return ModuleIntegration._enqueue(
            message_type="employee_joined",
            payload={
                "employee_id": employee_id,
                "employee_name": employee_data.get("employee_name"),
                "position": employee_data.get("position"),
                "department": employee_data.get("department"),
                "joining_date": employee_data.get("joining_date"),
                "joined_at": datetime.utcnow().isoformat(),
            },
            resource_id=employee_id,
            db=db,
        )

    @staticmethod
    def review_scheduled(review_id: str, employee_id: str, reviewer_id: str, review_date: str, db: Optional[Session] = None) -> str:
        """Performance review scheduled."""
        return ModuleIntegration._enqueue(
            message_type="review_scheduled",
            payload={
                "review_id": review_id,
                "employee_id": employee_id,
                "reviewer_id": reviewer_id,
                "review_date": review_date,
                "scheduled_at": datetime.utcnow().isoformat(),
            },
            resource_id=review_id,
            db=db,
        )

    # ===== PROJECT EVENTS =====

    @staticmethod
    def task_assigned(task_id: str, assignee_id: str, task_data: Dict[str, Any], db: Optional[Session] = None) -> str:
        """Task assigned to employee."""
        return ModuleIntegration._enqueue(
            message_type="task_assigned",
            payload={
                "task_id": task_id,
                "assignee_id": assignee_id,
                "task_title": task_data.get("task_title"),
                "project_id": task_data.get("project_id"),
                "due_date": task_data.get("due_date"),
                "assigned_at": datetime.utcnow().isoformat(),
            },
            resource_id=task_id,
            db=db,
        )

    @staticmethod
    def task_completed(task_id: str, completed_by: str, db: Optional[Session] = None) -> str:
        """Task completed."""
        return ModuleIntegration._enqueue(
            message_type="task_completed",
            payload={
                "task_id": task_id,
                "completed_by": completed_by,
                "completed_at": datetime.utcnow().isoformat(),
            },
            resource_id=task_id,
            db=db,
        )

    # ===== FINANCE EVENTS =====

    @staticmethod
    def invoice_created(invoice_id: str, client_id: str, amount: float, due_date: str, db: Optional[Session] = None) -> str:
        """Invoice created."""
        return ModuleIntegration._enqueue(
            message_type="invoice_created",
            payload={
                "invoice_id": invoice_id,
                "client_id": client_id,
                "amount": amount,
                "due_date": due_date,
                "created_at": datetime.utcnow().isoformat(),
            },
            resource_id=invoice_id,
            db=db,
        )

    @staticmethod
    def payment_due(invoice_id: str, days_until_due: int, db: Optional[Session] = None) -> str:
        """Payment due reminder."""
        return ModuleIntegration._enqueue(
            message_type="payment_due",
            payload={
                "invoice_id": invoice_id,
                "days_until_due": days_until_due,
                "reminded_at": datetime.utcnow().isoformat(),
            },
            resource_id=invoice_id,
            db=db,
        )

    # ===== APPROVAL EVENTS =====

    @staticmethod
    def approval_requested(
        approval_id: str,
        approver_id: str,
        approval_type: str,
        subject_id: str,
        db: Optional[Session] = None,
    ) -> str:
        """Approval requested."""
        return ModuleIntegration._enqueue(
            message_type="approval_requested",
            payload={
                "approval_id": approval_id,
                "approver_id": approver_id,
                "approval_type": approval_type,
                "subject_id": subject_id,
                "requested_at": datetime.utcnow().isoformat(),
            },
            resource_id=approval_id,
            db=db,
        )

    @staticmethod
    def approval_action(approval_id: str, action: str, db: Optional[Session] = None) -> str:
        """Approval action taken."""
        return ModuleIntegration._enqueue(
            message_type="approval_action",
            payload={
                "approval_id": approval_id,
                "action": action,  # approved, rejected, escalated
                "actioned_at": datetime.utcnow().isoformat(),
            },
            resource_id=approval_id,
            db=db,
        )

    # ===== COMMISSION EVENTS =====

    @staticmethod
    def commission_calculated(
        commission_id: str,
        recipient_id: str,
        commission_type: str,
        amount: float,
        db: Optional[Session] = None,
    ) -> str:
        """Commission calculated."""
        return ModuleIntegration._enqueue(
            message_type="commission_calculated",
            payload={
                "commission_id": commission_id,
                "recipient_id": recipient_id,
                "commission_type": commission_type,
                "amount": amount,
                "calculated_at": datetime.utcnow().isoformat(),
            },
            resource_id=commission_id,
            db=db,
        )


# Import datetime at top level
from datetime import datetime
