"""
Handler Validation Template - Reference Implementation

This file serves as the canonical template for implementing validation in queue handlers.
Copy this pattern to all handlers that mark messages as COMPLETED.

CRITICAL RULE:
- Do NOT mark COMPLETED without validation
- Always verify work actually happened in database
- Raise exceptions if validation fails (don't silently fail)
- Use RuntimeError for retryable errors, ValueError for non-retryable
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session
from app.core.logging import logger
from app.models.channel_queue import ChannelQueueItem


class HandlerValidationTemplate:
    """
    Reference implementation for handler validation pattern.

    Copy this structure to all handlers:

    1. process() - Do the work, return result dict
    2. on_success() - VALIDATE work, then mark COMPLETED
    3. on_retry() - Schedule retry if retryable error
    4. on_failed() - Mark FAILED if all retries exhausted
    """

    # Handler configuration
    MAX_RETRIES = 5
    RETRY_DELAY_MINUTES = 30

    @staticmethod
    def process(message: ChannelQueueItem, db: Session) -> Dict[str, Any]:
        """
        Execute the actual work.

        Returns:
            Dictionary with structure:
            {
                'status': 'success',
                'record_id': 'unique_id',
                'email': 'example@test.com',  # Other fields handler verified
            }

        Raises:
            Any exception - handler will handle retry/failure
        """
        if not message.payload:
            raise ValueError(f"Message {message.id} has no payload")

        payload = message.payload
        logger.info(f"[Handler] Processing message, payload keys={list(payload.keys())}")

        try:
            # ====== STEP 1: Do the actual work ======
            # Create record, send message, call API, etc.
            record = create_your_record(payload, db)

            # ====== STEP 2: Get record ID from result ======
            record_id = record.id if hasattr(record, 'id') else record.get('id')

            # ====== STEP 3: Return result dict for on_success() to validate ======
            result = {
                'status': 'success',
                'record_id': record_id,
                'email': payload.get('email'),  # Include fields for validation
                'other_field': 'value'
            }

            logger.info(f"[Handler] Work completed, returning result for validation")
            return result

        except Exception as e:
            logger.error(f"[Handler] Work failed: {e}", exc_info=True)
            raise  # Let queue processor handle retry


    @staticmethod
    def on_success(message: ChannelQueueItem, result: Dict[str, Any], db: Session) -> None:
        """
        Validate work completed before marking COMPLETED.

        CRITICAL: This method MUST verify:
        1. Result structure is valid
        2. Records actually exist in database
        3. Related records are consistent
        4. No data corruption occurred

        If ANY validation fails, raise an exception.
        NEVER mark COMPLETED without full validation.

        Raises:
            ValueError - Non-retryable error (handler bug, don't retry)
            RuntimeError - Retryable error (temporary DB issue, will retry)
        """
        try:
            logger.info(f"[Handler] Validating result before marking COMPLETED")

            # ========== VALIDATION STEP 1: Check result structure ==========
            if not isinstance(result, dict):
                raise ValueError(f"Handler returned invalid type: {type(result)}")

            required_fields = ['record_id', 'email']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Handler result missing required field: {field}")
                if not result[field]:
                    raise ValueError(f"Handler result has empty field: {field}")

            record_id = result['record_id']
            email = result['email']

            logger.info(
                f"[Handler] ✅ Step 1: Result structure valid "
                f"(record_id={record_id}, email={email})"
            )

            # ========== VALIDATION STEP 2: Database verification ==========
            # Query database to verify record actually exists
            from app.models.candidate import Candidate  # Import your model

            candidate = db.query(Candidate).filter(
                Candidate.candidateID == record_id
            ).first()

            if not candidate:
                raise RuntimeError(
                    f"Record {record_id} not found in database after handler completed. "
                    f"Handler returned ID but record was not persisted."
                )

            logger.info(f"[Handler] ✅ Step 2: Database verification passed, record exists")

            # ========== VALIDATION STEP 3: Related records consistency ==========
            # Check that dependent records exist (status, links, etc.)
            from app.models.candidate import CandidateStatus

            status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == record_id
            ).first()

            if not status:
                raise RuntimeError(
                    f"Required status record missing for {record_id}. "
                    f"Candidate exists but status was not created."
                )

            if status.piplineStatus != "Applied":
                raise RuntimeError(
                    f"Status is '{status.piplineStatus}', expected 'Applied'. "
                    f"Pipeline state incorrect."
                )

            logger.info(f"[Handler] ✅ Step 3: Related records valid, status exists and correct")

            # ========== VALIDATION STEP 4: Data integrity ==========
            # Verify fields match what handler was supposed to do
            if candidate.candidateEmail != email:
                raise RuntimeError(
                    f"Email mismatch: handler returned '{email}' "
                    f"but database has '{candidate.candidateEmail}'. "
                    f"Data corruption detected."
                )

            # Compare other payload fields if applicable
            payload = message.payload
            if payload.get('mobile') and candidate.candidateMobile != payload.get('mobile'):
                logger.warning(
                    f"Mobile mismatch for {record_id}: "
                    f"expected {payload.get('mobile')}, got {candidate.candidateMobile}"
                )
                # Note: Log warning but don't fail - mobile might have been updated elsewhere
                # Only fail if CRITICAL fields don't match

            logger.info(f"[Handler] ✅ Step 4: Data integrity verified, fields match")

            # ========== FINAL: Mark COMPLETED after all validations pass ==========
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = json.dumps(result)

            try:
                db.commit()
            except Exception as commit_err:
                db.rollback()
                raise RuntimeError(f"Failed to commit success status: {str(commit_err)}") from commit_err

            logger.info(f"[Handler] ✅✅✅ ALL VALIDATIONS PASSED - Message marked COMPLETED")
            logger.info(f"[Handler] Record {record_id} verified in database, all checks passed")

        except ValueError as e:
            # Non-retryable error (handler code bug, don't retry)
            db.rollback()
            logger.error(f"[Handler] ❌ NON-RETRYABLE validation failure: {e}")
            raise  # Queue processor will mark as FAILED, no retry

        except RuntimeError as e:
            # Retryable error (temporary DB issue, connection problem, etc.)
            db.rollback()
            logger.error(f"[Handler] ❌ RETRYABLE validation failure: {e}")
            raise  # Queue processor will retry

        except Exception as e:
            # Unexpected error (probably DB connection issue, treat as retryable)
            db.rollback()
            logger.error(f"[Handler] ❌ Unexpected validation error: {e}", exc_info=True)
            raise RuntimeError(f"Validation error: {str(e)}") from e


    @staticmethod
    def should_retry(message: ChannelQueueItem) -> bool:
        """Determine if message should be retried."""
        if message.retry_count >= HandlerValidationTemplate.MAX_RETRIES:
            logger.error(f"[Handler] Max retries exceeded for {message.id}")
            return False

        if message.next_retry_at and datetime.utcnow() < message.next_retry_at:
            return False

        return True


    @staticmethod
    def on_retry(message: ChannelQueueItem, error: str, db: Session) -> None:
        """Schedule message for retry after failed attempt."""
        from datetime import timedelta

        try:
            db.rollback()  # Clear any failed transaction

            message.retry_count += 1
            message.error = error[:1000]  # Truncate long error messages
            message.next_retry_at = datetime.utcnow() + timedelta(
                minutes=HandlerValidationTemplate.RETRY_DELAY_MINUTES
            )

            db.commit()
            logger.info(
                f"[Handler] Scheduled retry for {message.id}: "
                f"retry_count={message.retry_count}/{HandlerValidationTemplate.MAX_RETRIES}, "
                f"next_retry_at={message.next_retry_at}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[Handler] Failed to schedule retry: {e}", exc_info=True)
            raise RuntimeError(f"Failed to schedule retry: {str(e)}") from e


    @staticmethod
    def on_failed(message: ChannelQueueItem, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        try:
            db.rollback()  # Clear any failed transaction

            message.status = "FAILED"
            message.error = final_error[:1000]  # Truncate long error messages
            message.completed_at = datetime.utcnow()

            db.commit()
            logger.error(
                f"[Handler] Message {message.id} FAILED after "
                f"{message.retry_count} retries: {final_error}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[Handler] Failed to mark as FAILED: {e}", exc_info=True)
            raise


# ============================================================================
# HOW TO USE THIS TEMPLATE
# ============================================================================
"""
For each handler (e.g., CandidateCreationHandler, CandidateConversionHandler):

1. Copy the on_success() method structure
2. Replace Model/fields with your actual models and queries
3. Define required_fields at top of on_success()
4. Add validation checks:
   - Check 1: Result structure (required fields exist and not null)
   - Check 2: Primary record exists in database
   - Check 3: Related records exist (FKs, status, etc.)
   - Check 4: Data matches payload (detect corruption)
5. Raise ValueError for non-retryable errors
6. Raise RuntimeError for retryable errors
7. NEVER mark COMPLETED without full validation
8. ALWAYS rollback if validation fails

Example for CandidateCreationHandler:

class CandidateCreationHandler:
    @staticmethod
    def on_success(message, result, db):
        try:
            # STEP 1: Check result structure
            if 'candidate_id' not in result:
                raise ValueError("Missing candidate_id")

            candidate_id = result['candidate_id']

            # STEP 2: Database verification
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise RuntimeError(f"Candidate {candidate_id} not in database")

            # STEP 3: Related records
            status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == candidate_id
            ).first()

            if not status:
                raise RuntimeError(f"Status missing for {candidate_id}")

            # STEP 4: Data integrity
            if candidate.candidateEmail != message.payload.get('candidate_email'):
                raise RuntimeError(f"Email mismatch")

            # FINAL: Mark COMPLETED
            message.status = "COMPLETED"
            message.completed_at = datetime.utcnow()
            message.result = json.dumps(result)
            db.commit()

        except ValueError as e:
            db.rollback()
            logger.error(f"Non-retryable: {e}")
            raise
        except RuntimeError as e:
            db.rollback()
            logger.error(f"Retryable: {e}")
            raise
"""


def create_your_record(payload: dict, db: Session) -> Any:
    """Placeholder for actual record creation logic."""
    # Replace with your actual handler logic
    pass
