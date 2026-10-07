"""Business Unit management endpoints - BU → Client → Job workflow"""
from sqlalchemy import text
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.permission_registry import Permissions
from app.models.business_unit import BusinessUnit
from app.models.user import Users
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/business-units", tags=["business-units"])


class BusinessUnitResponse(BaseModel):
    id: int
    name: str
    display_name: str
    bu_code: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[str] = None
    active: bool = True

    class Config:
        from_attributes = True


class BusinessUnitCreateRequest(BaseModel):
    name: str
    display_name: str
    bu_code: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[str] = None


class ClientResponse(BaseModel):
    id: str
    name: str
    email: str = None
    phone: str = None
    business_unit_id: int

    class Config:
        from_attributes = True


@router.get("", response_model=List[BusinessUnitResponse], dependencies=[Depends(require_resource_permission("business-units", "view"))])
async def get_business_units(
    db: Session = Depends(get_db),
):
    """Get all active business units from database"""
    try:
        business_units = db.query(BusinessUnit).filter(BusinessUnit.active == True).order_by(BusinessUnit.name).all()
        return business_units
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch business units: {str(e)}"
        )


@router.post("", response_model=BusinessUnitResponse, dependencies=[Depends(require_resource_permission("business-units", "can_create"))])
async def create_business_unit(
    request: BusinessUnitCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Create a new business unit"""
    try:
        if not request.name.strip():
            raise HTTPException(status_code=400, detail="Business unit name is required")

        if not request.display_name.strip():
            raise HTTPException(status_code=400, detail="Display name is required")

        # Check for duplicate bu_code if provided
        if request.bu_code:
            existing = db.query(BusinessUnit).filter(BusinessUnit.bu_code == request.bu_code).first()
            if existing:
                raise HTTPException(status_code=409, detail=f"Business unit code '{request.bu_code}' already exists")

        business_unit = BusinessUnit(
            name=request.name,
            display_name=request.display_name,
            bu_code=request.bu_code,
            description=request.description,
            manager_id=request.manager_id,
            active=True
        )
        db.add(business_unit)
        db.commit()
        db.refresh(business_unit)
        return business_unit
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create business unit: {str(e)}"
        )


