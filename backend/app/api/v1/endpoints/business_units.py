"""Business Unit management endpoints - BU → Client → Job workflow"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_internal_user
from app.models.user import Users
from pydantic import BaseModel
from typing import List
from sqlalchemy import text

router = APIRouter(prefix="/business-units", tags=["business-units"])


class BusinessUnitResponse(BaseModel):
    id: int
    name: str
    region: str = None
    continent: str = None

    class Config:
        from_attributes = True


class ClientResponse(BaseModel):
    id: str
    name: str
    email: str = None
    phone: str = None
    business_unit_id: int

    class Config:
        from_attributes = True


@router.get("", response_model=List[BusinessUnitResponse])
async def get_business_units(
    db: Session = Depends(get_db),
    user: Users = Depends(get_current_internal_user),
):
    """Get all business units from database"""
    try:
        # Query from database
        result = db.execute(text("SELECT id, name, region, continent FROM business_units ORDER BY name"))
        rows = result.fetchall()

        if not rows:
            # Return empty list if no BUs exist
            return []

        return [
            {
                "id": row[0],
                "name": row[1],
                "region": row[2],
                "continent": row[3],
            }
            for row in rows
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch business units: {str(e)}"
        )


@router.post("", response_model=BusinessUnitResponse)
async def create_business_unit(
    name: str,
    region: str = None,
    continent: str = None,
    db: Session = Depends(get_db),
    user: Users = Depends(get_current_internal_user),
):
    """Create a new business unit"""
    try:
        result = db.execute(
            text("""
                INSERT INTO business_units (name, region, continent, created_at)
                VALUES (:name, :region, :continent, NOW())
                RETURNING id, name, region, continent
            """),
            {"name": name, "region": region, "continent": continent}
        )
        db.commit()
        row = result.fetchone()
        return {
            "id": row[0],
            "name": row[1],
            "region": row[2],
            "continent": row[3],
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create business unit: {str(e)}"
        )


@router.get("/{bu_id}/clients", response_model=List[ClientResponse])
async def get_clients_for_bu(
    bu_id: int,
    db: Session = Depends(get_db),
    user: Users = Depends(get_current_internal_user),
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


@router.post("/{bu_id}/clients", response_model=ClientResponse)
async def create_client(
    bu_id: int,
    name: str,
    email: str = None,
    phone: str = None,
    db: Session = Depends(get_db),
    user: Users = Depends(get_current_internal_user),
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
