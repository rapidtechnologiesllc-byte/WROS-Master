"""Background verification (BGV). Created NOT_STARTED when a candidate accepts an offer;
starts (IN_PROGRESS) once the candidate's signed BGV consent document has been received;
ends PASSED or FAILED (a person or the vendor's webhook), or WAIVED with a written reason.
Only PASSED/WAIVED lets a candidate reach the bench and so a client.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.background_verification import BackgroundVerification

logger = logging.getLogger(__name__)

CONSENT_DOCUMENT = "BACKGROUND_CHECK_CONSENT"
TERMINAL = ("PASSED", "FAILED", "WAIVED")


class BGVError(ValueError):
    pass


def ensure_bgv(db: Session, candidate_id: str, offer_id: Optional[int], tenant_id: Optional[int]) -> BackgroundVerification:
    row = db.query(BackgroundVerification).filter(BackgroundVerification.candidate_id == candidate_id,
                                                  BackgroundVerification.offer_letter_id == offer_id).first()
    if row is None:
        row = BackgroundVerification(candidate_id=candidate_id, offer_letter_id=offer_id, tenant_id=tenant_id,
                                     status="NOT_STARTED")
        db.add(row)
        db.flush()
    return row


def consent_received(db: Session, candidate_id: str, offer_id: Optional[int]) -> bool:
    from app.models.preboarding_document import PreboardingDocument

    query = db.query(PreboardingDocument).filter(PreboardingDocument.candidate_id == candidate_id,
                                                 PreboardingDocument.document_type == CONSENT_DOCUMENT,
                                                 PreboardingDocument.status.in_(("RECEIVED", "VERIFIED")))
    if offer_id is not None:
        query = query.filter(PreboardingDocument.offer_id == offer_id)
    return query.first() is not None


def _consent_ok(db: Session, bgv: BackgroundVerification, vendor_name: Optional[str]) -> bool:
    """New hires sign consent among their pre-joining documents. Employees from before the
    pipeline (no offer on the record) gave it outside the system: HR starts their BGV by
    naming the vendor, which records that consent was collected."""
    if consent_received(db, bgv.candidate_id, bgv.offer_letter_id):
        return True
    return bgv.offer_letter_id is None and bool(vendor_name)


def start_if_consented(db: Session, bgv: BackgroundVerification, vendor_name: Optional[str] = None,
                       vendor_reference: Optional[str] = None) -> bool:
    """NOT_STARTED -> IN_PROGRESS once consent is on file. Returns whether it started."""
    if bgv.status != "NOT_STARTED":
        return False
    if not _consent_ok(db, bgv, vendor_name):
        return False
    bgv.status, bgv.initiated_at = "IN_PROGRESS", datetime.utcnow()
    bgv.vendor_name = vendor_name or bgv.vendor_name
    bgv.vendor_reference = vendor_reference or bgv.vendor_reference
    logger.info(f"[BGV] {bgv.id} started for {bgv.candidate_id}")
    return True


def record_verdict(db: Session, bgv: BackgroundVerification, verdict: str, actor: str,
                   report_url: Optional[str] = None, notes: Optional[str] = None) -> BackgroundVerification:
    if verdict not in ("PASSED", "FAILED"):
        raise BGVError("Verdict must be PASSED or FAILED.")
    if bgv.status in TERMINAL:
        raise BGVError(f"Background verification is already {bgv.status}.")
    if bgv.status == "NOT_STARTED" and not _consent_ok(db, bgv, None):
        raise BGVError("The candidate's background check consent has not been received.")
    bgv.status, bgv.verdict_at, bgv.verdict_by = verdict, datetime.utcnow(), actor
    bgv.report_url = report_url or bgv.report_url
    bgv.notes = notes or bgv.notes
    if bgv.initiated_at is None:
        bgv.initiated_at = bgv.verdict_at
    logger.info(f"[BGV] {bgv.id} {verdict} by {actor}")
    return bgv


def waive(db: Session, bgv: BackgroundVerification, reason: str, user_id: str) -> BackgroundVerification:
    if not (reason or "").strip():
        raise BGVError("A reason is required to waive background verification.")
    if bgv.status in ("PASSED", "FAILED"):
        raise BGVError(f"Background verification is already {bgv.status}.")
    bgv.status, bgv.waiver_reason = "WAIVED", reason.strip()
    bgv.verdict_at, bgv.verdict_by = datetime.utcnow(), user_id
    return bgv
