"""Which employee referrals a user may see.

Referrals carry no tenant or business unit of their own: both come from the referring
employee. Every view is limited to the caller's tenant. Inside it, by role template only:
- org-level role templates, and finance (revenue edit -- bonuses are paid from there): all;
- people who manage staff (employees or business units edit): referrals made by employees of
  the business units they can see (app.core.data_scope), plus their own;
- everyone else: their own referrals.
"""
import logging
from typing import Any, Dict, List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.data_scope import bu_filter, visible_bu_ids
from app.core.tenant_context import tenant_id_of
from app.models.employee import Employee
from app.models.referral import EmployeeReferral
from app.models.user import Users
from app.services.permission_helper import PermissionHelper

logger = logging.getLogger(__name__)


def employee_id_for_user(db: Session, user: Users):
    """Referrals are keyed by Employee.id; a login maps to its employee via wros_user_id."""
    return db.query(Employee.id).filter(Employee.wros_user_id == user.UserID).scalar()


class ReferralAccessControl:
    @staticmethod
    def get_referrals_for_user(db: Session, user: Users) -> List[Dict[str, Any]]:
        from app.models.user import Jobs

        tenant_id = tenant_id_of(user)
        query = (db.query(EmployeeReferral, Employee, Jobs.jobTitle)
                 .join(Employee, EmployeeReferral.referring_employee_id == Employee.id)
                 .outerjoin(Jobs, Jobs.jobID == EmployeeReferral.job_id)
                 .filter(Employee.tenant_id == tenant_id))
        sees_all = visible_bu_ids(db, user) is None or PermissionHelper.has_any_permission(
            user.UserID, ["revenue.edit"], db, tenant_id)
        if not sees_all:
            own = EmployeeReferral.referring_employee_id == employee_id_for_user(db, user)
            if PermissionHelper.has_any_permission(user.UserID, ["employees.edit", "business-units.edit"], db, tenant_id):
                query = query.filter(or_(own, bu_filter(db, user, Employee.bu_id, unassigned_visible=False)))
            else:
                query = query.filter(own)
        return [
            {
                "referral_id": r.referral_id,
                "job_id": r.job_id,
                "job_title": job_title,
                "referring_employee_id": r.referring_employee_id,
                "referring_employee_name": f"{employee.first_name} {employee.last_name}".strip(),
                "referred_candidate_id": r.referred_candidate_id,
                "referred_candidate_name": r.referred_candidate_name,
                "referred_candidate_email": r.referred_candidate_email,
                "referral_status": r.referral_status,
                "referral_bonus_amount": (r.referral_bonus_amount_usd_cents or 0) / 100,
                "bonus_paid": bool(r.bonus_paid),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r, employee, job_title in query.order_by(EmployeeReferral.created_at.desc()).all()
        ]
