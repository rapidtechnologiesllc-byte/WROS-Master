"""
Candidate Rejection Workflow Service

Implements the complete rejection workflow:
1. reject_candidate() - Create rejection record
2. send_rejection_email() - Send email notification to candidate
3. archive_candidate() - Soft-delete candidate and mark as archived

Story: S-322 (Candidate Rejection Workflow)

Business Rules:
- R-01: Tenant isolation enforced on all queries
- R-07: Only safe candidate access paths (via candidate_service)
- Email sending is optional (controlled by send_email parameter)
- Archival is a soft-delete (candidate record preserved for audit)
- All operations logged to audit trail
"""

from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.candidate import Candidate, CandidateStatus
from app.models.candidate_rejection import CandidateRejection, CandidateRejectionReason
from app.models.user import Users
from app.models.candidate_history import CandidateHistory
from app.core.logging import logger
from app.core.security import get_password_hash


class CandidateRejectionError(Exception):
    """Raised when rejection operation fails."""
    pass


class CandidateNotFoundError(Exception):
    """Raised when candidate doesn't exist."""
    pass


def reject_candidate(
    db: Session,
    *,
    candidate_id: str,
    rejection_reason: str,
    rejection_note: Optional[str] = None,
    job_id: Optional[str] = None,
    rejected_by_user_id: Optional[str] = None,
    send_email: bool = True,
    tenant_id: int = 1,
) -> CandidateRejection:
    """
    Reject a candidate and create rejection record.

    Args:
        db: Database session
        candidate_id: ID of candidate to reject
        rejection_reason: Reason for rejection (code or free text)
        rejection_note: Optional detailed note
        job_id: Optional job ID this rejection relates to
        rejected_by_user_id: Optional user ID of person rejecting
        send_email: Whether to send rejection email (default: True)
        tenant_id: Tenant context (default: 1)

    Returns:
        CandidateRejection record

    Raises:
        CandidateNotFoundError: If candidate doesn't exist
        CandidateRejectionError: If rejection fails
    """
    # Verify candidate exists and belongs to this tenant
    candidate = db.query(Candidate).filter(
        and_(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == tenant_id,
        )
    ).first()

    if not candidate:
        raise CandidateNotFoundError(f"Candidate {candidate_id} not found in tenant {tenant_id}")

    try:
        # BU Lifecycle: Revert to org-wide (NULL) on rejection
        candidate.associated_bu_id = None

        # Create rejection record
        rejection = CandidateRejection(
            candidate_id=candidate_id,
            job_id=job_id,
            rejection_reason=rejection_reason,
            rejection_note=rejection_note,
            rejected_by_user_id=rejected_by_user_id,
            rejection_status="ACTIVE",
            email_sent=False,
            tenant_id=tenant_id,
        )
        db.add(rejection)
        db.flush()

        # Update candidate status to "Rejected" in CandidateStatus
        candidate_status = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate_id
        ).first()

        if candidate_status:
            candidate_status.piplineStatus = "Rejected"
            candidate_status.status = "Inactive"
            candidate_status.updatedAt = datetime.utcnow()
        else:
            # Create status record if doesn't exist
            candidate_status = CandidateStatus(
                candidateID=candidate_id,
                piplineStatus="Rejected",
                status="Inactive",
            )
            db.add(candidate_status)

        db.flush()

        # Create audit history entry
        db.add(CandidateHistory(
            candidateID=candidate_id,
            event_type="Rejection",
            note=f"Candidate rejected: {rejection_reason}" + (f" ({rejection_note})" if rejection_note else ""),
        ))

        db.flush()

        # Send email if requested
        if send_email:
            try:
                _send_rejection_email_internal(db, rejection)
                rejection.email_sent = True
                rejection.email_sent_at = datetime.utcnow()
            except Exception as e:
                logger.warning(f"Failed to send rejection email for candidate {candidate_id}: {str(e)}")
                # Don't fail the entire rejection if email fails
                rejection.email_sent = False

        db.commit()
        logger.info(f"Candidate {candidate_id} rejected with reason: {rejection_reason}")

        return rejection

    except CandidateNotFoundError:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error rejecting candidate {candidate_id}: {str(e)}")
        raise CandidateRejectionError(f"Failed to reject candidate: {str(e)}")


def send_rejection_email(
    db: Session,
    *,
    rejection_id: int,
    include_feedback: bool = False,
    include_next_steps: bool = True,
    tenant_id: int = 1,
) -> CandidateRejection:
    """
    Send rejection email to candidate.

    Args:
        db: Database session
        rejection_id: ID of rejection record
        include_feedback: Include detailed feedback in email
        include_next_steps: Include next steps candidate can take
        tenant_id: Tenant context

    Returns:
        Updated rejection record with email_sent=True

    Raises:
        CandidateRejectionError: If email send fails
    """
    try:
        # Fetch rejection record
        rejection = db.query(CandidateRejection).filter(
            and_(
                CandidateRejection.id == rejection_id,
                CandidateRejection.tenant_id == tenant_id,
            )
        ).first()

        if not rejection:
            raise CandidateRejectionError(f"Rejection record {rejection_id} not found")

        # Fetch candidate
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == rejection.candidate_id
        ).first()

        if not candidate:
            raise CandidateRejectionError(f"Candidate {rejection.candidate_id} not found")

        # Send email
        _send_rejection_email_internal(
            db,
            rejection,
            include_feedback=include_feedback,
            include_next_steps=include_next_steps,
        )

        # Update rejection record
        rejection.email_sent = True
        rejection.email_sent_at = datetime.utcnow()
        db.commit()

        logger.info(f"Rejection email sent for candidate {rejection.candidate_id}")
        return rejection

    except Exception as e:
        db.rollback()
        logger.error(f"Error sending rejection email for rejection {rejection_id}: {str(e)}")
        raise CandidateRejectionError(f"Failed to send rejection email: {str(e)}")


def archive_candidate(
    db: Session,
    *,
    candidate_id: str,
    archive_reason: Optional[str] = None,
    archive_note: Optional[str] = None,
    archived_by_user_id: Optional[str] = None,
    tenant_id: int = 1,
) -> CandidateRejection:
    """
    Archive (soft-delete) a rejected candidate.
    Candidate record preserved in DB for audit trail.

    Args:
        db: Database session
        candidate_id: ID of candidate to archive
        archive_reason: Why are we archiving?
        archive_note: Additional context
        archived_by_user_id: User ID of person archiving
        tenant_id: Tenant context

    Returns:
        Updated rejection record with ARCHIVED status

    Raises:
        CandidateRejectionError: If archival fails
    """
    try:
        # Get active rejection record for this candidate
        rejection = db.query(CandidateRejection).filter(
            and_(
                CandidateRejection.candidate_id == candidate_id,
                CandidateRejection.rejection_status == "ACTIVE",
                CandidateRejection.tenant_id == tenant_id,
            )
        ).order_by(CandidateRejection.rejected_at.desc()).first()

        if not rejection:
            raise CandidateRejectionError(
                f"No active rejection record found for candidate {candidate_id}"
            )

        # Update rejection record to ARCHIVED
        rejection.rejection_status = "ARCHIVED"
        rejection.archived_at = datetime.utcnow()
        rejection.archived_by_user_id = archived_by_user_id

        # Update rejection note if archive_note provided
        if archive_note:
            rejection.rejection_note = (rejection.rejection_note or "") + f"\n[Archived: {archive_note}]"

        db.flush()

        # Create audit history entry
        db.add(CandidateHistory(
            candidateID=candidate_id,
            event_type="Archive",
            note=f"Candidate archived" + (f" ({archive_reason})" if archive_reason else ""),
        ))

        db.commit()

        logger.info(f"Candidate {candidate_id} archived")
        return rejection

    except Exception as e:
        db.rollback()
        logger.error(f"Error archiving candidate {candidate_id}: {str(e)}")
        raise CandidateRejectionError(f"Failed to archive candidate: {str(e)}")


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _send_rejection_email_internal(
    db: Session,
    rejection: CandidateRejection,
    include_feedback: bool = False,
    include_next_steps: bool = True,
) -> None:
    """
    Internal helper to send rejection email.
    Uses sendThunderMessage() path if available, otherwise direct email.

    Args:
        db: Database session
        rejection: Rejection record
        include_feedback: Include detailed feedback
        include_next_steps: Include next steps
    """
    from app.services.email_service import EmailService

    candidate = db.query(Candidate).filter(
        Candidate.candidateID == rejection.candidate_id
    ).first()

    if not candidate:
        raise CandidateRejectionError(f"Candidate {rejection.candidate_id} not found")

    candidate_name = (
        f"{candidate.candidateFirstName} {candidate.candidateLastName}".strip()
        or candidate.candidateEmail
    )

    # Build email content
    subject = f"Application Status Update - {candidate_name}"
    body_parts = [
        f"Dear {candidate_name},",
        "",
        "Thank you for your interest in our opportunities. We have completed our review of your application.",
        "",
        f"**Reason:** {rejection.rejection_reason}",
    ]

    if rejection.rejection_note:
        body_parts.append(f"**Details:** {rejection.rejection_note}")

    if include_feedback:
        body_parts.extend([
            "",
            "**Feedback:**",
            "We value your interest and encourage you to apply for future opportunities that better match your profile.",
        ])

    if include_next_steps:
        body_parts.extend([
            "",
            "**What's Next?**",
            "- Review similar job postings on our careers page",
            "- Update your profile with new skills or experience",
            "- Follow us for new opportunities",
        ])

    body_parts.extend([
        "",
        "Best regards,",
        "BlitzenX Talent Team",
    ])

    body = "\n".join(body_parts)

    # Try sendThunderMessage first (preferred)
    try:
        from app.services.conversation_service import send_thunder_message

        send_thunder_message(
            db,
            candidate_id=rejection.candidate_id,
            message_text=body,
            channel="email",
            subject=subject,
        )
        logger.info(f"Rejection email sent via Thunder for {rejection.candidate_id}")
        return
    except Exception as e:
        logger.debug(f"Thunder message send failed, falling back to EmailService: {str(e)}")

    # Fallback to direct email
    try:
        email_service = EmailService()
        email_service.send_email(
            recipient=candidate.candidateEmail,
            subject=subject,
            body=body,
            is_html=False,
        )
        logger.info(f"Rejection email sent directly for {rejection.candidate_id}")
    except Exception as e:
        logger.error(f"Failed to send rejection email: {str(e)}")
        raise


def get_rejection_reasons(
    db: Session,
    *,
    tenant_id: int = 1,
    active_only: bool = True,
) -> List[CandidateRejectionReason]:
    """
    Get available rejection reasons.

    Args:
        db: Database session
        tenant_id: Tenant context
        active_only: Only return active reasons?

    Returns:
        List of rejection reasons
    """
    query = db.query(CandidateRejectionReason).filter(
        CandidateRejectionReason.tenant_id == tenant_id
    )

    if active_only:
        query = query.filter(CandidateRejectionReason.is_active == True)

    return query.all()


def get_candidate_rejection_status(
    db: Session,
    *,
    candidate_id: str,
    tenant_id: int = 1,
) -> Tuple[bool, Optional[CandidateRejection], List[CandidateRejection]]:
    """
    Check if candidate has been rejected and get rejection details.

    Args:
        db: Database session
        candidate_id: Candidate ID
        tenant_id: Tenant context

    Returns:
        Tuple of (is_rejected, latest_rejection, all_rejections)
    """
    rejections = db.query(CandidateRejection).filter(
        and_(
            CandidateRejection.candidate_id == candidate_id,
            CandidateRejection.tenant_id == tenant_id,
        )
    ).order_by(CandidateRejection.rejected_at.desc()).all()

    active_rejections = [r for r in rejections if r.rejection_status == "ACTIVE"]
    is_rejected = len(active_rejections) > 0
    latest = active_rejections[0] if active_rejections else None

    return is_rejected, latest, rejections


def create_default_rejection_reasons(db: Session, tenant_id: int = 1) -> None:
    """
    Initialize default rejection reasons if they don't exist.

    Args:
        db: Database session
        tenant_id: Tenant ID
    """
    default_reasons = [
        {
            "reason_code": "LACK_OF_EXPERIENCE",
            "reason_label": "Lacks Required Experience",
            "category": "Experience",
            "description": "Candidate does not meet minimum experience requirements for the role",
        },
        {
            "reason_code": "FAILED_SCREENING",
            "reason_label": "Failed Technical Screening",
            "category": "Screening",
            "description": "Candidate did not pass technical screening assessment",
        },
        {
            "reason_code": "FAILED_INTERVIEW",
            "reason_label": "Failed Interview",
            "category": "Screening",
            "description": "Candidate performance in interview was not satisfactory",
        },
        {
            "reason_code": "ROLE_MISMATCH",
            "reason_label": "Role/Skill Mismatch",
            "category": "Skills",
            "description": "Candidate's skills do not align with role requirements",
        },
        {
            "reason_code": "CULTURE_FIT",
            "reason_label": "Culture/Team Fit Concerns",
            "category": "Other",
            "description": "Concerns about fit with team culture or work style",
        },
        {
            "reason_code": "POSITION_FILLED",
            "reason_label": "Position Filled",
            "category": "Other",
            "description": "Position has been filled by another candidate",
        },
        {
            "reason_code": "WITHDREW",
            "reason_label": "Candidate Withdrew",
            "category": "Other",
            "description": "Candidate withdrew application or declined offer",
        },
        {
            "reason_code": "OTHER",
            "reason_label": "Other Reason",
            "category": "Other",
            "description": "Other reasons (see rejection note for details)",
        },
    ]

    for reason_data in default_reasons:
        existing = db.query(CandidateRejectionReason).filter(
            and_(
                CandidateRejectionReason.reason_code == reason_data["reason_code"],
                CandidateRejectionReason.tenant_id == tenant_id,
            )
        ).first()

        if not existing:
            reason = CandidateRejectionReason(
                reason_code=reason_data["reason_code"],
                reason_label=reason_data["reason_label"],
                reason_description=reason_data["description"],
                category=reason_data["category"],
                is_active=True,
                tenant_id=tenant_id,
            )
            db.add(reason)

    db.commit()
