"""Handler: Duplicate Candidate Analysis Events."""
import logging
from typing import Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from app.models.candidate import Candidate
from app.services.message_handlers.base_message_handler import time_bound

logger = logging.getLogger(__name__)


class DuplicateCandidateAnalysisHandler:
    """Handles duplicate candidate analysis events."""

    MAX_RETRIES = 3
    RETRY_DELAY_MINUTES = 15

    @staticmethod
    @time_bound(timeout_seconds=8)
    def process(message: Any, db: Session) -> Dict[str, Any]:
        """Process duplicate candidate detection and analysis.

        Args:
            message: ChannelQueueItem with type='duplicate_candidate_analysis'
            db: SQLAlchemy session

        Returns:
            Handler result: {"status": "processed", "intent_score": 75, "engagement_level": "medium"}
        """
        try:
            payload = message.payload or {}
            candidate_id = payload.get("candidate_id")
            data = payload.get("data", {})
            duplicate_count = data.get("duplicate_count", 1)
            job_types = data.get("job_types", [])

            # Fetch candidate
            candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            # Calculate intent score
            intent_score = _calculate_intent_score(duplicate_count, job_types)

            # Determine engagement level
            if intent_score >= 80:
                engagement_level = "high"
                logger.info(f"[DuplicateAnalysis] Candidate {candidate_id}: HIGH intent (score: {intent_score})")
            elif intent_score >= 50:
                engagement_level = "medium"
                logger.info(f"[DuplicateAnalysis] Candidate {candidate_id}: MEDIUM intent (score: {intent_score})")
            else:
                engagement_level = "low"
                logger.info(f"[DuplicateAnalysis] Candidate {candidate_id}: LOW intent (score: {intent_score})")

            db.commit()

            return {
                "status": "processed",
                "candidate_id": candidate_id,
                "duplicate_count": duplicate_count,
                "intent_score": intent_score,
                "engagement_level": engagement_level,
                "actions": ["calculated_intent", "adjusted_engagement_level"]
            }

        except ValueError as ve:
            logger.error(f"[DuplicateAnalysis] Validation error: {ve}")
            raise
        except OperationalError as oe:
            logger.error(f"[DuplicateAnalysis] DB error: {oe}", exc_info=True)
            raise RuntimeError(f"Database error: {str(oe)}") from oe
        except Exception as e:
            logger.error(f"[DuplicateAnalysis] Unexpected error: {e}", exc_info=True)
            raise RuntimeError(f"Unexpected error: {str(e)}") from e

    @staticmethod
    def validate(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Validate that duplicate analysis was recorded successfully."""
        from app.services.message_handlers.validate_handlers_factory import ValidateHandlersFactory
        return ValidateHandlersFactory.validate_candidate_duplicate_analysis_recorded(result, db, "duplicate_analysis")

    @staticmethod
    def should_retry(message: Any) -> bool:
        """Determine if message should be retried."""
        return message.retry_count < DuplicateCandidateAnalysisHandler.MAX_RETRIES

    @staticmethod
    def on_retry(message: Any, error: str, db: Session) -> None:
        """Schedule message for retry."""
        db.rollback()
        message.retry_count += 1
        message.error = error[:1000]
        message.next_retry_at = datetime.utcnow() + timedelta(minutes=DuplicateCandidateAnalysisHandler.RETRY_DELAY_MINUTES)
        db.commit()

    @staticmethod
    def on_success(message: Any, result: Dict[str, Any], db: Session) -> None:
        """Mark message as COMPLETED after validation passes."""
        DuplicateCandidateAnalysisHandler.validate(message, result, db)
        message.status = "COMPLETED"
        message.completed_at = datetime.utcnow()
        db.commit()

    @staticmethod
    def on_failed(message: Any, final_error: str, db: Session) -> None:
        """Mark message as FAILED after all retries exhausted."""
        db.rollback()
        message.status = "FAILED"
        message.error = final_error[:1000]
        message.completed_at = datetime.utcnow()
        db.commit()


def _calculate_intent_score(duplicate_count: int, job_types: list) -> int:
    """Calculate intent score based on application patterns.

    Args:
        duplicate_count: Number of times candidate applied
        job_types: List of job types applied for

    Returns:
        Intent score 0-100
    """
    if duplicate_count <= 1:
        return 50  # Single application = medium intent

    if not job_types:
        # Multiple applications, unknown types
        return 50 + (min(duplicate_count - 1, 3) * 10)  # 50-80 based on count

    # Check if applications are to similar or different roles
    unique_types = len(set(job_types))

    if unique_types == 1:
        # Multiple applications to same job type = HIGH intent
        base_score = 85
        return min(base_score + (duplicate_count - 2) * 3, 100)

    elif unique_types <= len(job_types) // 2:
        # Some overlap in job types = MEDIUM intent
        return 65 + (unique_types * 3)

    else:
        # Many different job types = LOW intent (scattered applications)
        return 40 + (duplicate_count * 2)


def handle_duplicate_candidate_analysis(message: Any, db: Session) -> Dict[str, Any]:
    """Handle duplicate_candidate_analysis message."""
    return DuplicateCandidateAnalysisHandler.process(message, db)
