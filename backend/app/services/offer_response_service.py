"""A candidate accepts or declines their offer. One implementation for every entry point:
POST /offer-letter/respond, POST /portal/offers/{id}/respond and (accept only) /offer-letter/sign.

respond_to_offer(db, candidate, offer_id, action, message) -> OfferLetter
    Only the candidate's own Released offer can be answered. Accept -> "Accepted";
    decline -> "Rejected" and the candidate returns to the org pool. Commits.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateStatus
from app.models.offer_letter import OfferLetter
from app.models.user import Users

logger = logging.getLogger(__name__)

ACCEPT, DECLINE = "accept", "decline"
_ACTIONS = {"accept": ACCEPT, "decline": DECLINE, "reject": DECLINE}


class OfferResponseError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def candidate_offers(db: Session, candidate: Candidate):
    """Offers the candidate can see: released to them, or already answered."""
    return db.query(OfferLetter).filter(
        OfferLetter.candidate_id == candidate.candidateID,
        OfferLetter.offer_status.in_(["Released", "Accepted", "Rejected"]),
    ).order_by(OfferLetter.id.desc()).all()


def own_released_offer(db: Session, candidate: Candidate, offer_id: int) -> OfferLetter:
    offer = db.query(OfferLetter).filter(OfferLetter.id == offer_id).with_for_update().first()
    if offer is None or offer.candidate_id != candidate.candidateID:
        raise OfferResponseError(f"Offer {offer_id} not found", 404)
    if offer.offer_status != "Released":
        raise OfferResponseError(
            f"Offer is '{offer.offer_status}'. Only a released offer can be answered.", 400)
    return offer


def set_pipeline_status(db: Session, candidate_id: str, value: str) -> None:
    status = db.query(CandidateStatus).filter(CandidateStatus.candidateID == candidate_id).first()
    if status is None:
        db.add(CandidateStatus(candidateID=candidate_id, status="Active", piplineStatus=value))
    else:
        status.piplineStatus = value


def respond_to_offer(db: Session, candidate: Candidate, offer_id: int, action: str,
                     message: Optional[str] = None) -> OfferLetter:
    normalized = _ACTIONS.get((action or "").strip().lower())
    if normalized is None:
        raise OfferResponseError("Action must be 'accept' or 'decline'.", 400)
    offer = own_released_offer(db, candidate, offer_id)
    offer.offer_status = "Accepted" if normalized == ACCEPT else "Rejected"
    offer.candidate_response = message
    offer.responded_at = datetime.now()
    set_pipeline_status(db, offer.candidate_id, "Hired" if normalized == ACCEPT else "Rejected")
    if normalized == DECLINE:
        from app.services.candidate_pool_service import set_org_pool

        set_org_pool(
            candidate_id=offer.candidate_id,
            reason=f"Candidate declined offer #{offer.id} - returned to Org Pool",
            db=db,
            performed_by_id=candidate.candidateID,
            performed_by_name=(f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip()
                               or candidate.candidateEmail),
        )
    db.commit()
    db.refresh(offer)
    logger.info(f"[Offer] {offer.id} {offer.offer_status} by candidate {candidate.candidateID}")
    after_response(db, offer, candidate, message)
    return offer


def after_response(db: Session, offer: OfferLetter, candidate: Candidate, message: Optional[str] = None) -> None:
    """After commit: tell the offer's creator. Their email is a courtesy; the offer state is
    already saved, so a mail failure is logged, not raised."""
    creator = db.query(Users).filter(Users.UserID == offer.created_by).first()
    if creator is None or not creator.UserEmail:
        return
    from app.services.email_service import EmailService

    name = f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip() or offer.candidate_id
    try:
        EmailService.notify_hr_candidate_responded(
            hr_email=creator.UserEmail, candidate_name=name, position=offer.position or "",
            offer_id=offer.id, decision=offer.offer_status, response_message=message or "")
    except Exception as exc:
        logger.error(f"[Offer] could not email {offer.created_by} about offer {offer.id}: {exc}", exc_info=True)
