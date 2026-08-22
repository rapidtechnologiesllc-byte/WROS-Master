"""
Phase 1 B6 -- the one sanctioned way to record and check consent.

Fail-closed by design: has_consent() returns False for a subject/type
it has never seen, same posture as tenant_context and audit_log in this
phase. Consent is append-only history (record_consent() always inserts
a new row rather than updating an existing one), so a later "revoked"
record doesn't erase the fact that consent was once granted -- the most
recent row is what governs current behavior.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.consent import ConsentRecord


def record_consent(
    db: Session,
    *,
    subject_type: str,
    subject_id: str,
    consent_type: str,
    consent_given: bool,
    tenant_id: Optional[int] = None,
    captured_by: Optional[str] = None,
) -> ConsentRecord:
    row = ConsentRecord(
        tenant_id=tenant_id,
        subject_type=subject_type,
        subject_id=subject_id,
        consent_type=consent_type,
        consent_given=consent_given,
        captured_by=captured_by,
    )
    db.add(row)
    return row


def has_consent(db: Session, *, subject_type: str, subject_id: str, consent_type: str) -> bool:
    """
    True only if the most recent record for this subject+type says so.
    No record at all -> False (fail closed), not an exception -- callers
    gate an action on this return value directly.
    """
    latest = (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.subject_type == subject_type,
            ConsentRecord.subject_id == subject_id,
            ConsentRecord.consent_type == consent_type,
        )
        .order_by(ConsentRecord.captured_at.desc(), ConsentRecord.id.desc())
        .first()
    )
    return bool(latest and latest.consent_given)
