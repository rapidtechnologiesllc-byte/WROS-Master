"""Client onboarding: after a client selects a candidate, until they start on the project.

GET  /client-onboarding                     rows (filter by status)
POST /client-onboarding/{id}/confirm-start  {confirmed_start_date}: the client confirmed the date;
                                            the employee is placed and allocated on that date
                                            (immediately if it is today or earlier)
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.client_onboarding import ClientOnboarding
from app.services import client_onboarding_service as onboarding
from app.services.hiring_pipeline_service import notify

router = APIRouter(prefix="/client-onboarding", tags=["client-onboarding"])


class ConfirmStartRequest(BaseModel):
    confirmed_start_date: date


def _out(row: ClientOnboarding) -> dict:
    return {"id": row.id, "submission_id": row.submission_id, "candidate_id": row.candidate_id,
            "employee_id": row.employee_id, "demand_id": row.demand_id, "client_id": row.client_id,
            "status": row.status, "proposed_start_date": row.proposed_start_date,
            "confirmed_start_date": row.confirmed_start_date, "confirmed_by": row.confirmed_by,
            "allocation_id": row.allocation_id}


@router.get("", dependencies=[Depends(require_resource_permission("resources", "view"))])
def list_client_onboardings(status: Optional[str] = None, db: Session = Depends(get_db),
                            user=Depends(get_current_internal_user)):
    query = db.query(ClientOnboarding)
    if user.tenant_id is not None:
        query = query.filter(ClientOnboarding.tenant_id == user.tenant_id)
    if status:
        query = query.filter(ClientOnboarding.status == status.upper())
    return [_out(r) for r in query.order_by(ClientOnboarding.id.desc()).limit(500).all()]


@router.post("/{onboarding_id}/confirm-start", dependencies=[Depends(require_resource_permission("resources", "edit"))])
def confirm_start(onboarding_id: int, request: ConfirmStartRequest, db: Session = Depends(get_db),
                  user=Depends(get_current_internal_user)):
    row = db.query(ClientOnboarding).filter(ClientOnboarding.id == onboarding_id).with_for_update().first()
    if row is None or (user.tenant_id is not None and row.tenant_id not in (None, user.tenant_id)):
        raise HTTPException(status_code=404, detail=f"Client onboarding {onboarding_id} not found")
    try:
        onboarding.confirm_start(db, row, request.confirmed_start_date, user.UserID)
    except onboarding.ClientOnboardingError as exc:
        db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    db.commit()
    notify(row.candidate_id, "client_start_confirmed", f"{row.id}:{row.confirmed_start_date}")
    if row.confirmed_start_date <= date.today():
        onboarding.run_start_date_job(db)
        db.refresh(row)
    return _out(row)
