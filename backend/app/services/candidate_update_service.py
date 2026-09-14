"""Candidate Update Service - Handles updates with field-level audit logging

Tracks all changes field-by-field and writes to audit_log table atomically.
"""
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.core.audit import write_audit_log

logger = logging.getLogger(__name__)


def update_candidate_safe(
    db: Session,
    candidate_id: str,
    updated_by_user_id: Optional[str],
    updated_by_name: str = "System",
    **candidate_fields
) -> Dict[str, Any]:
    """
    Safely update candidate with field-level audit logging.

    Args:
        db: Database session
        candidate_id: ID of candidate to update
        updated_by_user_id: User ID of person making changes
        updated_by_name: User name for logging
        **candidate_fields: Fields to update (only non-null values processed)

    Returns:
        {
            'status': 'success' | 'error',
            'candidate_id': str,
            'fields_updated': List[str],
            'audit_trail': List[Dict] with old_value/new_value for each field
        }
    """
    try:
        # Fetch existing candidate
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id
        ).first()

        if not candidate:
            return {
                'status': 'error',
                'candidate_id': candidate_id,
                'fields_updated': [],
                'audit_trail': [],
                'error': f'Candidate {candidate_id} not found'
            }

        # Track changes for audit trail
        audit_trail = []
        fields_updated = []

        # Map request fields to model fields
        field_mapping = {
            'candidate_first_name': 'candidateFirstName',
            'candidate_last_name': 'candidateLastName',
            'candidate_mobile': 'candidateMobile',
            'candidate_current_location': 'candidateCurrentLocation',
            'candidate_source': 'candidateSource',
            'candidate_experience': 'candidateExperience',
            'candidate_skills': 'candidateSkills',
            'candidate_email': 'candidateEmail',
            'candidate_job_title': 'candidateJobTitle',
            'candidate_gender': 'candidateGender',
            'candidate_date_of_birth': 'candidateDateOfBirth',
        }

        # Process each field update
        for request_field, value in candidate_fields.items():
            if value is None:
                continue

            model_field = field_mapping.get(request_field)
            if not model_field or not hasattr(candidate, model_field):
                logger.warning(f"Skipping unknown field: {request_field}")
                continue

            # Get old value
            old_value = getattr(candidate, model_field, None)

            # Skip if value hasn't changed
            if old_value == value:
                continue

            # Update the field
            setattr(candidate, model_field, value)
            fields_updated.append(request_field)

            # Track for audit trail
            audit_trail.append({
                'field': request_field,
                'old_value': str(old_value) if old_value is not None else None,
                'new_value': str(value) if value is not None else None
            })

            # Write individual audit log entry (NON-OPTIONAL)
            write_audit_log(
                db,
                entity_type="candidate",
                entity_id=candidate_id,
                action="update",
                tenant_id=candidate.tenant_id,
                user_id=updated_by_user_id,
                old_value=str(old_value) if old_value is not None else None,
                new_value=str(value) if value is not None else None,
                metadata={"field": request_field}
            )
            # Don't catch audit errors - let them bubble to db.commit() level

        # If no fields were actually updated, return early
        if not fields_updated:
            return {
                'status': 'success',
                'candidate_id': candidate_id,
                'fields_updated': [],
                'audit_trail': [],
                'message': 'No fields changed'
            }

        # Commit all changes atomically
        try:
            db.commit()
            db.refresh(candidate)
            logger.info(f"[UpdateService] ✅ Updated {len(fields_updated)} fields for candidate {candidate_id}")

            return {
                'status': 'success',
                'candidate_id': candidate_id,
                'fields_updated': fields_updated,
                'audit_trail': audit_trail,
                'message': f'Updated {len(fields_updated)} fields'
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to commit updates: {e}", exc_info=True)
            return {
                'status': 'error',
                'candidate_id': candidate_id,
                'fields_updated': [],
                'audit_trail': [],
                'error': f'Failed to commit: {str(e)}'
            }

    except Exception as e:
        logger.error(f"Update candidate service error: {e}", exc_info=True)
        db.rollback()
        return {
            'status': 'error',
            'candidate_id': candidate_id,
            'fields_updated': [],
            'audit_trail': [],
            'error': str(e)
        }
