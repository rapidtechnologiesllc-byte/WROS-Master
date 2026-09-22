"""Message Handler: Unified Candidate Creation

Process queued candidate creation requests.
This is the ONLY place where create_candidate() actually runs.
"""

import logging
from typing import Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from app.core.logging import logger as base_logger
from app.models.channel_queue import ChannelQueueItem

logger = logging.getLogger(__name__)


class CandidateCreationUnifiedHandler:
    """Process candidate creation from queue - UNIFIED HANDLER for all sources."""

    HANDLER_NAME = "candidate_creation_unified"
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 30

    @staticmethod
    def _do_process(message: ChannelQueueItem, db: Session) -> Dict[str, Any]:
        """Internal: actual candidate creation logic (wrapped with timeout)."""
        if not message.payload:
            raise ValueError(f"Message {message.id} has no payload")

        payload = message.payload

        email = payload.get('candidate_email')
        first_name = payload.get('candidate_first_name')
        last_name = payload.get('candidate_last_name')
        mobile = payload.get('candidate_mobile')
        source = payload.get('candidate_source', 'unknown')
        tenant_id = payload.get('tenant_id', 1)

        if not all([email, first_name, last_name]):
            raise ValueError("Missing required fields: email, first_name, last_name")

        logger.info(
            f"[CandidateCreationUnified] Processing: {email} ({first_name} {last_name}), "
            f"source={source}"
        )

        # THE ONLY place create_candidate() is called
        from app.services.candidate_service import create_candidate

        candidate, is_new = create_candidate(
            db=db,
            email=email,
            mobile=mobile,
            linkedin_url=payload.get('linkedin_url'),
            candidate_id=None,
            tenant_id=tenant_id,
            candidateFirstName=first_name,
            candidateLastName=last_name,
            candidateSource=source,
            candidateRole="Candidate",
        )

        db.flush()
        candidate_id = candidate.candidateID

        logger.info(
            f"[CandidateCreationUnified] ✅ Created: {candidate_id} "
            f"(new={is_new}, source={source})"
        )

        return {
            'status': 'success',
            'candidate_id': candidate_id,
            'email': candidate.candidateEmail,
            'is_new': is_new,
            'source': source,
        }

    @staticmethod
    def process(message: ChannelQueueItem, db: Session) -> Dict[str, Any]:
        """
        Process candidate creation message from queue with timeout protection.

        This is the ONLY place where candidates are actually created
        (all queue wrappers defer to here).

        Supports all creation sources:
        - bulk_csv_import, linkedin_fast, linkedin_slow, web_chat,
          thunder_test_demo, employee_referral, progressive_upload
        """
        try:
            # Enforce timeout to prevent stuck messages
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(
                CandidateCreationUnifiedHandler._do_process,
                message,
                db
            )
            try:
                return future.result(timeout=CandidateCreationUnifiedHandler.TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                raise RuntimeError(
                    f"Candidate creation exceeded {CandidateCreationUnifiedHandler.TIMEOUT_SECONDS}s timeout"
                )
            finally:
                executor.shutdown(wait=False)

        except ValueError as e:
            logger.error(f"[CandidateCreationUnified] Validation error: {e}")
            raise
        except RuntimeError as e:
            logger.error(f"[CandidateCreationUnified] Runtime error: {e}")
            raise
        except Exception as e:
            logger.error(f"[CandidateCreationUnified] Processing error: {e}", exc_info=True)
            raise RuntimeError(f"Failed to create candidate: {str(e)}")

    @staticmethod
    def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
        """Mark message as completed after successful handler execution."""
        try:
            # Verify candidate exists
            from app.models.candidate import Candidate
            candidate_id = result.get('candidate_id')

            if not candidate_id:
                raise ValueError("Result missing candidate_id")

            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found in database")

            # Mark queue item as completed
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = result
            db.commit()

            logger.info(
                f"[CandidateCreationUnified] ✅ Message marked COMPLETED: "
                f"{message.message_id} → candidate {candidate_id}"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateCreationUnified] on_success error: {e}", exc_info=True)
            raise

    @staticmethod
    def on_retry(message: ChannelQueueItem, error: str, db: Session) -> None:
        """Schedule message for retry."""
        try:
            db.rollback()
            message.retry_count += 1
            message.error = error[:1000]

            if message.retry_count < CandidateCreationUnifiedHandler.MAX_RETRIES:
                from datetime import timedelta
                message.next_retry_at = datetime.utcnow() + timedelta(minutes=5)
                message.status = "PENDING"  # Retry
            else:
                message.status = "FAILED"  # Max retries exhausted
                message.completed_at = datetime.utcnow()

            db.commit()
            logger.info(
                f"[CandidateCreationUnified] Message retry scheduled: "
                f"{message.message_id} (attempt {message.retry_count})"
            )

        except Exception as e:
            db.rollback()
            logger.error(f"[CandidateCreationUnified] on_retry error: {e}", exc_info=True)

    @staticmethod
    def on_failed(message: ChannelQueueItem, final_error: str, db: Session) -> None:
        """Mark message as permanently failed."""
        try:
            db.rollback()
            message.status = "FAILED"
            message.error = final_error[:1000]
            message.completed_at = datetime.utcnow()
            db.commit()

            logger.error(
                f"[CandidateCreationUnified] ❌ Message marked FAILED: "
                f"{message.message_id} - {final_error[:200]}"
            )

        except Exception as e:
            logger.error(f"[CandidateCreationUnified] on_failed error: {e}", exc_info=True)
