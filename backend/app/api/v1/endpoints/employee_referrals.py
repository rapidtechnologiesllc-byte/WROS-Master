"""Employee Referral API - referral tracking and the referrer picker on Add Candidate.

Referrals are written by the candidate creation handler (Add Candidate with source
"Employee Referral"), never directly through this API.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.tenant_context import tenant_id_of
from app.models.user import Users
from app.services.employee_referral_service import EmployeeReferralService
from app.services.referral_access_control import ReferralAccessControl, employee_id_for_user

router = APIRouter(prefix="/referrals", tags=["referrals"])

logger = logging.getLogger(__name__)


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
        "total_potential_bonus": sum(r["referral_bonus_amount"] for r in referrals if not r["bonus_paid"]
                                     and r["referral_status"] not in ("REJECTED", "SUPERSEDED")),
        "referrals": referrals,
    }


@router.get("/referrers", dependencies=[Depends(require_resource_permission("candidates", "create"))])
def list_referrers(
    db: Session = Depends(get_db),
    current_user: Users = Depends(get_current_internal_user),
):
    """Employees who can be picked as the referrer when adding a candidate (same tenant,
    not exited). Gated on candidate create: whoever can add a candidate can name who referred them.
    self_employee_id is the caller's own employee record, so "Refer a Candidate" can preselect it."""
    employees = EmployeeReferralService.referable_employees(db, tenant_id_of(current_user))
    own_id = employee_id_for_user(db, current_user)
    return {
        "employees": employees,
        "self_employee_id": own_id if any(e["id"] == own_id for e in employees) else None,
    }
