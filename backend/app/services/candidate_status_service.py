"""Candidate Status Service - Atomic status transitions with audit trail

Provides service layer for changing candidate status with automatic tracking of:
- status_changed_at: When status was changed
- previous_status: What the status was before
- status_change_reason: Why the status changed
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models.candidate import Candidate, CandidateStatus
from app.services.candidate_event_bus import CandidateEventBus

logger = logging.getLogger(__name__)


class CandidateStatusService:
    """Service for atomic candidate status transitions with audit trail."""

    @staticmethod
    def change_status(
        db: Session,
        candidate_id: str,
        new_status: str,
        reason: Optional[str] = None,
        publish_event: bool = True,
    ) -> Dict[str, Any]:
        """
        Atomically change candidate status with audit trail.

        Args:
            db: Database session
            candidate_id: ID of candidate to update
            new_status: New pipeline status (Applied, Interview, Offer, Employee, etc.)
            reason: Optional reason for status change
            publish_event: Whether to publish candidate_status_changed event (default True)

        Returns:
            {
                'status': 'success',
                'candidate_id': str,
                'old_status': str,
                'new_status': str,
                'changed_at': datetime,
                'reason': str
            }

        Raises:
            ValueError: If candidate or status record not found
            RuntimeError: If database operation fails
        """
        try:
            # Fetch candidate
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id
            ).first()

            if not candidate:
                raise ValueError(f"Candidate {candidate_id} not found")

            # Fetch candidate status record
            candidate_status = db.query(CandidateStatus).filter(
                CandidateStatus.candidateID == candidate_id
            ).first()

            if not candidate_status:
                raise ValueError(f"Candidate status record not found for {candidate_id}")

            # Capture old status for audit trail
            old_status = candidate_status.piplineStatus
            changed_at = datetime.utcnow()

            # Only update if status is actually changing (prevent redundant updates)
            if old_status == new_status:
                logger.info(f"[StatusService] Status unchanged for {candidate_id} (already {new_status})")
                return {
                    'status': 'success',
                    'candidate_id': candidate_id,
                    'old_status': old_status,
                    'new_status': new_status,
                    'changed_at': changed_at,
                    'reason': reason,
                    'changed': False
                }

            # Update status with audit trail
            candidate_status.previous_status = old_status
            candidate_status.piplineStatus = new_status
            candidate_status.status_changed_at = changed_at
            candidate_status.status_change_reason = reason or f"Changed from {old_status} to {new_status}"
            candidate_status.updatedAt = changed_at

            # Flush to validate constraints
            try:
                db.flush()
            except SQLAlchemyError as e:
                logger.error(f"[StatusService] Database error during flush: {e}", exc_info=True)
                db.rollback()
                raise RuntimeError(f"Failed to update candidate status: {str(e)}") from e

            # Commit atomically
            try:
                db.commit()
                logger.info(
                    f"[StatusService] Status changed for {candidate_id}: {old_status} → {new_status} "
                    f"(reason: {reason})"
                )
            except SQLAlchemyError as e:
                logger.error(f"[StatusService] Commit failed: {e}", exc_info=True)
                db.rollback()
                raise RuntimeError(f"Failed to commit status change: {str(e)}") from e

            # Publish status change event (after commit)
            if publish_event:
                try:
                    CandidateEventBus.publish_status_changed(
                        candidate_id=candidate_id,
                        old_status=old_status,
                        new_status=new_status,
                        reason=reason
                    )
                    logger.info(f"[StatusService] Published status_changed event for {candidate_id}")
                except Exception as e:
                    logger.error(f"[StatusService] Failed to publish event: {e}", exc_info=True)
                    # Don't fail status change if event publishing fails

            return {
                'status': 'success',
                'candidate_id': candidate_id,
                'old_status': old_status,
                'new_status': new_status,
                'changed_at': changed_at,
                'reason': reason or f"Changed from {old_status} to {new_status}",
                'changed': True
            }

        except ValueError as e:
            logger.warning(f"[StatusService] Validation error: {e}")
            raise

        except Exception as e:
            logger.error(f"[StatusService] Unexpected error: {e}", exc_info=True)
            raise

    @staticmethod
    def get_status_history(
        db: Session,
        candidate_id: str,
    ) -> Dict[str, Any]:
        """
        Get current status and audit trail for a candidate.

        Returns:
            {
                'candidate_id': str,
                'current_status': str,
                'previous_status': str,
                'changed_at': datetime,
                'change_reason': str,
                'updated_at': datetime
            }
        """
        candidate_status = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate_id
        ).first()

        if not candidate_status:
            raise ValueError(f"Candidate status not found for {candidate_id}")

        return {
            'candidate_id': candidate_id,
            'current_status': candidate_status.piplineStatus,
            'previous_status': candidate_status.previous_status,
            'changed_at': candidate_status.status_changed_at,
            'change_reason': candidate_status.status_change_reason,
            'updated_at': candidate_status.updatedAt,
        }
