"""Delivery Centers endpoint - List available office locations for employee assignment"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.delivery_center import DeliveryCenter
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/delivery-centers", tags=["Delivery Centers"])


@router.get("", response_model=list)
async def list_delivery_centers(db: Session = Depends(get_db)):
    """
    List all active delivery centers.

    Used for employee assignment - which office location they report from.
    Examples: Bangalore, Delhi, Chennai, Hyderabad, Remote
    """
    centers = db.query(DeliveryCenter).filter(DeliveryCenter.active == True).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "code": c.code,
            "location": c.location,
            "description": c.description
        }
        for c in centers
    ]


@router.get("/{delivery_center_id}", response_model=dict)
async def get_delivery_center(delivery_center_id: int, db: Session = Depends(get_db)):
    """Get a specific delivery center by ID."""
    center = db.query(DeliveryCenter).filter(
        DeliveryCenter.id == delivery_center_id,
        DeliveryCenter.active == True
    ).first()

    if not center:
        raise HTTPException(status_code=404, detail="Delivery center not found")

    return {
        "id": center.id,
        "name": center.name,
        "code": center.code,
        "location": center.location,
        "description": center.description,
        "contact_email": center.contact_email,
        "contact_phone": center.contact_phone
    }
