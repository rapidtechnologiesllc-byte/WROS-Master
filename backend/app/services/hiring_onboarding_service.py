"""Pre-joining onboarding, started by the hiring pipeline when a candidate accepts an offer.

start_onboarding(db, pipeline)  -> document requests (ID, address, salary slip, experience,
                                   education, PAN for India, BGV consent), the configured
                                   pre-joining checklist, a NOT_STARTED BGV record, and an
                                   email with the candidate's portal link. Idempotent.
portal_onboarding(db, candidate) -> what the candidate still has to do (portal)
receive_document(...)           -> candidate uploaded a document (portal): RECEIVED
review_document(...)            -> HR verifies or waives a document
Every change notifies the pipeline, which moves the candidate to BGV once all mandatory
documents are verified (or waived) and the checklist is completed.
"""
import logging
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.checklist import CandidateChecklist, ChecklistTemplate
from app.models.offer_letter import OfferLetter
from app.models.pipeline_email import PipelineEmail
from app.models.preboarding_document import PreboardingDocument

logger = logging.getLogger(__name__)

PIPELINE_EMAIL_TASK = "send_pipeline_email"


class OnboardingError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _tenant_key(candidate: Candidate) -> str:
    return str(candidate.tenant_id or 1)


def queue_candidate_email(db: Session, candidate: Candidate, kind: str, ref: str) -> Optional[str]:
    """Records the intended email (once per kind/ref) and queues it. Call before commit;
    returns the email id to queue after commit (None if it already exists)."""
    email_id = f"pe:{kind}:{candidate.candidateID}:{ref}"[:255]
    if db.query(PipelineEmail.id).filter(PipelineEmail.id == email_id).first():
        return None
    db.add(PipelineEmail(id=email_id, tenant_id=candidate.tenant_id, candidate_id=candidate.candidateID,
                         kind=kind, ref=ref))
    return email_id


def enqueue_email(email_id: Optional[str], candidate: Candidate) -> None:
    if email_id is None:
        return
    from app.services.thunder_mail.cadence_service import enqueue_once

    enqueue_once(PIPELINE_EMAIL_TASK, email_id, {"email_id": email_id, "candidate_id": candidate.candidateID},
                 candidate.tenant_id)


def start_onboarding(db: Session, pipeline) -> str:
    """Stage action for ONBOARDING. Commits."""
    from app.services.bgv_service import ensure_bgv
    from app.services.checklist_assignment_service import ChecklistAlreadyAssigned, assign_template
    from app.services.document_collection_service import _required_documents_for
    from app.services.system_config_service import get_config_value

    candidate = db.query(Candidate).filter(Candidate.candidateID == pipeline.candidate_id).first()
    offer = db.query(OfferLetter).filter(OfferLetter.id == pipeline.offer_letter_id).first()
    if candidate is None or offer is None:
        raise ValueError(f"Pipeline {pipeline.id}: candidate or accepted offer missing")
    tenant = _tenant_key(candidate)
    created = 0
    if not db.query(PreboardingDocument.id).filter(PreboardingDocument.candidate_id == candidate.candidateID,
                                                   PreboardingDocument.offer_id == offer.id).first():
        for doc_type, label in _required_documents_for(candidate):
            db.add(PreboardingDocument(tenant_id=tenant, candidate_id=candidate.candidateID, offer_id=offer.id,
                                       document_type=doc_type, document_label=label, is_mandatory=True))
            created += 1
    checklist_note = "no pre-joining checklist configured"
    template_id = int(get_config_value(db, tenant_id=candidate.tenant_id or 1, key="prejoining_checklist_template_id") or 0)
    if template_id:
        template = db.query(ChecklistTemplate).filter(ChecklistTemplate.id == template_id).first()
        if template is None:
            checklist_note = f"configured checklist template {template_id} does not exist"
        else:
            try:
                assign_template(db, candidate.candidateID, template, None)
                checklist_note = f"checklist '{template.name}' assigned"
            except ChecklistAlreadyAssigned:
                checklist_note = f"checklist '{template.name}' already assigned"
    ensure_bgv(db, candidate.candidateID, offer.id, candidate.tenant_id)
    email_id = queue_candidate_email(db, candidate, "ONBOARDING_START", str(offer.id))
    db.commit()
    enqueue_email(email_id, candidate)
    return f"{created} documents requested; {checklist_note}; BGV record created; onboarding email queued"


def _accepted_offer(db: Session, candidate_id: str) -> Optional[OfferLetter]:
    return db.query(OfferLetter).filter(OfferLetter.candidate_id == candidate_id,
                                        OfferLetter.offer_status == "Accepted").order_by(OfferLetter.id.desc()).first()


def portal_onboarding(db: Session, candidate: Candidate) -> Dict:
    offer = _accepted_offer(db, candidate.candidateID)
    docs = [] if offer is None else db.query(PreboardingDocument).filter(
        PreboardingDocument.candidate_id == candidate.candidateID, PreboardingDocument.offer_id == offer.id,
        PreboardingDocument.status != "CANCELLED").order_by(PreboardingDocument.id).all()
    checklists = db.query(CandidateChecklist).filter(CandidateChecklist.candidate_id == candidate.candidateID).all()
    return {
        "offer_id": offer.id if offer else None,
        "joining_date": offer.joining_date if offer else None,
        "documents": [{"id": d.id, "type": d.document_type, "label": d.document_label, "status": d.status,
                       "mandatory": d.is_mandatory, "received_at": d.received_at} for d in docs],
        "checklists": [{"id": c.id, "name": c.template_name, "status": c.status} for c in checklists],
    }


def _own_document(db: Session, candidate: Candidate, doc_id: int) -> PreboardingDocument:
    doc = db.query(PreboardingDocument).filter(PreboardingDocument.id == doc_id).with_for_update().first()
    if doc is None or doc.candidate_id != candidate.candidateID:
        raise OnboardingError(f"Document {doc_id} not found", 404)
    return doc


def receive_document(db: Session, candidate: Candidate, doc_id: int, document_url: Optional[str]) -> PreboardingDocument:
    """The candidate uploaded the file for a requested document. Commits."""
    doc = _own_document(db, candidate, doc_id)
    if doc.status in ("VERIFIED", "WAIVED", "CANCELLED"):
        raise OnboardingError(f"{doc.document_label} is already {doc.status.lower()}.")
    doc.status, doc.document_url, doc.received_at = "RECEIVED", document_url, datetime.utcnow()
    _start_bgv_on_consent(db, doc)
    db.commit()
    _notify(doc, "document_received")
    return doc


def review_document(db: Session, doc_id: int, decision: str, user_id: str, tenant_id: Optional[int]) -> PreboardingDocument:
    """HR: VERIFIED (it's what we asked for), WAIVED (not needed for this hire) or PENDING
    (rejected: the candidate must upload it again). Commits."""
    if decision not in ("VERIFIED", "WAIVED", "PENDING"):
        raise OnboardingError("Decision must be VERIFIED, WAIVED or PENDING.")
    doc = db.query(PreboardingDocument).filter(PreboardingDocument.id == doc_id).with_for_update().first()
    if doc is None or (tenant_id is not None and doc.tenant_id != str(tenant_id)):
        raise OnboardingError(f"Document {doc_id} not found", 404)
    if decision == "VERIFIED" and doc.status != "RECEIVED":
        raise OnboardingError(f"{doc.document_label} has not been uploaded yet.")
    doc.status = decision
    if decision == "PENDING":
        doc.document_url, doc.received_at = None, None
    _start_bgv_on_consent(db, doc)
    db.commit()
    logger.info(f"[Onboarding] document {doc.id} {decision} by {user_id}")
    _notify(doc, f"document_{decision.lower()}")
    return doc


def _start_bgv_on_consent(db: Session, doc: PreboardingDocument) -> None:
    from app.services.bgv_service import CONSENT_DOCUMENT, ensure_bgv, start_if_consented

    if doc.document_type != CONSENT_DOCUMENT or doc.status not in ("RECEIVED", "VERIFIED"):
        return
    db.flush()
    start_if_consented(db, ensure_bgv(db, doc.candidate_id, doc.offer_id, None))


def _notify(doc: PreboardingDocument, trigger: str) -> None:
    from app.services.hiring_pipeline_service import notify

    # timestamped: a re-upload after a rejection must re-evaluate too, not dedupe away
    notify(doc.candidate_id, trigger, f"{doc.id}:{doc.status}:{datetime.utcnow().isoformat()}")
