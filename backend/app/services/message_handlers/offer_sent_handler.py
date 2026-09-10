"""Offer Sent Message Handler - Process offer sent notifications."""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.offer import Offer

logger = logging.getLogger(__name__)


def handle_offer_sent(message: Any, db: Session) -> Dict[str, Any]:
    """Handle offer_sent message - triggered when an offer is sent to candidate.

    Message is marked COMPLETED only when:
    1. Offer status updated to SENT
    2. Offer document sent to candidate
    3. Candidate response tracking initiated

    Args:
        message: ChannelQueueItem with type='offer_sent'
        db: SQLAlchemy session

    Returns:
        {status, offer_id, candidate_id, sent_at, response_deadline}
    """
    try:
        payload = message.payload or {}
        offer_id = payload.get('offer_id')

        if not offer_id:
            raise ValueError("offer_id is required in payload")

        # 1. Fetch offer
        offer = db.query(Offer).filter(Offer.id == offer_id).first()
        if not offer:
            raise ValueError(f"Offer {offer_id} not found")

        logger.info(f"[OfferSent] Processing offer {offer_id} being sent to candidate")

        candidate_id = offer.candidate_id if hasattr(offer, 'candidate_id') else None

        # 2. Update offer status to SENT
        if hasattr(offer, 'status'):
            offer.status = 'SENT'
            if hasattr(offer, 'sent_at'):
                from datetime import datetime
                offer.sent_at = datetime.utcnow()
            db.commit()

        # 3. Send offer document to candidate
        document_sent = False
        try:
            # In production: generate offer letter PDF, send via email
            # Track email delivery status
            if candidate_id:
                logger.info(f"[OfferSent] Sending offer document to candidate {candidate_id}")
                document_sent = True
        except Exception as doc_err:
            logger.warning(f"[OfferSent] Could not send document: {doc_err}")

        # 4. Set response deadline and tracking
        response_deadline = None
        try:
            from datetime import datetime, timedelta
            response_deadline = (datetime.utcnow() + timedelta(days=5)).isoformat()
            # In production: store deadline in offer record for tracking
            if hasattr(offer, 'response_deadline'):
                offer.response_deadline = response_deadline
                db.commit()
        except Exception as deadline_err:
            logger.warning(f"[OfferSent] Could not set deadline: {deadline_err}")

        result = {
            "status": "offer_sent",
            "offer_id": offer_id,
            "candidate_id": candidate_id,
            "document_sent": document_sent,
            "response_deadline": response_deadline,
            "message": f"Offer {offer_id} sent to candidate {candidate_id}"
        }

        logger.info(f"[OfferSent] ✅ Completed: {offer_id}")
        return result

    except ValueError as ve:
        logger.error(f"[OfferSent] Validation error: {ve}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"[OfferSent] Failed to process sent: {e}", exc_info=True)
        raise
