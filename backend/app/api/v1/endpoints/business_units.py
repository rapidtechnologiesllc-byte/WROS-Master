"""Business Unit management endpoints - BU → Client → Job workflow"""
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


@router.put("/{bu_id}", response_model=BusinessUnitResponse, dependencies=[Depends(require_resource_permission("business-units", "can_edit"))])
async def update_business_unit(
    bu_id: int,
    request: BusinessUnitCreateRequest,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Update a business unit"""
    try:
        business_unit = db.query(BusinessUnit).filter(BusinessUnit.id == bu_id).first()
        if not business_unit:
            raise HTTPException(status_code=404, detail=f"Business unit {bu_id} not found")

        if not request.name.strip():
            raise HTTPException(status_code=400, detail="Business unit name is required")

        if not request.display_name.strip():
            raise HTTPException(status_code=400, detail="Display name is required")

        # Check for duplicate bu_code if changed
        if request.bu_code and request.bu_code != business_unit.bu_code:
            existing = db.query(BusinessUnit).filter(BusinessUnit.bu_code == request.bu_code).first()
            if existing:
                raise HTTPException(status_code=409, detail=f"Business unit code '{request.bu_code}' already exists")

        business_unit.name = request.name
        business_unit.display_name = request.display_name
        business_unit.bu_code = request.bu_code
        business_unit.description = request.description
        business_unit.manager_id = request.manager_id

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
            detail=f"Failed to update business unit: {str(e)}"
        )


@router.delete("/{bu_id}", dependencies=[Depends(require_resource_permission("business-units", "can_delete"))])
async def delete_business_unit(
    bu_id: int,
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user)
):
    """Soft delete a business unit (sets active=False, preserves data relationships)"""
    try:
        business_unit = db.query(BusinessUnit).filter(BusinessUnit.id == bu_id).first()
        if not business_unit:
            raise HTTPException(status_code=404, detail=f"Business unit {bu_id} not found")

        # Soft delete: set active=False instead of removing row
        business_unit.active = False
        db.commit()

        return {"status": "success", "id": bu_id, "message": f"Business unit {bu_id} deleted"}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete business unit: {str(e)}"
        )


@router.get("/{bu_id}/clients", response_model=List[ClientResponse], dependencies=[Depends(require_resource_permission("business-units", "view"))])
async def get_clients_for_bu(
    bu_id: int,
    db: Session = Depends(get_db),
):
    """Get all clients for a business unit"""
    try:
        result = db.execute(
            text("SELECT id, name, email, phone, business_unit_id FROM clients WHERE business_unit_id = :bu_id ORDER BY name"),
            {"bu_id": bu_id}
        )
        rows = result.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "phone": row[3],
                "business_unit_id": row[4],
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch clients: {str(e)}"
        )


@router.post("/{bu_id}/clients", response_model=ClientResponse, dependencies=[Depends(require_resource_permission("business-units", "create"))])
async def create_client(
    bu_id: int,
    name: str,
    email: str = None,
    phone: str = None,
    db: Session = Depends(get_db),
):
    """Create a new client for a business unit"""
    try:
        # Verify BU exists
        bu_check = db.execute(
            text("SELECT id FROM business_units WHERE id = :bu_id"),
            {"bu_id": bu_id}
        ).fetchone()

        if not bu_check:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business unit not found"
            )

        import uuid
        client_id = str(uuid.uuid4())

        result = db.execute(
            text("""
                INSERT INTO clients (id, name, email, phone, business_unit_id, created_at)
                VALUES (:id, :name, :email, :phone, :bu_id, NOW())
                RETURNING id, name, email, phone, business_unit_id
            """),
            {"id": client_id, "name": name, "email": email, "phone": phone, "bu_id": bu_id}
        )
        db.commit()
        row = result.fetchone()
        return {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "phone": row[3],
            "business_unit_id": row[4],
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create client: {str(e)}"
        )
