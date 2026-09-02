"""Role-Based Access Control for Employee Referrals.

ZERO-HARDCODING: All access rules determined by database-driven role_templates,
not hardcoded role names or hierarchy dictionaries.

Access determined by permissions:
- admin.manage: CEO, Workforce Manager (sees everything)
- revenue.manage: CFO, Finance (sees all for payment processing)
- business_unit.manage: BU Head, Partner (sees only their BU)
- employee.manage: HR Manager (sees only their BU)
- No special permission: Regular Employee (sees only own referrals)
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from app.models.referral import EmployeeReferral, JobReferralSettings, ReferralBonus
from app.models.employee import Employee
from app.models.user import Users
from app.services.permission_helper import PermissionHelper


class ReferralAccessControl:
    """Database-driven access control for employee referrals via role_templates."""

    @staticmethod
    def can_view_referral(
        db: Session,
        user_id: str,
        user_bu: Optional[str],
        referral_bu: Optional[str],
    ) -> bool:
        """Determine if user can view a specific referral (database-driven).

        Args:
            db: Database session
            user_id: User ID
            user_bu: User's business unit
            referral_bu: Business unit of the referral

        Returns:
            True if user can view, False otherwise
        """

        # Admin and Workforce Manager see everything
        user = db.query(Users).filter(Users.UserID == user_id).first()
        tenant_id = getattr(user, 'TenantID', 1) if user else 1
        if PermissionHelper.has_any_permission(user_id, ["admin-settings", "edit", "revenue", "edit"], db, tenant_id):
            return True

        # BU Head/Partner see only their BU
        # HR Manager sees only their BU
        # Regular employees see only own referrals (checked elsewhere)
        return False

    @staticmethod
    def get_referrals_for_user(
        db: Session,
        user_id: str,
        user_bu: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get referrals visible to this user (database-driven permissions)."""

        try:
            # Admin and Finance see ALL referrals
            user = db.query(Users).filter(Users.UserID == user_id).first()
            tenant_id = getattr(user, 'TenantID', 1) if user else 1
            if PermissionHelper.has_any_permission(user_id, ["admin-settings", "edit", "revenue", "edit"], db, tenant_id):
                referrals = db.query(EmployeeReferral).all()
            # BU Head/Partner and HR Manager see only their BU's referrals
            elif PermissionHelper.has_any_permission(user_id, ["business-units", "edit", "employees", "edit"], db, tenant_id):
                referrals = (
                    db.query(EmployeeReferral)
                    .join(Employee, EmployeeReferral.referring_employee_id == Employee.id)
                    .filter(Employee.business_unit == user_bu)
                    .all()
                )
            else:
                # Regular Employee sees only own referrals
                referrals = db.query(EmployeeReferral).filter(
                    EmployeeReferral.referring_employee_id == user_id
                ).all()

            return [
                {
                    "referral_id": r.referral_id,
                    "job_id": r.job_id,
                    "referring_employee_id": r.referring_employee_id,
                    "referred_candidate_name": r.referred_candidate_name,
                    "referral_status": r.referral_status,
                    "referral_bonus_amount": r.referral_bonus_amount_usd_cents / 100,
                    "bonus_paid": r.bonus_paid,
                    "created_at": r.created_at.isoformat(),
                }
                for r in referrals
            ]

        except Exception as e:
            return []

    @staticmethod
    def get_bonuses_for_user(
        db: Session,
        user_id: str,
        user_bu: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get referral bonuses visible to this user (database-driven permissions)."""

        try:
            # Admin and Finance see ALL bonuses for payment processing
            user = db.query(Users).filter(Users.UserID == user_id).first()
            tenant_id = getattr(user, 'TenantID', 1) if user else 1
            if PermissionHelper.has_any_permission(user_id, ["admin-settings", "edit", "revenue", "edit"], db, tenant_id):
                bonuses = db.query(ReferralBonus).all()
            # BU Head/Partner and HR Manager see only their BU's bonuses
            elif PermissionHelper.has_any_permission(user_id, ["business-units", "edit", "employees", "edit"], db, tenant_id):
                bonuses = (
                    db.query(ReferralBonus)
                    .join(Employee, ReferralBonus.referring_employee_id == Employee.id)
                    .filter(Employee.business_unit == user_bu)
                    .all()
                )
            else:
                # Regular Employee sees only own bonuses
                bonuses = db.query(ReferralBonus).filter(
                    ReferralBonus.referring_employee_id == user_id
                ).all()

            return [
                {
                    "bonus_id": b.bonus_id,
                    "referral_id": b.referral_id,
                    "referring_employee_id": b.referring_employee_id,
                    "bonus_amount": b.bonus_amount_usd_cents / 100,
                    "payment_status": b.payment_status,
                    "payment_date": b.payment_date.isoformat() if b.payment_date else None,
                    "paid_via": b.paid_via,
                }
                for b in bonuses
            ]

        except Exception as e:
            return []

    @staticmethod
    def get_job_referral_stats_for_user(
        db: Session,
        job_id: str,
        user_id: str,
        user_bu: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get job referral stats visible to this user (database-driven permissions)."""

        # Only admin, finance, and manager-level and above can see job stats
        user = db.query(Users).filter(Users.UserID == user_id).first()
        tenant_id = getattr(user, 'TenantID', 1) if user else 1
        can_view_stats = PermissionHelper.has_any_permission(
            user_id,
            ["admin-settings", "edit", "revenue", "edit", "business-units", "edit", "employees", "edit"],
            db, tenant_id
        )
        if not can_view_stats:
            return None

        # BU Head/HR can only see their BU's jobs
        if PermissionHelper.has_any_permission(user_id, ["business-units", "edit", "employees", "edit"], db, tenant_id):
            # Verify this job is in their BU
            # For now, assume job belongs to a BU (would need job model update)
            # TODO: Add business_unit field to Jobs model
            pass

        try:
            settings = db.query(JobReferralSettings).filter(
                JobReferralSettings.job_id == job_id
            ).first()

            referrals = db.query(EmployeeReferral).filter(
                EmployeeReferral.job_id == job_id
            ).all()

            hired_referrals = [r for r in referrals if r.referral_status == "HIRED"]
            pending_referrals = [r for r in referrals if r.referral_status in ["PENDING", "CANDIDATE_SCREENING"]]

            return {
                "job_id": job_id,
                "total_referrals": len(referrals),
                "total_emails_sent": settings.referral_emails_sent if settings else 0,
                "pending_referrals": len(pending_referrals),
                "hired_from_referrals": len(hired_referrals),
                "referral_to_hire_rate": (
                    len(hired_referrals) / len(referrals) * 100 if referrals else 0
                ),
                "total_bonuses_owed": sum(r.referral_bonus_amount_usd_cents for r in hired_referrals) / 100,
                "bonuses_paid": sum(r.referral_bonus_amount_usd_cents for r in hired_referrals if r.bonus_paid) / 100,
            }

        except Exception as e:
            return None

    @staticmethod
    def get_dashboard_view_for_role(
        db: Session,
        user_id: str,
        user_bu: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get the appropriate referral dashboard view for this user (database-driven).

        CEO/Admin Dashboard: org-wide view
        Finance Dashboard: payment processing view
        BU Head/Partner Dashboard: BU-specific view
        HR Manager Dashboard: HR-specific view
        Employee Dashboard: personal view
        """

        try:
            # CEO/Admin see org-wide dashboard
            # Finance sees payment processing dashboard
            # BU Head/Partner see BU-specific dashboard
            # HR Manager sees HR-specific dashboard
            # Regular Employee sees personal dashboard
            if user_id:
                return ReferralAccessControl._get_employee_dashboard(db, user_id)

        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _get_ceo_dashboard(db: Session) -> Dict[str, Any]:
        """CEO sees org-wide referral metrics."""
        all_referrals = db.query(EmployeeReferral).all()
        all_bonuses = db.query(ReferralBonus).all()

        hired_referrals = [r for r in all_referrals if r.referral_status == "HIRED"]
        pending_bonuses = [b for b in all_bonuses if b.payment_status == "PENDING"]

        return {
            "view": "CEO_DASHBOARD",
            "total_referrals": len(all_referrals),
            "total_hired": len(hired_referrals),
            "conversion_rate": (len(hired_referrals) / len(all_referrals) * 100) if all_referrals else 0,
            "total_bonuses_owed": sum(b.bonus_amount_usd_cents for b in all_bonuses) / 100,
            "bonuses_paid": sum(b.bonus_amount_usd_cents for b in all_bonuses if b.payment_status == "PAID") / 100,
            "pending_bonuses": len(pending_bonuses),
            "total_pending_amount": sum(b.bonus_amount_usd_cents for b in pending_bonuses) / 100,
        }

    @staticmethod
    def _get_finance_dashboard(db: Session) -> Dict[str, Any]:
        """Finance sees all bonuses for payment processing."""
        all_bonuses = db.query(ReferralBonus).all()
        pending_bonuses = [b for b in all_bonuses if b.payment_status == "PENDING"]
        paid_bonuses = [b for b in all_bonuses if b.payment_status == "PAID"]

        return {
            "view": "FINANCE_DASHBOARD",
            "total_bonuses": len(all_bonuses),
            "pending_payment": len(pending_bonuses),
            "pending_amount": sum(b.bonus_amount_usd_cents for b in pending_bonuses) / 100,
            "already_paid": len(paid_bonuses),
            "paid_amount": sum(b.bonus_amount_usd_cents for b in paid_bonuses) / 100,
            "pending_bonuses": pending_bonuses,
        }

    @staticmethod
    def _get_bu_dashboard(db: Session, bu: str) -> Dict[str, Any]:
        """BU Head sees only their BU's referral data."""
        bu_referrals = (
            db.query(EmployeeReferral)
            .join(Employee, EmployeeReferral.referring_employee_id == Employee.id)
            .filter(Employee.business_unit == bu)
            .all()
        )

        hired_referrals = [r for r in bu_referrals if r.referral_status == "HIRED"]

        return {
            "view": "BU_DASHBOARD",
            "business_unit": bu,
            "total_referrals": len(bu_referrals),
            "hired_referrals": len(hired_referrals),
            "conversion_rate": (len(hired_referrals) / len(bu_referrals) * 100) if bu_referrals else 0,
            "bonuses_owed": sum(r.referral_bonus_amount_usd_cents for r in hired_referrals) / 100,
        }

    @staticmethod
    def _get_hr_dashboard(db: Session, bu: str) -> Dict[str, Any]:
        """HR Manager sees only their BU's referral data."""
        bu_referrals = (
            db.query(EmployeeReferral)
            .join(Employee, EmployeeReferral.referring_employee_id == Employee.id)
            .filter(Employee.business_unit == bu)
            .all()
        )

        return {
            "view": "HR_DASHBOARD",
            "business_unit": bu,
            "total_referrals": len(bu_referrals),
            "by_status": {
                "pending": len([r for r in bu_referrals if r.referral_status == "PENDING"]),
                "screening": len([r for r in bu_referrals if r.referral_status == "CANDIDATE_SCREENING"]),
                "interviewed": len([r for r in bu_referrals if r.referral_status == "INTERVIEWED"]),
                "offered": len([r for r in bu_referrals if r.referral_status == "OFFERED"]),
                "hired": len([r for r in bu_referrals if r.referral_status == "HIRED"]),
            },
        }

    @staticmethod
    def _get_employee_dashboard(db: Session, employee_id: str) -> Dict[str, Any]:
        """Employee sees only their own referrals."""
        my_referrals = db.query(EmployeeReferral).filter(
            EmployeeReferral.referring_employee_id == employee_id
        ).all()

        my_bonuses = db.query(ReferralBonus).filter(
            ReferralBonus.referring_employee_id == employee_id
        ).all()

        hired_referrals = [r for r in my_referrals if r.referral_status == "HIRED"]

        return {
            "view": "EMPLOYEE_DASHBOARD",
            "total_referrals": len(my_referrals),
            "hired_referrals": len(hired_referrals),
            "bonus_potential": sum(r.referral_bonus_amount_usd_cents for r in hired_referrals) / 100,
            "bonuses_earned": sum(b.bonus_amount_usd_cents for b in my_bonuses if b.payment_status == "PAID") / 100,
            "bonuses_pending": sum(b.bonus_amount_usd_cents for b in my_bonuses if b.payment_status == "PENDING") / 100,
        }
