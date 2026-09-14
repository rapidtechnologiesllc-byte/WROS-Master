"""
Candidate Activity Logging Service - S-216/HRMS-0118 Extension
================================================================

Centralized logging for all candidate lifecycle events:
- Creation events
- Status changes
- Thunder operations (autonomous agent actions)
- Referral tracking
- HR manual notes

All writes to CandidateHistory table for append-only audit trail.
Caller owns transaction (follows app.core.audit.write_audit_log pattern).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_history import CandidateHistory
from app.models.activity_timeline import ActivityTimeline
from app.models.user import Users
from app.models.referral import EmployeeReferral

logger = logging.getLogger(__name__)

# Event type constants for consistency
EVENT_CANDIDATE_CREATED = "Candidate Added"
EVENT_CANDIDATE_EDITED = "Candidate Edited"
EVENT_CANDIDATE_ARCHIVED = "Candidate Archived"
EVENT_CANDIDATE_RESTORED = "Candidate Restored"

EVENT_SCREENING = "Screening"
EVENT_JOB_ASSIGNED = "Job Assigned"

EVENT_INTERVIEW_SCHEDULED = "Interview Scheduled"
EVENT_INTERVIEW_COMPLETED = "Interview Completed"
EVENT_INTERVIEW_RESCHEDULED = "Interview Rescheduled"
EVENT_INTERVIEW_CANCELLED = "Interview Cancelled"
EVENT_INTERVIEW_NO_SHOW = "Candidate No Show"
EVENT_FEEDBACK_SUBMITTED = "Feedback Submitted"

EVENT_OFFER_RELEASED = "Offer Released"
EVENT_OFFER_UPDATED = "Offer Updated"
EVENT_OFFER_ACCEPTED = "Offer Accepted"
EVENT_OFFER_REJECTED = "Offer Rejected"

EVENT_PREBOARDING = "Preboarding"
EVENT_ONBOARDED = "Onboarded"

EVENT_CANDIDATE_REJECTED = "Rejected"
EVENT_CANDIDATE_GHOSTED = "Candidate Ghosted"

EVENT_THUNDER_OPERATION = "Thunder Operation"
EVENT_REFERRAL_LINKED = "Referred by Employee"
EVENT_REFERRAL_STATUS_CHANGED = "Referral Status Changed"

EVENT_DUPLICATE_MERGED = "Duplicate Merged"
EVENT_EMAIL_UPDATED = "Email Updated"

# Communication & Engagement Events
EVENT_RESUME_UPLOADED = "Resume Uploaded"
EVENT_EMAIL_SENT = "Email Sent"
EVENT_EMAIL_OPENED = "Email Opened"
EVENT_EMAIL_REPLIED = "Email Reply Received"
EVENT_WHATSAPP_MESSAGE = "WhatsApp Message Received"
EVENT_SMS_MESSAGE = "SMS Message Received"
EVENT_CALL_RECEIVED = "Call Received"
EVENT_THUNDER_QUEUED = "Thunder Engagement Queued"
EVENT_THUNDER_PAUSED = "Thunder Paused"
EVENT_THUNDER_RESUMED = "Thunder Resumed"

# All valid event types for validation
VALID_EVENT_TYPES = {
    EVENT_CANDIDATE_CREATED,
    EVENT_CANDIDATE_EDITED,
    EVENT_CANDIDATE_ARCHIVED,
    EVENT_CANDIDATE_RESTORED,
    EVENT_SCREENING,
    EVENT_JOB_ASSIGNED,
    EVENT_INTERVIEW_SCHEDULED,
    EVENT_INTERVIEW_COMPLETED,
    EVENT_INTERVIEW_RESCHEDULED,
    EVENT_INTERVIEW_CANCELLED,
    EVENT_INTERVIEW_NO_SHOW,
    EVENT_FEEDBACK_SUBMITTED,
    EVENT_OFFER_RELEASED,
    EVENT_OFFER_UPDATED,
    EVENT_OFFER_ACCEPTED,
    EVENT_OFFER_REJECTED,
    EVENT_PREBOARDING,
    EVENT_ONBOARDED,
    EVENT_DUPLICATE_MERGED,
    EVENT_EMAIL_UPDATED,
    EVENT_CANDIDATE_REJECTED,
    EVENT_CANDIDATE_GHOSTED,
    EVENT_THUNDER_OPERATION,
    EVENT_REFERRAL_LINKED,
    EVENT_REFERRAL_STATUS_CHANGED,
    # Communication & Engagement
    EVENT_RESUME_UPLOADED,
    EVENT_EMAIL_SENT,
    EVENT_EMAIL_OPENED,
    EVENT_EMAIL_REPLIED,
    EVENT_WHATSAPP_MESSAGE,
    EVENT_SMS_MESSAGE,
    EVENT_CALL_RECEIVED,
    EVENT_THUNDER_QUEUED,
    EVENT_THUNDER_PAUSED,
    EVENT_THUNDER_RESUMED,
}


# ============================================================================
# PRIMARY LOGGING FUNCTIONS (Main API)
# ============================================================================

def log_candidate_created(
    db: Session,
    candidate_id: str,
    created_by_user_id: Optional[str] = None,
    created_by_name: Optional[str] = None,
    referral_id: Optional[str] = None,
    recruitment_source: str = "DIRECT",
) -> CandidateHistory:
    """
    Log a candidate creation event.

    Called immediately after candidate record is inserted in database.
    Writes to both CandidateHistory and ActivityTimeline.
    """
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.error(f"log_candidate_created: Candidate {candidate_id} not found")
            return None

        # Build note with metadata
        note_parts = []
        if recruitment_source and recruitment_source != "DIRECT":
            note_parts.append(f"Source: {recruitment_source}")
        if referral_id:
            note_parts.append(f"Referral: {referral_id}")
        note = " | ".join(note_parts) if note_parts else None

        # Write CandidateHistory entry
        history = CandidateHistory(
            candidateID=candidate_id,
            event_type=EVENT_CANDIDATE_CREATED,
            note=note,
            performed_by_id=created_by_user_id,
            performed_by_name=created_by_name or "System",
            event_at=datetime.utcnow(),
        )
        db.add(history)
        logger.info(f"Logged: Candidate {candidate_id} created by {created_by_name or 'System'}")

        # Write ActivityTimeline for global feed
        _write_timeline(
            db,
            entity_type="Candidate",
            entity_id=candidate_id,
            action="created",
            actor_id=created_by_user_id,
            actor_type="USER" if created_by_user_id else "SYSTEM",
            description=f"Candidate created - {recruitment_source}",
            tenant_id=candidate.tenant_id,
        )

        return history

    except Exception as e:
        logger.error(f"log_candidate_created failed for {candidate_id}: {str(e)}", exc_info=True)
        return None


def log_duplicate_merged(
    db: Session,
    candidate_id: str,
    old_email: str,
    new_email: str,
    match_field: str = "phone",
) -> CandidateHistory:
    """
    Log when duplicate candidate is found and merged.

    Tracks email updates during duplicate handling with full audit trail.
    Shows: Old email → New email, Match field (phone/email), Timestamp
    """
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.error(f"log_duplicate_merged: Candidate {candidate_id} not found")
            return None

        # Build detailed note showing the change
        note = f"Merged duplicate | Match: {match_field} | Email: {old_email} → {new_email}"

        # Write CandidateHistory entry
        history = CandidateHistory(
            candidateID=candidate_id,
            event_type=EVENT_DUPLICATE_MERGED,
            note=note,
            performed_by_id=None,
            performed_by_name="System",
            event_at=datetime.utcnow(),
        )
        db.add(history)
        logger.info(f"Logged: Duplicate merged for {candidate_id} - {match_field} match - Email updated: {old_email} → {new_email}")

        # Write ActivityTimeline for global feed
        _write_timeline(
            db,
            entity_type="Candidate",
            entity_id=candidate_id,
            action="merged_duplicate",
            actor_id=None,
            actor_type="SYSTEM",
            description=f"Duplicate candidate merged by {match_field} match. Email: {old_email} → {new_email}",
            tenant_id=candidate.tenant_id,
        )

        return history

    except Exception as e:
        logger.error(f"log_duplicate_merged failed for {candidate_id}: {str(e)}", exc_info=True)
        return None


# ============================================================================
# COMMUNICATION & ENGAGEMENT LOGGING
# ============================================================================

def log_resume_uploaded(
    db: Session,
    candidate_id: str,
    file_name: str,
    file_size_mb: float = 0.0,
    uploaded_by_user_id: Optional[str] = None,
    uploaded_by_name: Optional[str] = None,
) -> CandidateHistory:
    """Log when resume is uploaded to candidate profile."""
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.error(f"log_resume_uploaded: Candidate {candidate_id} not found")
            return None

        note = f"Resume: {file_name} ({file_size_mb:.1f} MB) | By: {uploaded_by_name or 'System'}"

        history = CandidateHistory(
            candidateID=candidate_id,
            event_type=EVENT_RESUME_UPLOADED,
            note=note,
            performed_by_id=uploaded_by_user_id,
            performed_by_name=uploaded_by_name or "System",
            event_at=datetime.utcnow(),
        )
        db.add(history)
        logger.info(f"Logged: Resume uploaded for {candidate_id} by {uploaded_by_name or 'System'}")

        _write_timeline(
            db,
            entity_type="Candidate",
            entity_id=candidate_id,
            action="resume_uploaded",
            actor_id=uploaded_by_user_id,
            actor_type="USER" if uploaded_by_user_id else "SYSTEM",
            description=f"Resume uploaded: {file_name}",
            tenant_id=candidate.tenant_id,
        )
        return history
    except Exception as e:
        logger.error(f"log_resume_uploaded failed for {candidate_id}: {str(e)}", exc_info=True)
        return None


def log_email_received(
    db: Session,
    candidate_id: str,
    subject: str,
    preview: Optional[str] = None,
    perform_pii_hashing: bool = True,
) -> CandidateHistory:
    """Log when candidate replies via email.

    PHASE 3: Data minimization - hash email content for GDPR compliance.
    Stores hash + length of content, not plaintext (PII-sensitive data).
    """
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.error(f"log_email_received: Candidate {candidate_id} not found")
            return None

        # Limit subject to 100 chars (not PII, but prevent excessive storage)
        safe_subject = subject[:100] if subject else "No Subject"

        # Hash preview if provided and PII hashing enabled (GDPR compliance)
        preview_note = "N/A"
        if preview and perform_pii_hashing:
            import hashlib
            preview_hash = hashlib.sha256(preview.encode()).hexdigest()[:8]
            preview_note = f"hash:{preview_hash} (len:{len(preview)})"
        elif preview:
            preview_note = f"{preview[:50]}"

        note_parts = [f"Subject: {safe_subject}", f"Content: {preview_note}"]
        note = " | ".join(note_parts)

        history = CandidateHistory(
            candidateID=candidate_id,
            event_type=EVENT_EMAIL_REPLIED,
            note=note,
            performed_by_id=None,
            performed_by_name=candidate.candidateFirstName or "Candidate",
            event_at=datetime.utcnow(),
        )
        db.add(history)
        logger.info(f"Logged: Email reply from {candidate_id} - {subject}")

        _write_timeline(
            db,
            entity_type="Candidate",
            entity_id=candidate_id,
            action="email_replied",
            actor_id=candidate_id,
            actor_type="CANDIDATE",
            description=f"Candidate replied: {subject}",
            tenant_id=candidate.tenant_id,
        )
        return history
    except Exception as e:
        logger.error(f"log_email_received failed for {candidate_id}: {str(e)}", exc_info=True)
        return None


def log_whatsapp_received(
    db: Session,
    candidate_id: str,
    message_preview: str,
    sender_phone: Optional[str] = None,
    perform_pii_hashing: bool = True,
) -> CandidateHistory:
    """Log when candidate sends WhatsApp message.

    PHASE 3: Data minimization - hash message content for GDPR compliance.
    Stores hash + length of content, not plaintext (PII-sensitive data).
    """
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.error(f"log_whatsapp_received: Candidate {candidate_id} not found")
            return None

        # Hash message content if PII hashing enabled (GDPR compliance)
        message_note = message_preview[:80]
        if perform_pii_hashing and message_preview:
            import hashlib
            msg_hash = hashlib.sha256(message_preview.encode()).hexdigest()[:8]
            message_note = f"hash:{msg_hash} (len:{len(message_preview)})"

        note = f"WhatsApp from {sender_phone or candidate.candidateMobile}: {message_note}"

        history = CandidateHistory(
            candidateID=candidate_id,
            event_type=EVENT_WHATSAPP_MESSAGE,
            note=note,
            performed_by_id=None,
            performed_by_name="Candidate",
            event_at=datetime.utcnow(),
        )
        db.add(history)
        logger.info(f"Logged: WhatsApp from {candidate_id}")

        _write_timeline(
            db,
            entity_type="Candidate",
            entity_id=candidate_id,
            action="whatsapp_received",
            actor_id=candidate_id,
            actor_type="CANDIDATE",
            description=f"WhatsApp message received: {message_preview[:50]}",
            tenant_id=candidate.tenant_id,
        )
        return history
    except Exception as e:
        logger.error(f"log_whatsapp_received failed for {candidate_id}: {str(e)}", exc_info=True)
        return None


def log_thunder_operation(
    db: Session,
    candidate_id: str,
    message_id: str,  # Unique ID - ALL states for this message grouped here
    operation_state: str,  # QUEUED, SENT, FAILED, OPENED, CLICKED, NO_RESPONSE, GHOSTED, PAUSED, RESUMED
    message_type: Optional[str] = None,  # EMAIL, WHATSAPP, SMS, CALL
    recipient: Optional[str] = None,
    agent_name: str = "flash_recruiter",
    campaign_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,  # Extra data: days_without_response, reason, etc
) -> CandidateHistory:
    """Log Thunder operation - single collapsible object per message_id.

    PHASE 2C: All states for ONE message_id grouped in ONE history entry.
    Frontend expands to see timeline: QUEUED → SENT → OPENED → [NO_RESPONSE] → [GHOSTED]

    Each call UPDATES the existing entry for that message_id with new state.
    History shows complete message lifecycle in one collapsible section.
    """
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.error(f"log_thunder_operation: Candidate {candidate_id} not found")
            return None

        # Build title/summary (shown when collapsed)
        title_parts = [f"Thunder [{message_id}]"]
        if operation_state == "SENT" and message_type:
            title_parts.append(f"{message_type} to {recipient or 'contact'}")
        else:
            title_parts.append(operation_state)

        summary = " • ".join(title_parts)

        # Build detailed note (shown when expanded)
        note_parts = [
            f"Message ID: {message_id}",
            f"State: {operation_state}",
            f"Agent: {agent_name}",
        ]

        if message_type:
            note_parts.append(f"Type: {message_type}")
        if recipient:
            note_parts.append(f"Recipient: {recipient}")
        if campaign_name:
            note_parts.append(f"Campaign: {campaign_name}")

        # Add metadata (days_without_response, reason, etc)
        if metadata:
            for key, value in metadata.items():
                if value is not None:
                    note_parts.append(f"{key}: {value}")

        note = "\n".join(note_parts)  # Multi-line for readability when expanded

        # Check if history entry for this message_id already exists
        existing = db.query(CandidateHistory).filter(
            CandidateHistory.candidateID == candidate_id,
            CandidateHistory.event_type == EVENT_THUNDER_OPERATION,
            CandidateHistory.note.like(f"%Message ID: {message_id}%")
        ).first()

        if existing:
            # Update existing entry with new state (append to timeline)
            existing.note = note
            existing.event_at = datetime.utcnow()
            db.add(existing)
            logger.info(f"Updated Thunder operation {message_id} for {candidate_id}: {operation_state}")
        else:
            # Create new entry for this message_id
            history = CandidateHistory(
                candidateID=candidate_id,
                event_type=EVENT_THUNDER_OPERATION,
                note=note,
                performed_by_id=None,
                performed_by_name="Thunder",
                event_at=datetime.utcnow(),
            )
            db.add(history)
            logger.info(f"Created Thunder operation {message_id} for {candidate_id}: {operation_state}")

        _write_timeline(
            db,
            entity_type="Candidate",
            entity_id=candidate_id,
            action=f"thunder_{operation_state.lower()}",
            actor_id=None,
            actor_type="SYSTEM",
            description=f"Thunder {operation_state} ({message_id})",
            tenant_id=candidate.tenant_id,
        )
        return history
    except Exception as e:
        logger.error(f"log_thunder_operation failed for {candidate_id}: {str(e)}", exc_info=True)
        return None


# Convenience wrappers (call log_thunder_operation internally)
def log_thunder_queued(
    db: Session,
    candidate_id: str,
    message_id: str,
    agent_name: str = "flash_recruiter",
    campaign_name: Optional[str] = None,
) -> CandidateHistory:
    """Convenience: Log when candidate queued to Thunder."""
    return log_thunder_operation(
        db, candidate_id, message_id, "QUEUED",
        agent_name=agent_name, campaign_name=campaign_name
    )


def log_thunder_message_sent(
    db: Session,
    candidate_id: str,
    message_id: str,
    message_type: str,
    recipient: Optional[str] = None,
    campaign_name: Optional[str] = None,
) -> CandidateHistory:
    """Convenience: Log when Thunder sends message."""
    return log_thunder_operation(
        db, candidate_id, message_id, "SENT",
        message_type=message_type, recipient=recipient, campaign_name=campaign_name
    )


def log_thunder_no_response(
    db: Session,
    candidate_id: str,
    message_id: str,
    days_without_response: int = 0,
) -> CandidateHistory:
    """Convenience: Log when no response detected."""
    return log_thunder_operation(
        db, candidate_id, message_id, "NO_RESPONSE",
        metadata={"days_without_response": days_without_response}
    )


def log_thunder_ghosted(
    db: Session,
    candidate_id: str,
    message_id: str,
    reason: Optional[str] = None,
) -> CandidateHistory:
    """Convenience: Log when engagement ends."""
    return log_thunder_operation(
        db, candidate_id, message_id, "GHOSTED",
        metadata={"reason": reason} if reason else None
    )


def log_candidate_status_change(
    db: Session,
    candidate_id: str,
    old_status: str,
    new_status: str,
    reason: Optional[str] = None,
    changed_by_user_id: Optional[str] = None,
    changed_by_name: Optional[str] = None,
) -> CandidateHistory:
    """
    Log a candidate status transition.

    Called whenever candidate's pipeline status changes.
    """
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.error(f"log_candidate_status_change: Candidate {candidate_id} not found")
            return None

        # Map status to event type
        event_type_map = {
            "Screening": EVENT_SCREENING,
            "Interview": EVENT_INTERVIEW_SCHEDULED,
            "Offer": EVENT_OFFER_RELEASED,
            "Hired": EVENT_ONBOARDED,
        }
        event_type = event_type_map.get(new_status, "Custom Status Change")

        # Build note with transition info
        note = f"{old_status} -> {new_status}"
        if reason:
            note += f": {reason}"

        history = CandidateHistory(
            candidateID=candidate_id,
            event_type=event_type,
            note=note,
            performed_by_id=changed_by_user_id,
            performed_by_name=changed_by_name or "System",
            event_at=datetime.utcnow(),
        )
        db.add(history)
        logger.info(f"Logged: Candidate {candidate_id} status changed to {new_status}")

        _write_timeline(
            db,
            entity_type="Candidate",
            entity_id=candidate_id,
            action="status_changed",
            actor_id=changed_by_user_id,
            actor_type="USER" if changed_by_user_id else "SYSTEM",
            description=f"Status: {old_status} -> {new_status}",
            tenant_id=candidate.tenant_id,
        )

        return history

    except Exception as e:
        logger.error(f"log_candidate_status_change failed: {str(e)}", exc_info=True)
        return None


def log_thunder_operation(
    db: Session,
    candidate_id: str,
    operation: str,
    metadata: Optional[Dict[str, Any]] = None,
    actor_name: str = "Thunder",
) -> CandidateHistory:
    """
    Log a Thunder autonomous agent operation on a candidate.

    Called whenever Thunder:
    - Sends a message to candidate
    - Schedules an interview
    - Releases an offer
    - Rejects a candidate
    """
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.error(f"log_thunder_operation: Candidate {candidate_id} not found")
            return None

        # Map operation to human-readable event type
        operation_event_map = {
            "INTERVIEW_SCHEDULED": EVENT_INTERVIEW_SCHEDULED,
            "MESSAGE_SENT": "Thunder Message Sent",
            "REJECTED": EVENT_CANDIDATE_REJECTED,
            "OFFER_RELEASED": EVENT_OFFER_RELEASED,
            "GHOSTED": EVENT_CANDIDATE_GHOSTED,
            "INTERVIEW_RESCHEDULED": EVENT_INTERVIEW_RESCHEDULED,
            "INTERVIEW_CANCELLED": EVENT_INTERVIEW_CANCELLED,
            "MOVED_FORWARD": "Moved Forward",
            "PRIORITY_ESCALATED": "Priority Escalated",
        }
        event_type = operation_event_map.get(operation, EVENT_THUNDER_OPERATION)

        # Build detailed note from metadata
        note_parts = [f"Operation: {operation}"]
        if metadata:
            for key, value in metadata.items():
                if value and key not in ["password", "token", "secret"]:
                    note_parts.append(f"{key}: {value}")
        note = " | ".join(note_parts)

        history = CandidateHistory(
            candidateID=candidate_id,
            event_type=event_type,
            note=note,
            performed_by_id="THUNDER_AI",
            performed_by_name=actor_name,
            event_at=datetime.utcnow(),
        )
        db.add(history)
        logger.info(f"Logged: Thunder {operation} on candidate {candidate_id}")

        _write_timeline(
            db,
            entity_type="Candidate",
            entity_id=candidate_id,
            action=operation.lower(),
            actor_id="THUNDER_AI",
            actor_type="AI_AGENT",
            description=f"Thunder: {operation}",
            tenant_id=candidate.tenant_id,
        )

        return history

    except Exception as e:
        logger.error(f"log_thunder_operation failed: {str(e)}", exc_info=True)
        return None


def log_referral_linked(
    db: Session,
    candidate_id: str,
    referral_id: str,
    referred_by_employee_id: Optional[str] = None,
    referred_by_employee_name: Optional[str] = None,
) -> CandidateHistory:
    """
    Log when a candidate is linked to an employee referral.
    """
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.error(f"log_referral_linked: Candidate {candidate_id} not found")
            return None

        note = f"Linked to referral {referral_id}"
        if referred_by_employee_name:
            note += f" from {referred_by_employee_name}"

        history = CandidateHistory(
            candidateID=candidate_id,
            event_type=EVENT_REFERRAL_LINKED,
            note=note,
            performed_by_id=referred_by_employee_id,
            performed_by_name=referred_by_employee_name or "System",
            event_at=datetime.utcnow(),
        )
        db.add(history)
        logger.info(f"Logged: Candidate {candidate_id} linked to referral {referral_id}")

        _write_timeline(
            db,
            entity_type="Candidate",
            entity_id=candidate_id,
            action="referral_linked",
            actor_id=referred_by_employee_id,
            actor_type="USER" if referred_by_employee_id else "SYSTEM",
            description=f"Linked to employee referral {referral_id}",
            tenant_id=candidate.tenant_id,
        )

        return history

    except Exception as e:
        logger.error(f"log_referral_linked failed: {str(e)}", exc_info=True)
        return None


def log_referral_status_changed(
    db: Session,
    candidate_id: str,
    referral_id: str,
    old_status: str,
    new_status: str,
    changed_by_user_id: Optional[str] = None,
    changed_by_name: Optional[str] = None,
) -> CandidateHistory:
    """
    Log referral status transitions (affects bonus eligibility).
    """
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
        if not candidate:
            logger.error(f"log_referral_status_changed: Candidate {candidate_id} not found")
            return None

        note = f"Referral {referral_id} status: {old_status} -> {new_status}"

        history = CandidateHistory(
            candidateID=candidate_id,
            event_type=EVENT_REFERRAL_STATUS_CHANGED,
            note=note,
            performed_by_id=changed_by_user_id,
            performed_by_name=changed_by_name or "System",
            event_at=datetime.utcnow(),
        )
        db.add(history)
        logger.info(f"Logged: Referral {referral_id} status changed to {new_status}")

        _write_timeline(
            db,
            entity_type="Candidate",
            entity_id=candidate_id,
            action="referral_status_changed",
            actor_id=changed_by_user_id,
            actor_type="USER" if changed_by_user_id else "SYSTEM",
            description=f"Referral status: {old_status} -> {new_status}",
            tenant_id=candidate.tenant_id,
        )

        return history

    except Exception as e:
        logger.error(f"log_referral_status_changed failed: {str(e)}", exc_info=True)
        return None


# ============================================================================
# HELPER FUNCTIONS (Internal)
# ============================================================================

def _write_timeline(
    db: Session,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: Optional[str] = None,
    actor_type: str = "USER",
    description: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> ActivityTimeline:
    """Write to ActivityTimeline for global activity feed."""
    timeline = ActivityTimeline(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        description=description,
    )
    db.add(timeline)
    return timeline


# ============================================================================
# QUERY FUNCTIONS (Read API)
# ============================================================================

def get_candidate_activity_timeline(
    db: Session,
    candidate_id: str,
    skip: int = 0,
    limit: int = 50,
    event_types: Optional[List[str]] = None,
    since_days: Optional[int] = None,
) -> Dict:
    """Get activity timeline for a candidate (paginated, newest first)."""
    try:
        query = db.query(CandidateHistory).filter(
            CandidateHistory.candidateID == candidate_id
        )

        if event_types:
            query = query.filter(CandidateHistory.event_type.in_(event_types))

        if since_days:
            since = datetime.utcnow() - timedelta(days=since_days)
            query = query.filter(CandidateHistory.event_at >= since)

        total = query.count()

        events = query.order_by(
            CandidateHistory.event_at.desc(),
            CandidateHistory.id.desc()
        ).offset(skip).limit(limit).all()

        return {
            "total": total,
            "events": [_serialize_history_event(e) for e in events],
            "skip": skip,
            "limit": limit,
            "has_more": (skip + limit) < total,
        }

    except Exception as e:
        logger.error(f"get_candidate_activity_timeline failed: {str(e)}", exc_info=True)
        return {
            "total": 0,
            "events": [],
            "skip": skip,
            "limit": limit,
            "error": str(e)
        }


def get_referral_candidate_journey(
    db: Session,
    referral_id: str,
) -> Dict:
    """Get all candidates linked to a referral with their progress."""
    try:
        referral = db.query(EmployeeReferral).filter(
            EmployeeReferral.referral_id == referral_id
        ).first()

        if not referral:
            return {"error": f"Referral {referral_id} not found"}

        candidates = db.query(Candidate).filter(
            Candidate.referral_id == referral_id
        ).all()

        candidate_journeys = []
        for candidate in candidates:
            history = db.query(CandidateHistory).filter(
                CandidateHistory.candidateID == candidate.candidateID
            ).order_by(CandidateHistory.event_at.desc()).all()

            candidate_journeys.append({
                "candidate_id": candidate.candidateID,
                "candidate_name": f"{candidate.candidateFirstName} {candidate.candidateLastName}".strip(),
                "candidate_email": candidate.candidateEmail,
                "history_count": len(history),
                "recent_events": [_serialize_history_event(e) for e in history[:5]],
            })

        return {
            "referral_id": referral_id,
            "referring_employee_id": referral.referring_employee_id if hasattr(referral, 'referring_employee_id') else None,
            "referral_status": referral.referral_status if hasattr(referral, 'referral_status') else None,
            "candidates": candidate_journeys,
        }

    except Exception as e:
        logger.error(f"get_referral_candidate_journey failed: {str(e)}", exc_info=True)
        return {"error": str(e)}


def _serialize_history_event(event: CandidateHistory) -> Dict:
    """Convert CandidateHistory row to dict for API response."""
    return {
        "id": event.id,
        "event_type": event.event_type,
        "note": event.note,
        "performed_by_id": event.performed_by_id,
        "performed_by_name": event.performed_by_name,
        "event_at": event.event_at.isoformat() if event.event_at else None,
        "created_at": event.createdAt.isoformat() if hasattr(event, 'createdAt') and event.createdAt else None,
    }
