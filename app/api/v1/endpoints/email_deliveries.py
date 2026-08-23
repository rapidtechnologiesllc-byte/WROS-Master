"""Email Delivery Tracking API for monitoring candidate stage progression emails."""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.core.dependencies import require_resource_permission, get_current_hr_or_admin
from app.models.email_template import EmailDelivery
from app.core.logging import logger

router = APIRouter(prefix="/email-deliveries", tags=["email-deliveries"])


class EmailDeliveryResponse:
    """Response schema for email delivery."""
    def __init__(self, delivery: EmailDelivery):
        self.id = str(delivery.id)
        self.candidate_id = str(delivery.candidate_id) if delivery.candidate_id else None
        self.stage = delivery.stage
        self.recipient_email = delivery.recipient_email
        self.subject = delivery.subject
        self.status = delivery.status
        self.error_message = delivery.error_message
        self.sent_at = delivery.sent_at.isoformat() if delivery.sent_at else None
        self.opened_at = delivery.opened_at.isoformat() if delivery.opened_at else None
        self.clicked_at = delivery.clicked_at.isoformat() if delivery.clicked_at else None
        self.created_at = delivery.created_at.isoformat() if delivery.created_at else None


@router.get(
    "",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get all email deliveries"
)
def get_all_deliveries(
    status: Optional[str] = None,
    stage: Optional[str] = None,
    candidate_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Get email delivery records with optional filters."""
    query = db.query(EmailDelivery)

    if status:
        query = query.filter(EmailDelivery.status == status)
    if stage:
        query = query.filter(EmailDelivery.stage == stage)
    if candidate_id:
        query = query.filter(EmailDelivery.candidate_id == candidate_id)

    total = query.count()
    deliveries = query.order_by(EmailDelivery.sent_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "deliveries": [EmailDeliveryResponse(d).__dict__ for d in deliveries]
    }


@router.get(
    "/candidate/{candidate_id}",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get email history for a candidate"
)
def get_candidate_email_history(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Get all emails sent to a specific candidate."""
    deliveries = db.query(EmailDelivery).filter(
        EmailDelivery.candidate_id == candidate_id
    ).order_by(EmailDelivery.sent_at.desc()).all()

    return {
        "candidate_id": candidate_id,
        "total": len(deliveries),
        "deliveries": [EmailDeliveryResponse(d).__dict__ for d in deliveries]
    }


@router.get(
    "/stats/summary",
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get email delivery statistics"
)
def get_delivery_stats(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Get summary statistics for email deliveries."""
    total = db.query(EmailDelivery).count()
    sent = db.query(EmailDelivery).filter(EmailDelivery.status == "sent").count()
    failed = db.query(EmailDelivery).filter(EmailDelivery.status == "failed").count()
    opened = db.query(EmailDelivery).filter(EmailDelivery.status == "opened").count()
    clicked = db.query(EmailDelivery).filter(EmailDelivery.status == "clicked").count()

    # By stage
    by_stage = {}
    for stage in ["screening", "interview", "offer", "hired", "rejected"]:
        by_stage[stage] = {
            "total": db.query(EmailDelivery).filter(EmailDelivery.stage == stage).count(),
            "sent": db.query(EmailDelivery).filter(
                EmailDelivery.stage == stage,
                EmailDelivery.status == "sent"
            ).count(),
            "opened": db.query(EmailDelivery).filter(
                EmailDelivery.stage == stage,
                EmailDelivery.status == "opened"
            ).count(),
        }

    success_rate = (sent / total * 100) if total > 0 else 0
    open_rate = (opened / sent * 100) if sent > 0 else 0
    click_rate = (clicked / sent * 100) if sent > 0 else 0

    return {
        "total_emails": total,
        "by_status": {
            "sent": sent,
            "failed": failed,
            "opened": opened,
            "clicked": clicked,
        },
        "rates": {
            "success_rate": f"{success_rate:.1f}%",
            "open_rate": f"{open_rate:.1f}%",
            "click_rate": f"{click_rate:.1f}%",
        },
        "by_stage": by_stage,
    }


@router.put(
    "/{delivery_id}/mark-opened",
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Mark email as opened"
)
def mark_email_opened(
    delivery_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Mark an email as opened (called by email tracking pixel)."""
    delivery = db.query(EmailDelivery).filter(EmailDelivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Email delivery not found")

    delivery.status = "opened"
    delivery.opened_at = datetime.utcnow()
    db.commit()

    logger.info(f"Marked email {delivery_id} as opened")

    return {"status": "success", "message": "Email marked as opened"}


@router.put(
    "/{delivery_id}/mark-clicked",
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Mark email as clicked"
)
def mark_email_clicked(
    delivery_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """Mark an email as clicked (called by link tracking)."""
    delivery = db.query(EmailDelivery).filter(EmailDelivery.id == delivery_id).first()
    if not delivery:
        raise HTTPException(status_code=404, detail="Email delivery not found")

    delivery.status = "clicked"
    delivery.clicked_at = datetime.utcnow()
    db.commit()

    logger.info(f"Marked email {delivery_id} as clicked")

    return {"status": "success", "message": "Email marked as clicked"}
