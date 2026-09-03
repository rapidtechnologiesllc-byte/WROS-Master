"""
HRMS-0312 -- Offer Management & Approval (Phase 3)
Complete offer lifecycle: creation → approval → sending → acceptance → employee conversion.
"""
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.offer import Offer, OfferStatus
from app.models.candidate import Candidate
from app.models.user import Users, Jobs
from app.core.logging import logger
import logging
import uuid

logger = logging.getLogger(__name__)

class OfferManagementService:
    """Manages offer creation, approval, sending, and acceptance."""

    def create_offer(
        self,
        db: Session,
        candidate_id: str,
        job_id: str,
        tenant_id: int,
        base_salary_usd_cents: int,
        position_title: str,
        expected_start_date: date,
        benefits: dict = None,
        signing_bonus_usd_cents: int = 0,
        created_by_user_id: str = "system",
        approval_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new offer record.

        Args:
            db: Database session
            candidate_id: Candidate unique identifier
            job_id: Job unique identifier
            tenant_id: Tenant ID
            base_salary_usd_cents: Annual salary in USD cents
            position_title: Job title for the offer
            expected_start_date: Expected start date
            benefits: Benefits package (dict)
            signing_bonus_usd_cents: One-time signing bonus in USD cents
            created_by_user_id: User creating the offer
            approval_notes: Internal notes for approvers

        Returns:
            Dict with success/error status and offer details
        """
        try:
            # Validate candidate exists
            candidate = db.query(Candidate).filter(
                Candidate.candidateID == candidate_id,
                Candidate.tenant_id == tenant_id
            ).first()

            if not candidate:
                logger.warning(f"Candidate {candidate_id} not found for offer creation")
                return {"status": "error", "message": f"Candidate {candidate_id} not found"}

            # Validate job exists
            job = db.query(Jobs).filter(
                Jobs.jobID == job_id,
                Jobs.tenant_id == tenant_id
            ).first()

            if not job:
                logger.warning(f"Job {job_id} not found for offer creation")
                return {"status": "error", "message": f"Job {job_id} not found"}

            # Validate creator exists
            creator = db.query(Users).filter(Users.UserID == created_by_user_id).first()
            if not creator:
                logger.warning(f"Creator {created_by_user_id} not found")
                return {"status": "error", "message": f"Creator user {created_by_user_id} not found"}

            # Create offer
            offer_id = str(uuid.uuid4())
            offer = Offer(
                id=offer_id,
                candidate_id=candidate_id,
                job_id=job_id,
                tenant_id=tenant_id,
                status=OfferStatus.DRAFT,
                base_salary_usd_cents=base_salary_usd_cents,
                signing_bonus_usd_cents=signing_bonus_usd_cents,
                position_title=position_title,
                expected_start_date=expected_start_date,
                benefits=benefits or {},
                created_at=datetime.utcnow(),
                created_by_user_id=created_by_user_id,
                approval_notes=approval_notes
            )

            db.add(offer)
            db.commit()
            db.refresh(offer)

            logger.info(f"Offer {offer_id} created for candidate {candidate_id}, job {job_id}")

            return {
                "status": "success",
                "offer_id": offer_id,
                "candidate_id": candidate_id,
                "job_id": job_id,
                "salary_usd_cents": base_salary_usd_cents,
                "position_title": position_title,
                "start_date": expected_start_date.isoformat(),
                "created_at": offer.created_at.isoformat()
            }

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating offer: {str(e)}")
            return {"status": "error", "message": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Unexpected error creating offer: {str(e)}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

            def approve_offer(
        self,
        db: Session,
        offer_id: str,
        tenant_id: int,
        approved_by_user_id: str,
        approval_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Approve an offer for sending to candidate.

        Args:
            db: Database session
            offer_id: Offer unique identifier
            tenant_id: Tenant ID
            approved_by_user_id: User ID of approver
            approval_notes: Optional approval notes

        Returns:
            Dict with success/error status and approval details
        """
        try:
            offer = db.query(Offer).filter(
                Offer.id == offer_id,
                Offer.tenant_id == tenant_id
            ).first()

            if not offer:
                logger.warning(f"Offer {offer_id} not found for approval")
                return {"status": "error", "message": f"Offer {offer_id} not found"}

            if offer.status != OfferStatus.DRAFT:
                logger.warning(f"Cannot approve offer {offer_id} in {offer.status} status")
                return {
                    "status": "error",
                    "message": f"Cannot approve offer in {offer.status} status. Only DRAFT offers can be approved."
                }

            # Validate approver exists
            approver = db.query(Users).filter(Users.UserID == approved_by_user_id).first()
            if not approver:
                logger.warning(f"Approver {approved_by_user_id} not found")
                return {"status": "error", "message": f"Approver user {approved_by_user_id} not found"}

            offer.status = OfferStatus.APPROVED
            offer.approved_at = datetime.utcnow()
            offer.approved_by_user_id = approved_by_user_id
            if approval_notes:
                offer.approval_notes = approval_notes

            db.commit()
            db.refresh(offer)

            logger.info(f"Offer {offer_id} approved by {approved_by_user_id}")

            return {
                "status": "success",
                "offer_id": offer_id,
                "offer_status": offer.status,
                "approved_at": offer.approved_at.isoformat(),
                "approved_by": approved_by_user_id,
                "approval_notes": offer.approval_notes
            }

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error approving offer {offer_id}: {str(e)}")
            return {"status": "error", "message": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Unexpected error approving offer {offer_id}: {str(e)}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

            def send_offer_to_candidate(
        self,
        db: Session,
        offer_id: str,
        tenant_id: int,
        candidate_email: str,
        expiration_days: int = 7
    ) -> Dict[str, Any]:
        """
        Send offer to candidate via email.

        Args:
            db: Database session
            offer_id: Offer unique identifier
            tenant_id: Tenant ID
            candidate_email: Email to send offer to
            expiration_days: Days until offer expires (default 7)

        Returns:
            Dict with success/error status and send details
        """
        try:
            offer = db.query(Offer).filter(
                Offer.id == offer_id,
                Offer.tenant_id == tenant_id
            ).first()

            if not offer:
                logger.warning(f"Offer {offer_id} not found for sending")
                return {"status": "error", "message": f"Offer {offer_id} not found"}

            if offer.status != OfferStatus.APPROVED:
                logger.warning(f"Cannot send offer {offer_id} in {offer.status} status")
                return {
                    "status": "error",
                    "message": f"Offer must be in APPROVED status before sending. Current status: {offer.status}"
                }

            # Calculate expiration
            sent_time = datetime.utcnow()
            expiration_datetime = sent_time + timedelta(days=expiration_days)

            offer.status = OfferStatus.SENT
            offer.sent_at = sent_time
            offer.sent_to_email = candidate_email
            offer.expiration_date = expiration_datetime

            db.commit()
            db.refresh(offer)

            logger.info(f"Offer {offer_id} sent to {candidate_email}, expires {expiration_datetime}")

            return {
                "status": "success",
                "offer_id": offer_id,
                "offer_status": offer.status,
                "sent_to": candidate_email,
                "sent_at": offer.sent_at.isoformat(),
                "expires_at": expiration_datetime.isoformat()
            }

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error sending offer {offer_id}: {str(e)}")
            return {"status": "error", "message": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Unexpected error sending offer {offer_id}: {str(e)}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

            def accept_offer(
        self,
        db: Session,
        offer_id: str,
        tenant_id: int,
        candidate_id: str
    ) -> dict:
        """Record candidate acceptance of offer."""
        offer = db.query(Offer).filter(
            Offer.id == offer_id,
            Offer.tenant_id == tenant_id
        ).first()

        if not offer:
            return {"status": "error", "message": "Offer not found"}

        if offer.status not in [OfferStatus.SENT, OfferStatus.REVIEWED]:
            return {"status": "error", "message": "Offer cannot be accepted in current status"}

        # Check expiration
        if offer.expiration_date and datetime.utcnow() > offer.expiration_date:
            return {"status": "error", "message": "Offer has expired"}

        offer.status = OfferStatus.ACCEPTED
        offer.accepted_at = datetime.utcnow()
        offer.accepted_by_candidate_id = candidate_id

        # Update candidate status
        candidate = db.query(Candidate).filter(
            Candidate.candidateID == candidate_id,
            Candidate.tenant_id == tenant_id
        ).first()

        if candidate:
            candidate.status = "OFFER_ACCEPTED"

        db.commit()

        return {
            "status": "success",
            "offer_id": offer_id,
            "candidate_id": candidate_id,
            "accepted_at": offer.accepted_at.isoformat(),
            "start_date": offer.expected_start_date.isoformat()
        }

    def reject_offer(
        self,
        db: Session,
        offer_id: str,
        tenant_id: int,
        rejection_reason: str
    ) -> Dict[str, Any]:
        """
        Record rejection of an offer (candidate action).

        Args:
            db: Database session
            offer_id: Offer unique identifier
            tenant_id: Tenant ID
            rejection_reason: Reason for rejection

        Returns:
            Dict with success/error status and rejection details
        """
        try:
            offer = db.query(Offer).filter(
                Offer.id == offer_id,
                Offer.tenant_id == tenant_id
            ).first()

            if not offer:
                logger.warning(f"Offer {offer_id} not found for rejection")
                return {"status": "error", "message": f"Offer {offer_id} not found"}

            # Can only reject offers that have been sent
            if offer.status not in [OfferStatus.SENT, OfferStatus.REVIEWED]:
                logger.warning(f"Cannot reject offer {offer_id} in {offer.status} status")
                return {
                    "status": "error",
                    "message": f"Cannot reject offer in {offer.status} status. Only SENT or REVIEWED offers can be rejected."
                }

            offer.status = OfferStatus.REJECTED
            offer.rejected_at = datetime.utcnow()
            offer.rejection_reason = rejection_reason

            db.commit()
            db.refresh(offer)

            logger.info(f"Offer {offer_id} rejected by candidate. Reason: {rejection_reason}")

            return {
                "status": "success",
                "offer_id": offer_id,
                "offer_status": offer.status,
                "rejected_at": offer.rejected_at.isoformat(),
                "rejection_reason": rejection_reason
            }

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error rejecting offer {offer_id}: {str(e)}")
            return {"status": "error", "message": f"Database error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            db.rollback()
            logger.error(f"Unexpected error rejecting offer {offer_id}: {str(e)}")
            return {"status": "error", "message": f"Unexpected error: {str(e)}"}

            def retract_offer(
        self,
        db: Session,
        offer_id: str,
        tenant_id: int,
        retraction_reason: str
    ) -> dict:
        """Retract offer if candidate hasn't accepted."""
        offer = db.query(Offer).filter(
            Offer.id == offer_id,
            Offer.tenant_id == tenant_id
        ).first()

        if not offer:
            return {"status": "error", "message": "Offer not found"}

        if offer.status == OfferStatus.ACCEPTED:
            return {"status": "error", "message": "Cannot retract accepted offer"}

        offer.status = OfferStatus.RETRACTED
        offer.retracted_at = datetime.utcnow()
        offer.retraction_reason = retraction_reason

        db.commit()

        return {
            "status": "success",
            "offer_id": offer_id,
            "retracted_at": offer.retracted_at.isoformat(),
            "reason": retraction_reason
        }

    def get_offer_summary(
        self,
        db: Session,
        offer_id: str,
        tenant_id: int
    ) -> dict:
        """Get complete offer details."""
        offer = db.query(Offer).filter(
            Offer.id == offer_id,
            Offer.tenant_id == tenant_id
        ).first()

        if not offer:
            return None

        return {
            "offer_id": offer.id,
            "candidate_id": offer.candidate_id,
            "job_id": offer.job_id,
            "status": offer.status,
            "position": offer.position_title,
            "salary": offer.base_salary_usd_cents,
            "signing_bonus": offer.signing_bonus_usd_cents,
            "start_date": offer.expected_start_date.isoformat(),
            "benefits": offer.benefits,
            "created_at": offer.created_at.isoformat(),
            "sent_at": offer.sent_at.isoformat() if offer.sent_at else None,
            "expires_at": offer.expiration_date.isoformat() if offer.expiration_date else None,
            "accepted_at": offer.accepted_at.isoformat() if offer.accepted_at else None,
            "rejected_at": offer.rejected_at.isoformat() if offer.rejected_at else None
        }
