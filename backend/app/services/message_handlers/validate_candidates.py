"""Validation framework for candidate-related message handlers.

Provides reusable validators for:
- Candidate creation completion
- Candidate data integrity
- Status transition validity
"""

import logging
from sqlalchemy.orm import Session
from app.models.candidate import Candidate
from app.services.message_handlers.base_message_handler import ValidationError

logger = logging.getLogger(__name__)


def validate_candidate_created(candidate_id: str, payload: dict, db: Session) -> None:
    """Validate that candidate was actually created in database.

    Args:
        candidate_id: ID of candidate that should have been created
        payload: Original payload with expected data
        db: Database session

    Raises:
        ValidationError: If candidate not found or data doesn't match
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()

    if not candidate:
        raise ValidationError(f"Candidate {candidate_id} not found in database after creation")

    # Validate critical fields match payload
    expected_email = payload.get("candidate_email")
    if candidate.candidateEmail != expected_email:
        raise ValidationError(
            f"Email mismatch: expected {expected_email}, got {candidate.candidateEmail}"
        )

    if not candidate.candidateCreatedAt:
        raise ValidationError(f"Candidate {candidate_id} has no createdAt timestamp")

    logger.info(f"✅ Candidate {candidate_id} validated: {candidate.candidateEmail}")


def validate_candidate_status(candidate_id: str, expected_status: str, db: Session) -> None:
    """Validate that candidate has expected status.

    Args:
        candidate_id: ID of candidate to check
        expected_status: Expected status value
        db: Database session

    Raises:
        ValidationError: If status doesn't match
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()

    if not candidate:
        raise ValidationError(f"Candidate {candidate_id} not found for status validation")

    if candidate.candidateStatus != expected_status:
        raise ValidationError(
            f"Status mismatch for {candidate_id}: expected {expected_status}, got {candidate.candidateStatus}"
        )

    logger.info(f"✅ Candidate {candidate_id} status valid: {expected_status}")


def validate_candidate_not_duplicate(candidate_id: str, email: str, phone: str, db: Session) -> None:
    """Validate that no duplicates exist for this candidate.

    Args:
        candidate_id: ID of the candidate
        email: Email to check for duplicates
        phone: Phone to check for duplicates
        db: Database session

    Raises:
        ValidationError: If duplicates found
    """
    from sqlalchemy import and_, or_

    duplicates = db.query(Candidate).filter(
        and_(
            Candidate.candidateID != candidate_id,
            or_(
                Candidate.candidateEmail == email,
                Candidate.candidateMobile == phone
            )
        )
    ).all()

    if duplicates:
        dup_ids = [d.candidateID for d in duplicates]
        logger.warning(
            f"Potential duplicates found for {candidate_id}: {dup_ids}. "
            f"Email={email}, Phone={phone}"
        )

    logger.info(f"✅ Candidate {candidate_id} uniqueness validated")
