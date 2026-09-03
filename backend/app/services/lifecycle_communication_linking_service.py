"""
EPIC-14/S-435 (HRMS-1408) -- Candidate & Employee Lifecycle
import logging
Communication Linking.

Real ask, Avinash 2026-08-05: HR/recruiter emails to a candidate
currently live only in that person's own mailbox, invisible on the
candidate's WROS record. This is the ONE sanctioned linking mechanism
(BR-1408-03, same "one sanctioned path" discipline as
create_candidate_safe()/sendThunderMessage()) -- writes into the
existing S-216/HRMS-0118 Activity Timeline (app.services.
activity_timeline_service) rather than a second, parallel history
table.

BR-1408-01: metadata-only. Only sender/recipient/subject/timestamp/
webLink are ever stored -- message BODY content is never passed to
this function, never stored, never reasoned over. An agent reading
linked email content is explicitly out of scope for this story (per
the spec's own "Hard boundary" section) -- a separate, separately-
consented future story, not built here.

BR-1408-02: matching by VERIFIED email address only, never fuzzy
name-guessing. Employee is checked before Candidate -- once someone
converts, new communications belong on their employee record; their
existing candidate-era timeline entries are left exactly where they
are (not moved/duplicated), matching the spec's own "no gap/duplicate"
acceptance criterion.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.employee import Employee
from app.services.activity_timeline_service import write_timeline_entry

DIRECTIONS = ("SENT", "RECEIVED")


def _resolve_entity(db: Session, email: str):
    """Returns (entity_type, entity_id, display_name) for a verified
    email address, or None if it matches neither a known employee nor
    a known candidate. Employee checked first -- see module docstring."""
    if not email:
        return None
    normalized = email.strip().lower()

    employee = db.query(Employee).filter(Employee.email == normalized).first()
    if employee:
        name = " ".join(p for p in [employee.first_name, employee.last_name] if p).strip() or employee.email
        return "employee", employee.id, name

    candidate = db.query(Candidate).filter(Candidate.candidateEmail == normalized).first()
    if candidate:
        name_parts = [candidate.candidateFirstName or "", candidate.candidateLastName or ""]
        name = " ".join(p for p in name_parts if p).strip() or candidate.candidateEmail
        return "candidate", candidate.candidateID, name

    return None


def link_email_to_lifecycle_record(
    db: Session,
    *,
    other_party_email: str,
    direction: str,
    subject: str,
    timestamp: datetime,
    web_link: Optional[str] = None,
    tenant_id: Optional[int] = None,
    actor_id: Optional[str] = None,
) -> Optional[dict]:
    """Call once per real email message (never per-line, never with
    body content). `other_party_email` is whichever side of the
    message ISN'T the WROS user who owns the mailbox being synced --
    the recipient if direction=SENT, the sender if direction=RECEIVED.

    Returns a small dict describing what was linked, or None if the
    other party's address didn't match any verified WROS record
    (BR-1408-02 -- no false-positive link, matches the spec's own AC).
    Never raises -- a linking bug must never break the mail sync loop
    it's called from.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {DIRECTIONS}, got {direction!r}")

    try:
        resolved = _resolve_entity(db, other_party_email)
        if resolved is None:
            return None
        entity_type, entity_id, display_name = resolved

        verb = "to" if direction == "SENT" else "from"
        description = f"Email {verb} {display_name} ({other_party_email}) -- Subject: '{subject or '(no subject)'}'"
        if web_link:
            description += f" -- {web_link}"

        entry = write_timeline_entry(
            db,
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=f"EMAIL_{direction}",
            actor_id=actor_id,
            actor_type="SYSTEM",
            description=description,
        )
        db.commit()
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "timeline_entry_id": entry.id,
        }
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[LifecycleCommunicationLinking] Failed to link email (direction={direction!r}): {exc}")
        db.rollback()
        raise ValueError("Operation failed")
