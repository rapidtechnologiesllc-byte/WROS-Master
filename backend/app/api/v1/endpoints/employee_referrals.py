import logging
from fastapi import Request
"""Employee Referral API - Job referrals and bonus tracking."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models.user import Users
from app.services.employee_referral_service import EmployeeReferralService
from app.services.referral_access_control import ReferralAccessControl

router = APIRouter(prefix="/referrals", tags=["referrals"])

logger = logging.getLogger(__name__)

class CreateJobReferralRequest(BaseModel):
    """Request to enable referrals for a job."""

    job_id: str
    job_title: str
    job_description: str
    enable_referrals: bool = True
    referral_bonus_amount_usd_cents: int = 50000  # $500 default

class RecordReferralRequest(BaseModel):
    """Request to record an employee referral."""

    job_id: str
    referred_candidate_email: str
    referred_candidate_name: str

class MarkBonusPaidRequest(BaseModel):
    """Request to mark a referral bonus as paid."""

    bonus_id: str
    paid_via: str = "PAYROLL"


@router.get("/referrals/all", dependencies=[Depends(require_resource_permission("my-referrals", "view"))])
def get_all_referrals(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Referrals visible to this user, inside their tenant: everything for org-level role
    templates and finance, their business units' for people who manage staff, else their own
    (app.services.referral_access_control)."""
    referrals = ReferralAccessControl.get_referrals_for_user(db, current_user)

    return {
        "status": "retrieved",
        "total_referrals": len(referrals),
        "referrals": referrals,
    }

