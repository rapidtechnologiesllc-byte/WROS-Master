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
            interview = db.query(Interview).filter(Interview.interviewID == interview_id).first()
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
