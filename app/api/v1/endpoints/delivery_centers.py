"""Delivery Centers API endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.tenant_context import get_current_tenant
from app.models.delivery_center import DeliveryCenter

router = APIRouter(prefix="/delivery-centers", tags=["delivery-centers"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
def get_all_delivery_centers(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant)
):
    """Get all active delivery centers for the tenant"""
    delivery_centers = db.query(DeliveryCenter).filter(
        DeliveryCenter.tenant_id == tenant_id,
        DeliveryCenter.active == True
    ).all()

    return {
        "delivery_centers": [
            {
                "id": dc.id,
                "name": dc.name,
                "code": dc.code,
                "description": dc.description,
                "location": dc.location,
                "contact_email": dc.contact_email,
                "contact_phone": dc.contact_phone
            }
            for dc in delivery_centers
        ]
    }


@router.get("/{delivery_center_id}")
def get_delivery_center(
    delivery_center_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant)
):
    """Get a specific delivery center"""
    delivery_center = db.query(DeliveryCenter).filter(
        DeliveryCenter.id == delivery_center_id,
        DeliveryCenter.tenant_id == tenant_id
    ).first()

    if not delivery_center:
        raise HTTPException(status_code=404, detail="Delivery center not found")

    return {
        "id": delivery_center.id,
        "name": delivery_center.name,
        "code": delivery_center.code,
        "description": delivery_center.description,
        "location": delivery_center.location,
        "contact_email": delivery_center.contact_email,
        "contact_phone": delivery_center.contact_phone
    }
