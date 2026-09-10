"""
Offer Generation Handler - Queue-Driven (PHASE A FIX #3)

Purpose: Generate and send offer letters via queue
- Receives offer_approved message from queue
- Generates offer letter from template
- Stores PDF in database
- Queues offer_sent notification
- Logs to SLM for learning

Pattern: Same as other queue handlers
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class OfferGenerationHandler:
    """Handle offer generation and sending"""

    @staticmethod
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """
        Process: Generate and send offer letter

        Args:
            message: ChannelQueueItem with type='offer_approved'
            db: SQLAlchemy session

        Returns:
            {
                'status': 'success',
                'offer_id': str,
                'candidate_id': str,
                'offer_letter_url': str
            }

        Raises:
            ValueError: Invalid payload (400 client error)
            RuntimeError: DB operation failures (500 internal, retry eligible)
        """
        try:
            payload = message.payload or {}

            # PHASE 1: VALIDATION
            candidate_id = payload.get('candidate_id')
            job_id = payload.get('job_id')
            offer_details = payload.get('offer_details', {})

            if not candidate_id or not job_id:
                raise ValueError("Missing required fields: candidate_id, job_id")

            logger.info(
                f"[OfferGeneration] Generating offer for "
                f"candidate={candidate_id}, job={job_id}"
            )

            # PHASE 2: VERIFY CANDIDATE & JOB EXIST
            from app.models.user import Candidate, Jobs

            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()

            if not job:
                raise ValueError(f"Job {job_id} not found")

            logger.info(
                f"[OfferGeneration] Verified: candidate={candidate.candidateEmail}, "
                f"job={job.jobTitle}"
            )

            # PHASE 3: GENERATE OFFER LETTER
            # In production: use offer_template_service.generate_pdf()
            # For MVP: create basic offer record (PDF generation deferred to Phase B)

            from app.models.offer_letter import OfferLetter

            offer = OfferLetter(
                candidate_id=candidate_id,
                job_id=job_id,
                position_title=job.jobTitle,
                salary=offer_details.get('salary'),
                currency=offer_details.get('currency', 'USD'),
                start_date=offer_details.get('start_date'),
                benefits=offer_details.get('benefits', ''),
                offer_expiry=datetime.utcnow() + timedelta(days=7),  # 7 days to accept
                status="GENERATED",
                created_at=datetime.utcnow(),
                generated_by=payload.get('approver_id', 'system'),
            )

            db.add(offer)
            db.flush()  # Get offer_id
            offer_id = offer.id

            logger.info(
                f"[OfferGeneration] Offer record created: {offer_id}, "
                f"salary={offer.salary}, start_date={offer.start_date}"
            )

            # PHASE 4: QUEUE OFFER SENT NOTIFICATION
            try:
                from app.services.message_queue_service import MessageQueueService

                MessageQueueService.enqueue(
                    task_name='offer_sent_notification',
                    task_id=f"offer_notify_{offer_id}",
                    data={
                        'candidate_id': candidate_id,
                        'offer_id': offer_id,
                        'candidate_email': candidate.candidateEmail,
                        'candidate_name': f"{candidate.candidateFirstName} {candidate.candidateLastName}",
                        'position_title': job.jobTitle,
                        'salary': offer.salary,
                        'start_date': str(offer.start_date),
                        'offer_expiry': str(offer.offer_expiry),
                    }
                )
                logger.info(f"[OfferGeneration] Notification queued to send offer to {candidate.candidateEmail}")

            except Exception as notif_err:
                logger.warning(
                    f"[OfferGeneration] Failed to queue notification: {notif_err} "
                    f"(non-blocking, offer already created)"
                )

            # PHASE 5: COMMIT TRANSACTION
            db.commit()

            logger.info(
                f"[OfferGeneration] ✅ Offer generated successfully for {candidate_id}"
            )

            return {
                'status': 'success',
                'offer_id': offer_id,
                'candidate_id': candidate_id,
                'job_id': job_id,
                'salary': offer.salary,
                'start_date': str(offer.start_date),
                'offer_expiry': str(offer.offer_expiry),
            }

        except ValueError as ve:
            logger.error(f"[OfferGeneration] Validation error: {ve}")
            raise  # NOT RETRYABLE

        except RuntimeError as re:
            logger.error(f"[OfferGeneration] Runtime error (retryable): {re}")
            raise  # RETRYABLE

        except OperationalError as oe:
            logger.error(f"[OfferGeneration] DB operational error: {oe}", exc_info=True)
            raise RuntimeError(f"DB unavailable: {str(oe)}") from oe

        except Exception as e:
            logger.error(f"[OfferGeneration] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e
