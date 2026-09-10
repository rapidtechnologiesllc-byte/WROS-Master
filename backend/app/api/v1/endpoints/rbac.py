"""RBAC endpoints - wraps business units, departments, and role management"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.business_unit import BusinessUnit
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/rbac", tags=["rbac"])


class BusinessUnitResponse(BaseModel):
    id: int
    name: str
    display_name: Optional[str] = None
    bu_code: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[str] = None
    active: bool = True

    class Config:
        from_attributes = True


class BusinessUnitCreateRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    bu_code: Optional[str] = None
    description: Optional[str] = None
    manager_id: Optional[str] = None


@router.get("/business-units", response_model=List[BusinessUnitResponse])
def get_business_units(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user)
):
    """Get all active business units"""
    try:
        business_units = db.query(BusinessUnit).filter(
            BusinessUnit.active == True
        ).all()
        return business_units
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch business units: {str(e)}"
        )


@router.get("/business-units/{business_unit_id}", response_model=BusinessUnitResponse)
def get_business_unit(
    business_unit_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user)
):
    """Get a specific business unit by ID"""
    try:
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first()
        if not bu:
            raise HTTPException(status_code=404, detail="Business unit not found")
        return bu
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch business unit: {str(e)}"
        )


@router.post("/business-units", response_model=BusinessUnitResponse)
def create_business_unit(
    request: BusinessUnitCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user)
):
    """Create a new business unit"""
    try:
        new_bu = BusinessUnit(
            name=request.name,
            display_name=request.display_name or request.name,
            bu_code=request.bu_code,
            description=request.description,
            manager_id=request.manager_id,
            active=True
        )
        db.add(new_bu)
        db.commit()
        db.refresh(new_bu)
        return new_bu
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create business unit: {str(e)}"
        )


@router.put("/business-units/{business_unit_id}", response_model=BusinessUnitResponse)
def update_business_unit(
    business_unit_id: int,
    request: BusinessUnitCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user)
):
    """Update a business unit"""
    try:
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first()
        if not bu:
            raise HTTPException(status_code=404, detail="Business unit not found")

        bu.name = request.name
        bu.display_name = request.display_name or request.name
        bu.bu_code = request.bu_code
        bu.description = request.description
        bu.manager_id = request.manager_id

        db.commit()
        db.refresh(bu)
        return bu
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update business unit: {str(e)}"
        )


@router.delete("/business-units/{business_unit_id}", status_code=204, response_model=dict, dependencies=[Depends(require_role_template_permission(*Permissions.SYSTEM_MANAGE))])
def delete_business_unit(
    business_unit_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user)
):
    """Delete (deactivate) a business unit"""
    try:
        bu = db.query(BusinessUnit).filter(BusinessUnit.id == business_unit_id).first()
        if not bu:
            raise HTTPException(status_code=404, detail="Business unit not found")

        bu.active = False
        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete business unit: {str(e)}"
        )


@router.get("/business-units/{business_unit_id}/departments", response_model=list)
def get_business_unit_departments(
    business_unit_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_internal_user)
):
    """Get departments for a business unit"""
    try:
        # TODO: Implement departments fetching
        return []
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch departments: {str(e)}"
        )
