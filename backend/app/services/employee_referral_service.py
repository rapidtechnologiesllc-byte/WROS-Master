import logging
"""Employee Referral Service - Handle job referrals and bonus tracking."""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.core.config import settings as app_settings
from app.models.referral import EmployeeReferral, JobReferralSettings, ReferralBonus
from app.models.employee import Employee
from app.models.candidate import Candidate
import uuid

logger = logging.getLogger(__name__)

# Bonus when the job has no referral settings of its own (REFERRAL_BONUS_DEFAULT_USD_CENTS)
DEFAULT_REFERRAL_BONUS_USD_CENTS = app_settings.REFERRAL_BONUS_DEFAULT_USD_CENTS

# An existing candidate is referable only after this many days without activity
REFERRAL_DORMANT_DAYS = app_settings.REFERRAL_DORMANT_DAYS

# People who have left cannot be named as a referrer
NOT_REFERABLE_STATUSES = ("EXITED",)

# Candidate pipeline status -> referral status shown on My Referrals
PIPELINE_TO_REFERRAL_STATUS = {
    "Applied": "PENDING",
    "Screening": "SCREENING",
    "Interview": "INTERVIEW_SCHEDULED",
    "OfferApproval": "OFFERED",
    "Pre-onboarding-Approval": "OFFERED",
    "Pre-Onboarding": "HIRED",
    "Hired": "HIRED",
    "Onboarded": "HIRED",
    "EMPLOYEE": "HIRED",
    "Rejected": "REJECTED",
}

class EmployeeReferralService:
    """Service for managing employee referrals."""

    @staticmethod
    def create_job_referral_settings(
        db: Session,
        job_id: str,
        enable_referrals: bool = True,
        referral_bonus_amount_usd_cents: int = DEFAULT_REFERRAL_BONUS_USD_CENTS,
    ) -> Dict[str, Any]:
        """Create referral settings when a job is created."""

        try:
            settings = JobReferralSettings(
                settings_id=f"jrs_{uuid.uuid4().hex[:12]}",
                job_id=job_id,
                enable_referrals=enable_referrals,
                referral_bonus_amount_usd_cents=referral_bonus_amount_usd_cents,
                referral_email_template="employee_referral_default",
            )
            db.add(settings)
            db.commit()

            return {
                "status": "created",
                "job_id": job_id,
                "enable_referrals": enable_referrals,
                "referral_bonus": referral_bonus_amount_usd_cents / 100,  # Convert to dollars
            }

        except Exception:

            db.rollback()

            raise

    @staticmethod
    def send_referral_emails_for_job(
        db: Session,
        job_id: str,
        job_title: str,
        job_description: str,
        referral_bonus_amount_usd_cents: int,
    ) -> Dict[str, Any]:
        """Send referral emails to all employees for a job."""

        try:
            # Get all active employees
            employees = db.query(Employee).filter(Employee.status == "ACTIVE").all()

            if not employees:
                return {"status": "no_employees", "emails_sent": 0}

            # Update referral settings
            settings = db.query(JobReferralSettings).filter(
                JobReferralSettings.job_id == job_id
            ).first()

            if settings:
                settings.referral_emails_sent = len(employees)
                db.commit()

            # Prepare email data
            from app.core.config import settings
            referral_link_base = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/referral/add-candidate"
            referral_email_data = []

            for employee in employees:
                referral_token = str(uuid.uuid4())  # Unique token for tracking
                referral_link = f"{referral_link_base}?job_id={job_id}&ref_emp={employee.id}&token={referral_token}"

                email_data = {
                    "to": employee.email,
                    "employee_name": f"{employee.first_name} {employee.last_name}",
                    "job_title": job_title,
                    "job_description": job_description[:500],  # Truncate
                    "referral_bonus_amount": f"${referral_bonus_amount_usd_cents / 100:.2f}",
                    "referral_link": referral_link,
                    "referral_details_link": "https://blitzenx.com/referral-program/details",
                }

                referral_email_data.append(email_data)

            return {
                "status": "ready",
                "job_id": job_id,
                "emails_to_send": len(referral_email_data),
                "email_data": referral_email_data,
                "message": f"Ready to send {len(referral_email_data)} referral emails",
            }

        except Exception:

            db.rollback()

            raise

    @staticmethod
    def referable_employees(db: Session, tenant_id: int) -> List[Dict[str, Any]]:
        """Employees who can be named as the referrer on Add Candidate: everyone in the
        tenant who has not left."""
        rows = (db.query(Employee)
                .filter(Employee.tenant_id == tenant_id, Employee.status.notin_(NOT_REFERABLE_STATUSES))
                .order_by(Employee.first_name, Employee.last_name)
                .all())
        return [{"id": e.id, "name": f"{e.first_name} {e.last_name}".strip(), "email": e.email} for e in rows]

    @staticmethod
    def last_activity_at(db: Session, candidate: Candidate) -> Optional[datetime]:
        """Latest sign of work on the candidate: created, any History entry, any pipeline
        status change. (Naive UTC, as the DB sessions run in UTC.)"""
        from sqlalchemy import func
        from app.models.candidate import CandidateStatus
        from app.models.candidate_history import CandidateHistory

        seen = [
            candidate.candidateCreatedAt,
            candidate.status_changed_at,
            db.query(func.max(CandidateHistory.event_at))
              .filter(CandidateHistory.candidateID == candidate.candidateID).scalar(),
            db.query(func.max(CandidateStatus.updatedAt))
              .filter(CandidateStatus.candidateID == candidate.candidateID).scalar(),
        ]
        seen = [s.replace(tzinfo=None) for s in seen if s is not None]
        return max(seen) if seen else None

    @staticmethod
    def existing_candidate_referral_block(db: Session, candidate: Candidate) -> Optional[str]:
        """Why a candidate already in the system cannot be referred, or None when they can.

        Referable only when dormant: no activity for REFERRAL_DORMANT_DAYS, not inside the
        post-rejection no-contact period, and not already hired through a referral.
        """
        from app.services.candidate_contact_policy import rejection_cooldown_until

        name = " ".join(p for p in (candidate.candidateFirstName, candidate.candidateLastName) if p) or "This candidate"
        until = rejection_cooldown_until(db, candidate.candidateID)
        if until is not None:
            return (f"{name} is already in the system and was rejected recently; they cannot be "
                    f"contacted until {until:%d %b %Y}. No referral was recorded.")
        if candidate.referral_id:
            current = db.query(EmployeeReferral).filter(EmployeeReferral.referral_id == candidate.referral_id).first()
            if current is not None and current.referral_status in ("HIRED", "BONUS_PAID"):
                return f"{name} was already hired through a referral. No referral was recorded."
        last = EmployeeReferralService.last_activity_at(db, candidate)
        if last is not None and datetime.utcnow() - last < timedelta(days=REFERRAL_DORMANT_DAYS):
            return (f"{name} is already in the system and active (last activity {last:%d %b %Y}). "
                    f"A referral counts only for a new candidate or one with no activity for "
                    f"{REFERRAL_DORMANT_DAYS} days. No referral was recorded.")
        return None

    @staticmethod
    def record_candidate_referral(
        db: Session,
        candidate: Candidate,
        referring_employee_id: str,
        job_id: Optional[str] = None,
        recorded_by_user_id: Optional[str] = None,
    ) -> EmployeeReferral:
        """Record that an employee referred this candidate and link the two.

        The one write path for referrals (Add Candidate -> candidate creation handler).
        No commit: the caller commits the candidate and its referral together. The referrer
        must be a current employee of the candidate's tenant (ValueError otherwise: a bad
        id is a caller bug, never retried).
        """
        employee = db.query(Employee).filter(Employee.id == referring_employee_id).first()
        if (employee is None or employee.tenant_id != candidate.tenant_id
                or employee.status in NOT_REFERABLE_STATUSES):
            raise ValueError(f"Referring employee {referring_employee_id} is not a current employee of this tenant")

        settings = (db.query(JobReferralSettings).filter(JobReferralSettings.job_id == job_id).first()
                    if job_id else None)
        if settings is not None and settings.enable_referrals is False:
            raise ValueError(f"Job {job_id} does not accept referrals")
        bonus_cents = (settings.referral_bonus_amount_usd_cents if settings and settings.referral_bonus_amount_usd_cents
                       else DEFAULT_REFERRAL_BONUS_USD_CENTS)

        # A dormant candidate's earlier, unfinished referral is replaced by this one
        if candidate.referral_id:
            earlier = db.query(EmployeeReferral).filter(EmployeeReferral.referral_id == candidate.referral_id).first()
            if earlier is not None and earlier.referral_status not in ("HIRED", "BONUS_PAID"):
                earlier.referral_status = "SUPERSEDED"
                earlier.updated_at = datetime.utcnow()

        referral = EmployeeReferral(
            referral_id=f"ref_{uuid.uuid4().hex[:12]}",
            job_id=job_id,
            referring_employee_id=employee.id,
            referred_candidate_id=candidate.candidateID,
            referred_candidate_email=candidate.candidateEmail,
            referred_candidate_name=" ".join(
                p for p in (candidate.candidateFirstName, candidate.candidateLastName) if p),
            referral_source="EMPLOYEE_REFERRAL",
            referral_status="PENDING",
            referral_bonus_amount_usd_cents=bonus_cents,
        )
        db.add(referral)
        if settings is not None:
            settings.total_referrals_received = (settings.total_referrals_received or 0) + 1
        db.flush()

        candidate.referral_id = referral.referral_id
        candidate.recruitment_source = "EMPLOYEE_REFERRAL"

        from app.services.candidate_activity_service import log_referral_linked
        log_referral_linked(
            db,
            candidate_id=candidate.candidateID,
            referral_id=referral.referral_id,
            referrer_name=f"{employee.first_name} {employee.last_name}".strip(),
            recorded_by_user_id=recorded_by_user_id or candidate.created_by_user_id,
        )
        return referral

    @staticmethod
    def sync_with_pipeline_status(db: Session, candidate: Candidate, pipeline_status: str) -> Optional[str]:
        """Move the candidate's referral to the stage that matches their pipeline status.

        Called by the candidate status-change handler. No commit (the handler commits).
        Returns the new referral status, or None when nothing changed. A paid bonus is final.
        """
        if not candidate.referral_id:
            return None
        new_status = PIPELINE_TO_REFERRAL_STATUS.get(pipeline_status)
        referral = db.query(EmployeeReferral).filter(EmployeeReferral.referral_id == candidate.referral_id).first()
        if new_status is None or referral is None or referral.referral_status in (new_status, "BONUS_PAID"):
            return None
        old_status = referral.referral_status
        EmployeeReferralService._set_status(db, referral, new_status)

        from app.services.candidate_activity_service import log_referral_status_changed
        log_referral_status_changed(
            db,
            candidate_id=candidate.candidateID,
            referral_id=referral.referral_id,
            old_status=old_status,
            new_status=new_status,
        )
        return new_status

    @staticmethod
    def _set_status(db: Session, referral: EmployeeReferral, new_status: str) -> None:
        """Set the status; the first move to HIRED creates the pending bonus for Finance."""
        old_status = referral.referral_status
        referral.referral_status = new_status
        referral.updated_at = datetime.utcnow()
        if new_status == "HIRED" and old_status != "HIRED":
            already = db.query(ReferralBonus).filter(ReferralBonus.referral_id == referral.referral_id).first()
            if already is None:
                db.add(ReferralBonus(
                    bonus_id=f"bon_{uuid.uuid4().hex[:12]}",
                    referral_id=referral.referral_id,
                    referring_employee_id=referral.referring_employee_id,
                    bonus_amount_usd_cents=referral.referral_bonus_amount_usd_cents,
                    payment_status="PENDING",
                ))

    @staticmethod
    def update_referral_status(
        db: Session, referral_id: str, new_status: str
    ) -> Dict[str, Any]:
        """Update referral status as candidate progresses."""

        try:
            referral = db.query(EmployeeReferral).filter(
                EmployeeReferral.referral_id == referral_id
            ).first()

            if not referral:
                return {"status": "error", "message": "Referral not found"}

            old_status = referral.referral_status
            EmployeeReferralService._set_status(db, referral, new_status)
            db.commit()

            return {
                "status": "updated",
                "referral_id": referral_id,
                "old_status": old_status,
                "new_status": new_status,
            }

        except Exception:

            db.rollback()

            raise

    @staticmethod
    def mark_bonus_paid(
        db: Session,
        bonus_id: str,
        payment_date: datetime = None,
        paid_via: str = "PAYROLL",
    ) -> Dict[str, Any]:
        """Mark a referral bonus as paid."""

        try:
            bonus = db.query(ReferralBonus).filter(ReferralBonus.bonus_id == bonus_id).first()

            if not bonus:
                return {"status": "error", "message": "Bonus not found"}

            bonus.payment_status = "PAID"
            bonus.payment_date = payment_date or datetime.utcnow()
            bonus.paid_via = paid_via
            bonus.updated_at = datetime.utcnow()

            # Update referral
            referral = db.query(EmployeeReferral).filter(
                EmployeeReferral.referral_id == bonus.referral_id
            ).first()
            if referral:
                referral.bonus_paid = True
                referral.bonus_paid_date = payment_date or datetime.utcnow()
                referral.bonus_payment_id = bonus_id

            db.commit()

            return {
                "status": "paid",
                "bonus_id": bonus_id,
                "amount": bonus.bonus_amount_usd_cents / 100,
                "paid_date": bonus.payment_date.isoformat(),
                "paid_via": paid_via,
            }

        except Exception:

            db.rollback()

            raise

    @staticmethod
    def get_pending_bonuses(db: Session) -> List[Dict[str, Any]]:
        """Get all pending referral bonuses (for finance review)."""

        try:
            bonuses = db.query(ReferralBonus).filter(
                ReferralBonus.payment_status == "PENDING"
            ).all()

            result = []
            for bonus in bonuses:
                referral = db.query(EmployeeReferral).filter(
                    EmployeeReferral.referral_id == bonus.referral_id
                ).first()

                result.append({
                    "bonus_id": bonus.bonus_id,
                    "referral_id": bonus.referral_id,
                    "referring_employee_id": bonus.referring_employee_id,
                    "bonus_amount": bonus.bonus_amount_usd_cents / 100,
                    "status": bonus.payment_status,
                    "candidate_name": referral.referred_candidate_name if referral else "Unknown",
                    "created_at": bonus.created_at.isoformat(),
                })

            return result

        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
            # CRITICAL FIX: Raise error instead of returning empty list
            raise Exception(f"Failed to get pending bonuses: {str(e)}")

    @staticmethod
    def notify_finance_about_bonus(
        db: Session, bonus_id: str, notification_sent: bool = True
    ) -> Dict[str, Any]:
        """Mark finance as notified about a referral bonus."""

        try:
            bonus = db.query(ReferralBonus).filter(ReferralBonus.bonus_id == bonus_id).first()

            if not bonus:
                return {"status": "error", "message": "Bonus not found"}

            if notification_sent:
                bonus.finance_notified_at = datetime.utcnow()

            db.commit()

            return {
                "status": "notified",
                "bonus_id": bonus_id,
                "finance_notified": notification_sent,
            }

        except Exception:

            db.rollback()

            raise

    @staticmethod
    def notify_employee_about_bonus(
        db: Session, bonus_id: str, notification_sent: bool = True
    ) -> Dict[str, Any]:
        """Notify employee that their referral bonus will be paid."""

        try:
            bonus = db.query(ReferralBonus).filter(ReferralBonus.bonus_id == bonus_id).first()

            if not bonus:
                return {"status": "error", "message": "Bonus not found"}

            # Get employee
            employee = db.query(Employee).filter(
                Employee.id == bonus.referring_employee_id
            ).first()

            if not employee:
                return {"status": "error", "message": "Employee not found"}

            if notification_sent:
                bonus.employee_notified_at = datetime.utcnow()

            # Update referral
            referral = db.query(EmployeeReferral).filter(
                EmployeeReferral.referral_id == bonus.referral_id
            ).first()
            if referral:
                referral.employee_notified = True
                referral.employee_notified_at = datetime.utcnow()

            db.commit()

            return {
                "status": "notified",
                "bonus_id": bonus_id,
                "employee_email": employee.email,
                "bonus_amount": bonus.bonus_amount_usd_cents / 100,
                "message": f"Employee {employee.email} notified about ${bonus.bonus_amount_usd_cents / 100:.2f} referral bonus",
            }

        except Exception:

            db.rollback()

            raise

    @staticmethod
    def get_referral_stats_for_job(db: Session, job_id: str) -> Dict[str, Any]:
        """Get referral statistics for a job."""

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

        except Exception:

            db.rollback()

            raise
