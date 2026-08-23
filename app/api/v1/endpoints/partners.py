"""Partners API endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.tenant_context import get_current_tenant
from app.models.partner import Partner

router = APIRouter(prefix="/partners", tags=["partners"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
def get_all_partners(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant)
):
    """Get all active partners for the tenant"""
    partners = db.query(Partner).filter(
        Partner.tenant_id == tenant_id,
        Partner.active == True
    ).all()

    return {
        "partners": [
            {
                "id": p.id,
                "name": p.name,
                "code": p.code,
                "description": p.description,
                "website": p.website,
                "contact_email": p.contact_email,
                "contact_phone": p.contact_phone
            }
            for p in partners
        ]
    }


@router.get("/{partner_id}")
def get_partner(
    partner_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant)
):
    """Get a specific partner"""
    partner = db.query(Partner).filter(
        Partner.id == partner_id,
        Partner.tenant_id == tenant_id
    ).first()

    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    return {
        "id": partner.id,
        "name": partner.name,
        "code": partner.code,
        "description": partner.description,
        "website": partner.website,
        "contact_email": partner.contact_email,
        "contact_phone": partner.contact_phone
    }
