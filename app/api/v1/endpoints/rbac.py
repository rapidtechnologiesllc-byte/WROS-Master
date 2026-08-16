"""
RBAC (Role-Based Access Control) Endpoints
- Business Unit management
- Role management
- User role assignment
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import logger
from app.core.dependencies import require_permission, get_current_internal_user
from app.models.user import Users
from app.models.business_unit import BusinessUnit

router = APIRouter(prefix="/rbac", tags=["rbac"])


class BusinessUnitCreate(BaseModel):
    """Schema for creating a business unit"""
    name: str
    description: Optional[str] = None
    partner_id: Optional[int] = None
    bu_head_id: Optional[int] = None
    region: Optional[str] = None
    continent: Optional[str] = None
    bu_code: Optional[str] = None


class BusinessUnitUpdate(BaseModel):
    """Schema for updating a business unit"""
    name: Optional[str] = None
    description: Optional[str] = None
    partner_id: Optional[int] = None
    bu_head_id: Optional[int] = None
    region: Optional[str] = None
    continent: Optional[str] = None


class BusinessUnitResponse(BaseModel):
    """Schema for business unit response"""
    id: int
    tenant_id: int
    name: str
    display_name: str
    description: Optional[str] = None
    bu_code: Optional[str] = None
    manager_id: Optional[str] = None
    active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.post(
    "/business-units",
    response_model=BusinessUnitResponse,
    summary="Create a new business unit",
    description="Creates a new business unit for the current tenant",
)
def create_business_unit(
    request: BusinessUnitCreate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> BusinessUnitResponse:
    """Create a new business unit."""
    try:
        # Create business unit
        bu = BusinessUnit(
            tenant_id=current_user.tenant_id,
            name=request.name,
            display_name=request.name,
            description=request.description,
            bu_code=request.bu_code,
            active=True
        )

        db.add(bu)
        db.commit()
        db.refresh(bu)

        logger.info(f"Created business unit {bu.id} for tenant {current_user.tenant_id}")

        return BusinessUnitResponse.from_orm(bu)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating business unit: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create business unit: {str(e)}"
        )


@router.put(
    "/business-units/{bu_id}",
    response_model=BusinessUnitResponse,
    summary="Update a business unit",
    description="Updates an existing business unit",
)
def update_business_unit(
    bu_id: int,
    request: BusinessUnitUpdate,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> BusinessUnitResponse:
    """Update an existing business unit."""
    try:
        # Find business unit
        bu = db.query(BusinessUnit).filter(
            BusinessUnit.id == bu_id,
            BusinessUnit.tenant_id == current_user.tenant_id
        ).first()

        if not bu:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business unit not found"
            )

        # Update fields
        if request.name is not None:
            bu.name = request.name
            bu.display_name = request.name
        if request.description is not None:
            bu.description = request.description

        db.add(bu)
        db.commit()
        db.refresh(bu)

        logger.info(f"Updated business unit {bu.id} for tenant {current_user.tenant_id}")

        return BusinessUnitResponse.from_orm(bu)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating business unit: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update business unit: {str(e)}"
        )


@router.delete(
    "/business-units/{bu_id}",
    summary="Delete a business unit",
    description="Deletes a business unit",
)
def delete_business_unit(
    bu_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Delete a business unit."""
    try:
        # Find business unit
        bu = db.query(BusinessUnit).filter(
            BusinessUnit.id == bu_id,
            BusinessUnit.tenant_id == current_user.tenant_id
        ).first()

        if not bu:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business unit not found"
            )

        db.delete(bu)
        db.commit()

        logger.info(f"Deleted business unit {bu.id} for tenant {current_user.tenant_id}")

        return {"message": "Business unit deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting business unit: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete business unit: {str(e)}"
        )


@router.get(
    "/business-units",
    response_model=List[BusinessUnitResponse],
    summary="List business units",
    description="Lists all business units for the current tenant",
)
def list_business_units(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> List[BusinessUnitResponse]:
    """Get all business units for the current tenant."""
    try:
        bus = db.query(BusinessUnit).filter(
            BusinessUnit.tenant_id == current_user.tenant_id
        ).all()

        return [BusinessUnitResponse.from_orm(bu) for bu in bus]
    except Exception as e:
        logger.error(f"Error listing business units: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list business units: {str(e)}"
        )


@router.get(
    "/business-units/{bu_id}",
    response_model=BusinessUnitResponse,
    summary="Get a specific business unit",
    description="Gets details of a specific business unit",
)
def get_business_unit(
    bu_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
) -> BusinessUnitResponse:
    """Get a specific business unit by ID."""
    try:
        bu = db.query(BusinessUnit).filter(
            BusinessUnit.id == bu_id,
            BusinessUnit.tenant_id == current_user.tenant_id
        ).first()

        if not bu:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business unit not found"
            )

        return BusinessUnitResponse.from_orm(bu)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting business unit: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get business unit: {str(e)}"
        )
