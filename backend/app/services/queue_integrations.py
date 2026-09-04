"""Queue Integration Helpers - Easy way for modules to enqueue messages

Each module that needs to trigger queues can use these helpers instead of
directly calling MessageQueueService.

Examples:
    # In a recruitment endpoint:
    QueueIntegrations.queue_candidate_created(candidate_id, candidate_email, db)

    # In an interview endpoint:
    QueueIntegrations.queue_interview_scheduled(interview_id, candidate_id, panel, db)

    # In a timesheet endpoint:
    QueueIntegrations.queue_timesheet_submitted(timesheet_id, employee_id, manager_id, db)
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.message_queue_service import MessageQueueService
from app.core.logging import logger

logger = logging.getLogger(__name__)

class QueueIntegrations:
    """Integration helpers for all modules"""

    # ==================== RECRUITMENT QUEUES ====================

    @staticmethod
    def queue_candidate_created(
        candidate_id: str,
        candidate_email: str,
        candidate_name: str,
        job_id: Optional[str] = None,
        source: str = "manual_intake",
        created_by: str = "system",
        db: Optional[Session] = None,
    ) -> str:
        """
        Queue a new candidate for Thunder autonomous processing.

        Args:
            candidate_id: Candidate UUID
            candidate_email: Candidate email
            candidate_name: Candidate full name
            job_id: Optional job ID if candidate applied for specific role
            source: Source of candidate (manual_intake, referral, job_board, etc.)
            created_by: User who created candidate
            db: Database session

        Returns:
            Message ID

        Raises:
            RuntimeError: If queueing fails
        """
        try:
            payload = {
                "candidate_id": candidate_id,
                "candidate_email": candidate_email,
                "candidate_name": candidate_name,
                "job_id": job_id,
                "source": source,
            }

            message_id = MessageQueueService.enqueue(
                message_type="candidate_created",
                payload=payload,
                resource_id=candidate_id,
                created_by=created_by,
                db=db,
            )

            logger.info(
                f"Queued candidate_created: {candidate_id} "
                f"from {source} (message: {message_id})"
            )
            return message_id

        except Exception as e:
            logger.error(f"Failed to queue candidate_created: {e}", exc_info=True)
            raise

    @staticmethod
    def queue_interview_scheduled(
        interview_id: str,
        candidate_id: str,
        candidate_email: str,
        candidate_phone: Optional[str],
        interview_date: str,
        interview_time: str,
        panel_members: List[Dict[str, str]],
        job_title: str,
        consent_whatsapp: bool = False,
        created_by: str = "system",
        db: Optional[Session] = None,
    ) -> str:
        """
        Queue interview notifications (email, whatsapp, calendar).

        Args:
            interview_id: Interview UUID
            candidate_id: Candidate UUID
            candidate_email: Candidate email
            candidate_phone: Candidate phone (optional, for WhatsApp)
            interview_date: Interview date (YYYY-MM-DD)
            interview_time: Interview time (HH:MM)
            panel_members: List of panel members [{name, email}, ...]
            job_title: Job title being interviewed for
            consent_whatsapp: Whether candidate consented to WhatsApp
            created_by: User who scheduled interview
            db: Database session

        Returns:
            Message ID
        """
        try:
            payload = {
                "interview_id": interview_id,
                "candidate_id": candidate_id,
                "candidate_email": candidate_email,
                "candidate_phone": candidate_phone,
                "interview_date": interview_date,
                "interview_time": interview_time,
                "panel_members": panel_members,
                "job_title": job_title,
                "consent_whatsapp": consent_whatsapp,
            }

            message_id = MessageQueueService.enqueue(
                message_type="interview_scheduled",
                payload=payload,
                resource_id=interview_id,
                created_by=created_by,
                db=db,
            )

            logger.info(f"Queued interview_scheduled: {interview_id} (message: {message_id})")
            return message_id

        except Exception as e:
            logger.error(f"Failed to queue interview_scheduled: {e}", exc_info=True)
            raise

    @staticmethod
    def queue_offer_generated(
        offer_id: str,
        candidate_id: str,
        candidate_email: str,
        position: str,
        salary: str,
        start_date: str,
        created_by: str = "system",
        db: Optional[Session] = None,
    ) -> str:
        """
        Queue offer letter and signature request.

        Args:
            offer_id: Offer UUID
            candidate_id: Candidate UUID
            candidate_email: Candidate email
            position: Position title
            salary: Salary information
            start_date: Start date (YYYY-MM-DD)
            created_by: User who generated offer
            db: Database session

        Returns:
            Message ID
        """
        try:
            payload = {
                "offer_id": offer_id,
                "candidate_id": candidate_id,
                "candidate_email": candidate_email,
                "position": position,
                "salary": salary,
                "start_date": start_date,
            }

            message_id = MessageQueueService.enqueue(
                message_type="offer_generated",
                payload=payload,
                resource_id=offer_id,
                created_by=created_by,
                db=db,
            )

            logger.info(f"Queued offer_generated: {offer_id} (message: {message_id})")
            return message_id

        except Exception as e:
            logger.error(f"Failed to queue offer_generated: {e}", exc_info=True)
            raise

    # ==================== TIMESHEET QUEUES ====================

    @staticmethod
    def queue_timesheet_submitted(
        timesheet_id: str,
        employee_id: str,
        manager_id: str,
        week: str,
        total_hours: float,
        created_by: str = "system",
        db: Optional[Session] = None,
    ) -> str:
        """
        Queue timesheet for manager approval.

        Args:
            timesheet_id: Timesheet UUID
            employee_id: Employee UUID
            manager_id: Manager UUID
            week: Week identifier (e.g., "2026-W35")
            total_hours: Total hours submitted
            created_by: User (employee)
            db: Database session

        Returns:
            Message ID
        """
        try:
            payload = {
                "timesheet_id": timesheet_id,
                "employee_id": employee_id,
                "manager_id": manager_id,
                "week": week,
                "total_hours": total_hours,
            }

            message_id = MessageQueueService.enqueue(
                message_type="timesheet_submitted",
                payload=payload,
                resource_id=timesheet_id,
                created_by=created_by,
                db=db,
            )

            logger.info(f"Queued timesheet_submitted: {timesheet_id} (message: {message_id})")
            return message_id

        except Exception as e:
            logger.error(f"Failed to queue timesheet_submitted: {e}", exc_info=True)
            raise

    # ==================== KPI QUEUES ====================

    @staticmethod
    def queue_kpi_updated(
        kpi_id: str,
        metric_type: str,
        current_value: float,
        target_value: float,
        manager_email: str,
        threshold: Optional[float] = None,
        created_by: str = "system",
        db: Optional[Session] = None,
    ) -> str:
        """
        Queue KPI update for dashboard and optional alerts.

        Args:
            kpi_id: KPI UUID
            metric_type: Type of metric (hires, revenue, commits, etc.)
            current_value: Current value
            target_value: Target value
            manager_email: Manager email for alerts
            threshold: Alert threshold (if falls below)
            created_by: System
            db: Database session

        Returns:
            Message ID
        """
        try:
            threshold_triggered = threshold and current_value < threshold

            payload = {
                "kpi_id": kpi_id,
                "metric_type": metric_type,
                "current_value": current_value,
                "target_value": target_value,
                "manager_email": manager_email,
                "threshold": threshold,
                "threshold_triggered": threshold_triggered,
            }

            message_id = MessageQueueService.enqueue(
                message_type="kpi_updated",
                payload=payload,
                resource_id=kpi_id,
                created_by=created_by,
                db=db,
            )

            logger.info(f"Queued kpi_updated: {kpi_id} (message: {message_id})")
            return message_id

        except Exception as e:
            logger.error(f"Failed to queue kpi_updated: {e}", exc_info=True)
            raise

    # ==================== SALES QUEUES ====================

    @staticmethod
    def queue_sales_deal(
        deal_id: str,
        partner_id: str,
        action: str,  # created, updated, closed, lost
        value: float,
        stage: str,
        created_by: str = "system",
        db: Optional[Session] = None,
    ) -> str:
        """
        Queue sales deal for processing and commission calculation.

        Args:
            deal_id: Deal UUID
            partner_id: Partner UUID
            action: Deal action (created, updated, closed, lost)
            value: Deal value
            stage: Deal stage
            created_by: User who created/updated deal
            db: Database session

        Returns:
            Message ID
        """
        try:
            payload = {
                "deal_id": deal_id,
                "partner_id": partner_id,
                "action": action,
                "value": value,
                "stage": stage,
            }

            message_id = MessageQueueService.enqueue(
                message_type="sales_deal",
                payload=payload,
                resource_id=deal_id,
                created_by=created_by,
                db=db,
            )

            logger.info(f"Queued sales_deal: {deal_id} (message: {message_id})")
            return message_id

        except Exception as e:
            logger.error(f"Failed to queue sales_deal: {e}", exc_info=True)
            raise

    # ==================== CLIENT QUEUES ====================

    @staticmethod
    def queue_client_contact(
        client_id: str,
        contact_name: str,
        contact_email: str,
        company: str,
        is_new_contact: bool = False,
        created_by: str = "system",
        db: Optional[Session] = None,
    ) -> str:
        """
        Queue client contact for CRM sync and follow-up.

        Args:
            client_id: Client UUID
            contact_name: Contact person name
            contact_email: Contact email
            company: Company name
            is_new_contact: Whether this is a new contact
            created_by: User who added contact
            db: Database session

        Returns:
            Message ID
        """
        try:
            payload = {
                "client_id": client_id,
                "contact_name": contact_name,
                "contact_email": contact_email,
                "company": company,
                "is_new_contact": is_new_contact,
            }

            message_id = MessageQueueService.enqueue(
                message_type="client_contact",
                payload=payload,
                resource_id=client_id,
                created_by=created_by,
                db=db,
            )

            logger.info(f"Queued client_contact: {client_id} (message: {message_id})")
            return message_id

        except Exception as e:
            logger.error(f"Failed to queue client_contact: {e}", exc_info=True)
            raise
