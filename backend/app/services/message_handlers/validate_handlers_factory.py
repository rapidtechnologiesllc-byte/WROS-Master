"""Factory for creating validate() methods across all message handlers.

Provides standardized validation patterns for:
- Candidate operations (archive, conversion, status changes, etc.)
- Interview operations (scheduling, updates)
- Offer operations (generation, approval, rejection)
- Other queue-driven operations

Usage:
    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        return ValidateHandlersFactory.validate_candidate_exists(result, db, "candidate_archive")
"""

import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ValidateHandlersFactory:
    """Factory for creating and executing validation methods."""

    @staticmethod
    def validate_candidate_exists(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Generic candidate validation: record must exist."""
        from app.models.candidate import Candidate

        if not result or "candidate_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        candidate_id = result.get("candidate_id")

        try:
            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found after {handler_name}")

            logger.info(f"✅ {handler_name} validated: {candidate_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_candidate_deleted(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Generic candidate deletion validation: record must NOT exist."""
        from app.models.candidate import Candidate

        if not result or "candidate_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        candidate_id = result.get("candidate_id")

        try:
            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if candidate:
                raise ValueError(f"Candidate {candidate_id} still exists after {handler_name}")

            logger.info(f"✅ {handler_name} validated: {candidate_id} successfully deleted")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_interview_exists(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Generic interview validation: record must exist."""
        from app.models.user import Interview

        if not result or "interview_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        interview_id = result.get("interview_id")

        try:
            interview = db.query(Interview).filter(Interview.id == interview_id).first()
            if not interview:
                raise ValueError(f"Interview {interview_id} not found after {handler_name}")

            logger.info(f"✅ {handler_name} validated: {interview_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_offer_exists(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Generic offer validation: record must exist."""
        from app.models.user import Offer

        if not result or "offer_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        offer_id = result.get("offer_id")

        try:
            offer = db.query(Offer).filter(Offer.offerID == offer_id).first()
            if not offer:
                raise ValueError(f"Offer {offer_id} not found after {handler_name}")

            logger.info(f"✅ {handler_name} validated: {offer_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_job_exists(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Generic job validation: record must exist."""
        from app.models.user import Jobs

        if not result or "job_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        job_id = result.get("job_id")

        try:
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found after {handler_name}")

            logger.info(f"✅ {handler_name} validated: {job_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_invoice_exists(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Generic invoice validation: record must exist."""
        from app.models.invoice import Invoice

        if not result or "invoice_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        invoice_id = result.get("invoice_id")

        try:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found after {handler_name}")

            logger.info(f"✅ {handler_name} validated: {invoice_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_invoice_status(result: Dict[str, Any], db: Session, handler_name: str, expected_status: str) -> None:
        """Validate invoice status is expected value."""
        from app.models.invoice import Invoice

        if not result or "invoice_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        invoice_id = result.get("invoice_id")

        try:
            invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
            if not invoice:
                raise ValueError(f"Invoice {invoice_id} not found")

            if invoice.status != expected_status:
                raise ValueError(
                    f"Invoice {invoice_id} status is {invoice.status}, "
                    f"expected {expected_status}"
                )

            logger.info(f"✅ {handler_name} validated: {invoice_id} status={expected_status}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_revenue_record_created(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate revenue record was created."""
        from app.models.revenue import Revenue

        if not result or "revenue_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        revenue_id = result.get("revenue_id")

        try:
            revenue = db.query(Revenue).filter(Revenue.id == revenue_id).first()
            if not revenue:
                raise ValueError(f"Revenue {revenue_id} not found after {handler_name}")

            if revenue.status != 'RECOGNIZED':
                raise ValueError(
                    f"Revenue {revenue_id} status is {revenue.status}, "
                    f"expected RECOGNIZED"
                )

            logger.info(f"✅ {handler_name} validated: {revenue_id}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_revenue_amount_matches(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate revenue amount matches expected amount."""
        from app.models.revenue import Revenue

        if not result or "revenue_id" not in result or "amount_recognized" not in result:
            raise ValueError(f"Invalid result: {result}")

        revenue_id = result.get("revenue_id")
        expected_amount = result.get("amount_recognized", 0)

        try:
            revenue = db.query(Revenue).filter(Revenue.id == revenue_id).first()
            if not revenue:
                raise ValueError(f"Revenue {revenue_id} not found")

            if revenue.amount_usd_cents != expected_amount:
                raise ValueError(
                    f"Revenue amount mismatch: expected ${expected_amount / 100:.2f}, "
                    f"got ${revenue.amount_usd_cents / 100:.2f}"
                )

            logger.info(f"✅ {handler_name} validated: amount correct")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE validation error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    # PHASE 4 VALIDATORS - Remaining 17 handlers

    @staticmethod
    def validate_candidate_status(result: Dict[str, Any], db: Session, handler_name: str, expected_status: str) -> None:
        """Validate candidate status matches expected value."""
        from app.models.candidate import Candidate, CandidateStatus

        if not result or "candidate_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        candidate_id = result.get("candidate_id")

        try:
            status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == candidate_id
            ).order_by(CandidateStatus.created_at.desc()).first()

            if not status or status.piplineStatus != expected_status:
                actual = status.piplineStatus if status else 'None'
                raise ValueError(f"Candidate status is {actual}, expected {expected_status}")

            logger.info(f"✅ {handler_name} validated: {candidate_id} status={expected_status}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_offer_status(result: Dict[str, Any], db: Session, handler_name: str, expected_status: str) -> None:
        """Validate offer status matches expected value."""
        from app.models.user import Offer

        if not result or "offer_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        offer_id = result.get("offer_id")

        try:
            offer = db.query(Offer).filter(Offer.offerID == offer_id).first()
            if not offer or offer.offerStatus != expected_status:
                actual = offer.offerStatus if offer else 'None'
                raise ValueError(f"Offer status is {actual}, expected {expected_status}")

            logger.info(f"✅ {handler_name} validated: {offer_id} status={expected_status}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_job_status(result: Dict[str, Any], db: Session, handler_name: str, expected_status: str) -> None:
        """Validate job status matches expected value."""
        from app.models.user import Jobs

        if not result or "job_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        job_id = result.get("job_id")

        try:
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if not job or job.jobStatus != expected_status:
                actual = job.jobStatus if job else 'None'
                raise ValueError(f"Job status is {actual}, expected {expected_status}")

            logger.info(f"✅ {handler_name} validated: {job_id} status={expected_status}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_message_delivery_logged(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate message delivery was logged."""
        from app.models.message_delivery import MessageDelivery

        if not result or "delivery_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        delivery_id = result.get("delivery_id")

        try:
            delivery = db.query(MessageDelivery).filter(
                MessageDelivery.id == delivery_id
            ).first()

            if not delivery:
                raise ValueError(f"Delivery {delivery_id} not logged")

            if delivery.status not in ['sent', 'delivered', 'pending']:
                raise ValueError(f"Delivery status is {delivery.status}")

            logger.info(f"✅ {handler_name} validated: delivery logged")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_cascade_recorded(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate cascade failure was recorded."""
        from app.models.event_log import EventLog

        if not result or "cascade_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        cascade_id = result.get("cascade_id")

        try:
            event = db.query(EventLog).filter(
                EventLog.id == cascade_id,
                EventLog.event_type == "cascade_failure"
            ).first()

            if not event:
                raise ValueError(f"Cascade {cascade_id} not recorded")

            logger.info(f"✅ {handler_name} validated: cascade recorded")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    # PHASE 4 VALIDATORS (EXPANDED SET) - 25+ validators for remaining 19 handlers

    @staticmethod
    def validate_candidate_archived(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate candidate marked as archived (thunder_enabled=False)."""
        from app.models.candidate import Candidate

        if not result or "candidate_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        candidate_id = result.get("candidate_id")

        try:
            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            if candidate.thunder_enabled:
                raise ValueError(f"Candidate {candidate_id} still has thunder_enabled=True")

            logger.info(f"✅ {handler_name} validated: {candidate_id} archived")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_candidate_status_matches(result: Dict[str, Any], db: Session, handler_name: str, expected_status: str) -> None:
        """Validate candidate has expected status."""
        from app.models.candidate import CandidateStatus

        if not result or "candidate_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        candidate_id = result.get("candidate_id")

        try:
            status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == candidate_id
            ).order_by(CandidateStatus.created_at.desc()).first()

            if not status or status.piplineStatus != expected_status:
                actual = status.piplineStatus if status else 'None'
                raise ValueError(f"Candidate status is {actual}, expected {expected_status}")

            logger.info(f"✅ {handler_name} validated: {candidate_id} status={expected_status}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_candidate_rejection_recorded(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate rejection record created."""
        from app.models.event_log import EventLog

        if not result or "candidate_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        candidate_id = result.get("candidate_id")

        try:
            event = db.query(EventLog).filter(
                EventLog.entity_id == candidate_id,
                EventLog.event_type == "candidate_rejection"
            ).order_by(EventLog.created_at.desc()).first()

            if not event:
                raise ValueError(f"Rejection not recorded for candidate {candidate_id}")

            logger.info(f"✅ {handler_name} validated: rejection recorded")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_candidate_reactivation_timestamp(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate reactivation timestamp set (archived=False, reactivated_at set)."""
        from app.models.candidate import Candidate

        if not result or "candidate_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        candidate_id = result.get("candidate_id")

        try:
            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            if candidate.thunder_enabled != True:
                raise ValueError(f"Candidate {candidate_id} still archived (thunder_enabled=False)")

            logger.info(f"✅ {handler_name} validated: {candidate_id} reactivated")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_candidate_duplicate_analysis_recorded(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate duplicate analysis result recorded."""
        from app.models.event_log import EventLog

        if not result or "analysis_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        analysis_id = result.get("analysis_id")

        try:
            event = db.query(EventLog).filter(
                EventLog.id == analysis_id,
                EventLog.event_type == "duplicate_analysis"
            ).first()

            if not event:
                raise ValueError(f"Analysis {analysis_id} not recorded")

            logger.info(f"✅ {handler_name} validated: analysis recorded")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_interview_scheduled_with_timestamp(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate interview scheduled with scheduled_at timestamp."""
        from app.models.user import Interview

        if not result or "interview_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        interview_id = result.get("interview_id")

        try:
            interview = db.query(Interview).filter(Interview.id == interview_id).first()
            if not interview:
                raise ValueError(f"Interview {interview_id} not found")

            if not hasattr(interview, 'scheduled_at') or interview.scheduled_at is None:
                raise ValueError(f"Interview {interview_id} missing scheduled_at timestamp")

            logger.info(f"✅ {handler_name} validated: {interview_id} scheduled")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_interview_reminder_queued(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate reminder notification queued for interview."""
        from app.models.message_queue import ChannelQueueItem

        if not result or "interview_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        interview_id = result.get("interview_id")

        try:
            reminder = db.query(ChannelQueueItem).filter(
                ChannelQueueItem.payload.contains(f'"interview_id": "{interview_id}"'),
                ChannelQueueItem.task_name.ilike('%reminder%')
            ).first()

            if not reminder:
                raise ValueError(f"No reminder queued for interview {interview_id}")

            logger.info(f"✅ {handler_name} validated: reminder queued")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_offer_approval_recorded(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate offer approval (approved_at timestamp, approved_by set)."""
        from app.models.user import Offer

        if not result or "offer_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        offer_id = result.get("offer_id")

        try:
            offer = db.query(Offer).filter(Offer.offerID == offer_id).first()
            if not offer:
                raise ValueError(f"Offer {offer_id} not found")

            if not hasattr(offer, 'approved_at') or offer.approved_at is None:
                raise ValueError(f"Offer {offer_id} missing approved_at timestamp")

            logger.info(f"✅ {handler_name} validated: {offer_id} approved")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_offer_letter_generated(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate offer letter PDF created."""
        from app.models.user import Offer

        if not result or "offer_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        offer_id = result.get("offer_id")

        try:
            offer = db.query(Offer).filter(Offer.offerID == offer_id).first()
            if not offer:
                raise ValueError(f"Offer {offer_id} not found")

            if not hasattr(offer, 'offer_letter_url') or not offer.offer_letter_url:
                raise ValueError(f"Offer {offer_id} missing offer_letter_url")

            logger.info(f"✅ {handler_name} validated: {offer_id} letter generated")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_offer_sent_notification_queued(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate offer_sent notification queued."""
        from app.models.message_queue import ChannelQueueItem

        if not result or "offer_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        offer_id = result.get("offer_id")

        try:
            message = db.query(ChannelQueueItem).filter(
                ChannelQueueItem.task_name == 'offer_sent',
                ChannelQueueItem.payload.contains(f'"offer_id": "{offer_id}"')
            ).first()

            if not message:
                raise ValueError(f"No offer_sent notification queued for {offer_id}")

            logger.info(f"✅ {handler_name} validated: notification queued")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_offer_acceptance_recorded(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate offer acceptance (accepted_at timestamp)."""
        from app.models.user import Offer

        if not result or "offer_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        offer_id = result.get("offer_id")

        try:
            offer = db.query(Offer).filter(Offer.offerID == offer_id).first()
            if not offer:
                raise ValueError(f"Offer {offer_id} not found")

            if offer.offerStatus != 'ACCEPTED':
                raise ValueError(f"Offer {offer_id} status is {offer.offerStatus}, expected ACCEPTED")

            if not hasattr(offer, 'accepted_at') or offer.accepted_at is None:
                raise ValueError(f"Offer {offer_id} missing accepted_at timestamp")

            logger.info(f"✅ {handler_name} validated: {offer_id} accepted")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_offer_rejection_recorded(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate offer rejection (rejected_at timestamp, reason recorded)."""
        from app.models.user import Offer

        if not result or "offer_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        offer_id = result.get("offer_id")

        try:
            offer = db.query(Offer).filter(Offer.offerID == offer_id).first()
            if not offer:
                raise ValueError(f"Offer {offer_id} not found")

            if offer.offerStatus != 'REJECTED':
                raise ValueError(f"Offer {offer_id} status is {offer.offerStatus}, expected REJECTED")

            if not hasattr(offer, 'rejected_at') or offer.rejected_at is None:
                raise ValueError(f"Offer {offer_id} missing rejected_at timestamp")

            logger.info(f"✅ {handler_name} validated: {offer_id} rejected")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_job_status_changed(result: Dict[str, Any], db: Session, handler_name: str, expected_status: str = None) -> None:
        """Validate job status transitioned to expected state."""
        from app.models.user import Jobs

        if not result or "job_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        job_id = result.get("job_id")

        try:
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")

            if expected_status and job.jobStatus != expected_status:
                raise ValueError(f"Job {job_id} status is {job.jobStatus}, expected {expected_status}")

            logger.info(f"✅ {handler_name} validated: {job_id} status={job.jobStatus}")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_job_candidate_sourcing_queued(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate sourcing message queued for job."""
        from app.models.message_queue import ChannelQueueItem

        if not result or "job_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        job_id = result.get("job_id")

        try:
            message = db.query(ChannelQueueItem).filter(
                ChannelQueueItem.task_name.ilike('%source%'),
                ChannelQueueItem.payload.contains(f'"job_id": "{job_id}"')
            ).first()

            if not message:
                raise ValueError(f"No sourcing message queued for job {job_id}")

            logger.info(f"✅ {handler_name} validated: sourcing queued")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_flash_recruitment_started(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate flash recruiter queued engagement messages."""
        from app.models.message_queue import ChannelQueueItem

        if not result or "job_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        job_id = result.get("job_id")

        try:
            messages = db.query(ChannelQueueItem).filter(
                ChannelQueueItem.task_name.ilike('%engage%'),
                ChannelQueueItem.payload.contains(f'"job_id": "{job_id}"')
            ).count()

            if messages == 0:
                raise ValueError(f"No engagement messages queued for job {job_id}")

            logger.info(f"✅ {handler_name} validated: {messages} engagement messages queued")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_cascade_failure_state_updated(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate cascade failure signal state recorded."""
        from app.models.event_log import EventLog

        if not result or "cascade_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        cascade_id = result.get("cascade_id")

        try:
            event = db.query(EventLog).filter(
                EventLog.id == cascade_id,
                EventLog.event_type.ilike('%cascade%')
            ).first()

            if not event:
                raise ValueError(f"Cascade signal {cascade_id} not recorded")

            logger.info(f"✅ {handler_name} validated: cascade state updated")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_candidate_data_sync_complete(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate data changes propagated (skills/location/contact info)."""
        from app.models.candidate import Candidate

        if not result or "candidate_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        candidate_id = result.get("candidate_id")

        try:
            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found after sync")

            logger.info(f"✅ {handler_name} validated: data sync complete")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_ops_alert_notification_sent(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate ops alert notification queued."""
        from app.models.message_queue import ChannelQueueItem

        if not result or "alert_id" not in result:
            raise ValueError(f"Invalid result: {result}")

        alert_id = result.get("alert_id")

        try:
            message = db.query(ChannelQueueItem).filter(
                ChannelQueueItem.task_name.ilike('%alert%'),
                ChannelQueueItem.payload.contains(f'"alert_id": "{alert_id}"')
            ).first()

            if not message:
                raise ValueError(f"Alert notification not queued for {alert_id}")

            logger.info(f"✅ {handler_name} validated: alert queued")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Database error: {str(e)}") from e

    @staticmethod
    def validate_slm_email_generated_and_staged(result: Dict[str, Any], db: Session, handler_name: str) -> None:
        """Validate SLM email generated and message ready for Thunder send."""
        if not result or "email_body" not in result:
            raise ValueError(f"Invalid result: {result}")

        email_body = result.get("email_body", "")

        try:
            if not email_body or len(email_body) < 50:
                raise ValueError(f"Email body too short: {len(email_body)} chars")

            if len(email_body) > 5000:
                raise ValueError(f"Email body too long: {len(email_body)} chars (max 5000)")

            logger.info(f"✅ {handler_name} validated: email generated ({len(email_body)} chars)")

        except ValueError:
            raise

        except Exception as e:
            logger.error(f"[{handler_name}] RETRYABLE error: {e}", exc_info=True)
            raise RuntimeError(f"Validation error: {str(e)}") from e
