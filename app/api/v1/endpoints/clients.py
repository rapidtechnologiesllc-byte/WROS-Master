"""
Read-only client name list -- powers filter dropdowns (e.g. Jobs
"Client" filter) that previously showed hardcoded fake company names.
No CRUD here; app.models.client.Client already has real create/update
paths used elsewhere (resource_management.py, revenue.py's client
dashboard) -- this just exposes id+company_name for selection UI.

Gated the same way as GET /users/all (get_current_hr_or_admin): any
internal user needs to see real client names to filter by them, this
isn't sensitive data on its own the way markup_rate_pct etc. are.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin
from app.models.client import Client
from app.schemas.client import ClientListItem, ClientListResponse

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=ClientListResponse)
def list_clients(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_hr_or_admin),
):
    clients = db.query(Client).order_by(Client.company_name).all()
    return ClientListResponse(
        clients=[ClientListItem(id=c.id, company_name=c.company_name) for c in clients]
    )
