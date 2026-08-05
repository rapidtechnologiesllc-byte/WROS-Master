"""
Client list + create.

The GET here originally powered filter dropdowns only, on the
(incorrect, corrected 2026-08-05) assumption that a create path already
existed "elsewhere" -- confirmed by grep it did not: no `Client(...)`
row was ever instantiated anywhere in this codebase except one internal
helper in partner_intent_service.py. POST /clients is the first real
create path, via app.services.client_service.create_client() -- see
that function's own docstring for the BU-attribution-locking rule it
enforces (Avinash's 2026-08-05 "client attribution locking" law: a
client's BU is derived from the creating user's own BU, never a
caller-supplied field).

Gated the same way as GET /users/all (get_current_hr_or_admin): any
internal user needs to see real client names to filter by them, this
isn't sensitive data on its own the way markup_rate_pct etc. are.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.models.client import Client
from app.schemas.client import (
    ClientCreateRequest, ClientCreateResponse, ClientDetailResponse, ClientListItem,
    ClientListResponse, ClientUpdateRequest,
)
from app.services.client_service import (
    ClientValidationError, DuplicateClientError, create_client, update_client_details,
)

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=ClientListResponse)
def list_clients(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    query = db.query(Client)
    if active_only:
        query = query.filter(Client.status != "INACTIVE")
    clients = query.order_by(Client.company_name).all()
    return ClientListResponse(
        clients=[ClientListItem(id=c.id, company_name=c.company_name, status=c.status) for c in clients]
    )


@router.post("", response_model=ClientCreateResponse, status_code=201)
def create_client_endpoint(
    body: ClientCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    try:
        client = create_client(
            db,
            company_name=body.company_name,
            created_by_user=current_user,
            client_type=body.client_type,
            industry=body.industry,
            country=body.country,
            billing_currency=body.billing_currency,
        )
    except DuplicateClientError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ClientValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return client


@router.get("/{client_id}", response_model=ClientDetailResponse)
def get_client_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id!r} not found.")
    return client


@router.patch("/{client_id}", response_model=ClientDetailResponse)
def update_client_endpoint(
    client_id: str,
    body: ClientUpdateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id!r} not found.")
    try:
        client = update_client_details(db, client, body.dict(exclude_unset=True))
    except DuplicateClientError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ClientValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return client
