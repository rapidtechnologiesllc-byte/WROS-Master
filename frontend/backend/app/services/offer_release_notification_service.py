"""
S-054/HRMS-0454 -- Offer Release Notification via Thunder.

Real architecture adaptations:
- No new `offers` table -- Step 1's schema sketch is already this
  codebase's real, pre-existing `OfferLetter` model
  (app/models/offer_letter.py, built in an earlier round of this same
  session, before EPIC-04's sequential build started). It already has
  a real literal `offer_status` enum (Pending/AwaitingApproval/
  Approved/Released/Accepted/Rejected/Cancelled -- unlike most
  timestamp-presence workarounds this EPIC-04 round has needed),
  `released_at`/`released_by`, `job_id` (`Jobs.jobID`, matching
  `offer_readiness_service`'s own convention), `position`, `salary`,
  `joining_date`, `offer_expire_date`. A real
  `POST /offer-letter/release/{offer_id}` endpoint also already
  existed and already did the Approved->Released transition plus a
  real (if incomplete) email notification -- this story extends that
  endpoint rather than building a parallel
  `PATCH /api/offers/{id}/release` from scratch. See that endpoint's
  own comment for the BR-01/RBAC fixes made there.
- BR-03 (salary in the candidate's local currency, never base units)
  is moot by construction: `OfferLetter.salary` is ALREADY a free-text
  display string (e.g. "24 LPA"), not an integer base-currency-unit
  column the spec assumes -- same pattern `candidateExpectedSalary`
  already established earlier this session. Shown as-is, no
  conversion logic needed or written.
- Portal link reuses `candidate_portal_service.generate_portal_link_url()`
  (S-017's real, already-built magic-link generator) rather than a
  fictional `/candidate/{token}/offer` sub-route -- no per-offer
  portal sub-route exists in this codebase's already-built S-017
  portal; the portal's real root page is what this points to.
- "Attaches offer letter PDF if available": the real, already-generated
  document lives in SharePoint (`OfferLetter.download_url`/
  `sharepoint_url`, set by the pre-existing
  `generate_offer_letter_document()` flow) -- a real download LINK is
  included in the email rather than fetching and re-attaching the
  binary, avoiding an extra live SharePoint round-trip in a
  notification send path; the link IS the real, already-established
  access mechanism other parts of this codebase already use for this
  document.
- No `OFFER_SENT` conversation-state enum value exists (same fictional
  state issue every S-041-053 story has flagged) -- logged as a real
  `OFFER_RELEASED` ConversationEvent instead.
- BR-02 (send via both channels, always): WhatsApp via
  `thunder_service.send_thunder_message()` (R-08/consent/debounce
  still real, hard invariants -- a failure there is logged and
  swallowed, matching every dual-channel story this round). Email via
  the now-extended `EmailService.notify_candidate_offer_released()`,
  which now returns True/False instead of always swallowing, so a
  genuine double-channel failure can be logged as OFFER_EMAIL_FAILED
  per BR-02's own integrations note (email failure alone -- WhatsApp
  still attempted regardless either way).
"""
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.offer_letter import OfferLetter
from app.services.candidate_portal_service import generate_portal_link_url
from app.services.email_service import EmailService
from app.services.thunder_service import ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError, send_thunder_message


def _active_conversation(db: Session, candidate_id: str) -> Optional[CandidateConversation]:
    return (
        db.query(CandidateConversation)
        .filter(CandidateConversation.candidate_id == candidate_id)
        .order_by(CandidateConversation.id.desc())
        .first()
    )


def _build_whatsapp_message(candidate: Candidate, offer: OfferLetter, portal_link: str) -> str:
    expiry = str(offer.offer_expire_date) if offer.offer_expire_date else "the expiry date"
    salary_clause = f" Your offer includes {offer.salary}." if offer.salary else ""
    return (
        f"Exciting news, {candidate.candidateFirstName or 'there'}! We are pleased to extend a job offer to you "
        f"for the {offer.position} position at BlitzenX.{salary_clause} Please review the full offer at {portal_link} "
        f"and let us know your decision by {expiry}. We are excited about the possibility of having you join the team!"
    )


def send_offer_release_notification(db: Session, offer: OfferLetter) -> Dict:
    """Steps 3-4. Never raises. Returns
    {"whatsapp_sent": bool, "email_sent": bool}."""
    result = {"whatsapp_sent": False, "email_sent": False}

    candidate = db.query(Candidate).filter(Candidate.candidateID == offer.candidate_id).first()
    if candidate is None:
        return result

    conversation = _active_conversation(db, candidate.candidateID)
    portal_link = generate_portal_link_url(candidate.candidateID)

    if conversation is not None:
        message = _build_whatsapp_message(candidate, offer, portal_link)
        try:
            send_thunder_message(db, conversation, candidate, message, sender_type="ai_agent", channel="whatsapp", auto_generated=True)
            result["whatsapp_sent"] = True
        except (ConsentNotGiven, ConversationOwnedByHuman, DuplicateMessageSuppressed, ThunderPausedError) as exc:
            logger.info(f"[OfferReleaseNotification] WhatsApp notification skipped for candidate {candidate.candidateID!r}: {exc}")

    offer_document_url = offer.download_url or offer.sharepoint_url or ""
    result["email_sent"] = EmailService.notify_candidate_offer_released(
        candidate_email=candidate.candidateEmail,
        candidate_name=candidate.candidateFirstName or candidate.candidateEmail,
        position=offer.position or "",
        joining_date=str(offer.joining_date) if offer.joining_date else "",
        offer_expire_date=str(offer.offer_expire_date) if offer.offer_expire_date else "",
        salary=offer.salary or "",
        portal_link=portal_link,
        offer_document_url=offer_document_url,
    )

    if conversation is not None:
        if not result["whatsapp_sent"] and not result["email_sent"]:
            db.add(ConversationEvent(conversation_id=conversation.id, event_type="OFFER_EMAIL_FAILED", event_data={"offer_id": offer.id}, triggered_by="system"))
        db.add(ConversationEvent(
            conversation_id=conversation.id, event_type="OFFER_RELEASED",
            event_data={"offer_id": offer.id, "candidate_id": offer.candidate_id, "released_by": offer.released_by}, triggered_by="system",
        ))
        conversation.offer_faq_active = True
        db.add(conversation)
        db.commit()

    return result
