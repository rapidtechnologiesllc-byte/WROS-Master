"""Role-Based Access Control for Employee Referrals."""

from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from app.models.referral import EmployeeReferral, JobReferralSettings, ReferralBonus
from app.models.employee import Employee


class ReferralAccessControl:
    """
    Role-based access to referral data.

    Access Rules:
    - CEO: Sees ALL referrals across ALL business units (org-level)
    - Workforce Manager (Corporate): Sees ALL referrals across ALL business units
    - BU Head/Partner: Sees only their business unit's referrals
    - HR Manager: Sees only their business unit's referrals
    - Finance: Sees ALL referrals (for payment processing)
    - Regular Employee: Sees only their own referrals
    """

    ROLE_HIERARCHY = {
        "SUPER_ADMIN": 5,  # Highest - sees everything
        "CEO": 5,
        "WORKFORCE_MANAGER": 4,  # Corporate level - sees everything
        "CFO": 4,  # Finance lead - sees all bonuses
        "BU_HEAD": 3,  # Business unit head - sees their BU only
        "PARTNER": 3,  # Partner - sees their BU only
        "HR_MANAGER": 2,  # HR - sees their BU only
        "FINANCE": 4,  # Finance team - sees all for payment
        "EMPLOYEE": 1,  # Regular employee - sees own referrals
    }

    @staticmethod
    def can_view_referral(
        user_role: str,
        user_bu: Optional[str],
        referral_bu: Optional[str],
    ) -> bool:
        """
        Determine if user can view a specific referral.

        Args:
            user_role: User's role (CEO, BU_HEAD, HR_MANAGER, etc.)
            user_bu: User's business unit
            referral_bu: Business unit of the referral

        Returns:
            True if user can view, False otherwise
        """

        role_level = ReferralAccessControl.ROLE_HIERARCHY.get(user_role, 0)

        # CEO and Workforce Manager see everything
        if role_level >= 4:
            return True

        # BU Head and HR Manager see only their BU
        if role_level == 3 or role_level == 2:
            return user_bu == referral_bu

        # Regular employees see only own referrals (checked elsewhere)
        return False

    @staticmethod
    def get_referrals_for_user(
        db: Session,
        user_id: str,
        user_role: str,
        user_bu: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get referrals visible to this user based on role and BU.
        """

        role_level = ReferralAccessControl.ROLE_HIERARCHY.get(user_role, 0)

        try:
            if role_level >= 4:  # CEO, Workforce Manager, Finance
                # See ALL referrals
                referrals = db.query(EmployeeReferral).all()

            elif role_level == 3 or role_level == 2:  # BU Head, HR Manager
                # See only their BU's referrals
                # Need to join with employee to get business unit
                referrals = (
                    db.query(EmployeeReferral)
                    .join(Employee, EmployeeReferral.referring_employee_id == Employee.id)
                    .filter(Employee.business_unit == user_bu)
                    .all()
                )

            else:  # Regular Employee
                # See only own referrals
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
        user_role: str,
        user_bu: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get referral bonuses visible to this user.

        Finance sees ALL bonuses for payment processing.
        CEO/Workforce Manager see all bonuses.
        BU Head/HR see only their BU's bonuses.
        Employee sees own bonuses.
        """

        role_level = ReferralAccessControl.ROLE_HIERARCHY.get(user_role, 0)

        try:
            if role_level >= 4:  # CEO, Finance, Workforce Manager
                # See ALL bonuses
                bonuses = db.query(ReferralBonus).all()

            elif role_level == 3 or role_level == 2:  # BU Head, HR Manager
                # See only their BU's bonuses
                bonuses = (
                    db.query(ReferralBonus)
                    .join(Employee, ReferralBonus.referring_employee_id == Employee.id)
                    .filter(Employee.business_unit == user_bu)
                    .all()
                )

            else:  # Regular Employee
                # See only own bonuses
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
        user_role: str,
        user_bu: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get job referral stats visible to this user.

        Finance can see stats for all jobs.
        CEO can see stats for all jobs.
        BU Head/HR can only see stats for jobs in their BU.
        Regular employees cannot see job stats.
        """

        role_level = ReferralAccessControl.ROLE_HIERARCHY.get(user_role, 0)

        # Only manager-level and above can see job stats
        if role_level < 2:
            return None

        # BU Head/HR can only see their BU's jobs
        if role_level == 2 or role_level == 3:
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
        user_role: str,
        user_bu: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get the appropriate referral dashboard view for this user's role.

        CEO Dashboard:
        - Total referrals across all BUs
        - Total bonuses owed/paid
        - Referral stats by BU
        - Top referrers
        - Pending bonuses to approve

        Workforce Manager Dashboard:
        - Same as CEO (corporate view)

        BU Head/Partner Dashboard:
        - Referrals in their BU
        - Stats specific to their BU
        - Top referrers in their BU
        - Pending bonuses in their BU

        HR Manager Dashboard:
        - Referrals in their BU
        - Referral stats for their BU
        - Candidate status updates

        Finance Dashboard:
        - All pending bonuses
        - Bonds ready to pay
        - Payment status tracking
        - Approval workflow

        Employee Dashboard:
        - Own referrals and status
        - Bonuses earned/pending
        - Bonus payout timeline
        """

        role_level = ReferralAccessControl.ROLE_HIERARCHY.get(user_role, 0)

        try:
            if role_level >= 5:  # CEO
                return ReferralAccessControl._get_ceo_dashboard(db)

            elif role_level == 4:  # Workforce Manager or Finance
                if user_role == "FINANCE" or user_role == "CFO":
                    return ReferralAccessControl._get_finance_dashboard(db)
                else:
                    return ReferralAccessControl._get_ceo_dashboard(db)  # Same as CEO

            elif role_level == 3:  # BU Head/Partner
                return ReferralAccessControl._get_bu_dashboard(db, user_bu)

            elif role_level == 2:  # HR Manager
                return ReferralAccessControl._get_hr_dashboard(db, user_bu)

            else:  # Regular Employee
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
