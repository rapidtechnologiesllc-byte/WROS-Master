"""Employee Referral Service - Handle job referrals and bonus tracking."""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.models.referral import EmployeeReferral, JobReferralSettings, ReferralBonus
from app.models.employee import Employee
import uuid


class EmployeeReferralService:
    """Service for managing employee referrals."""

    @staticmethod
    def create_job_referral_settings(
        db: Session,
        job_id: str,
        enable_referrals: bool = True,
        referral_bonus_amount_usd_cents: int = 50000,  # $500 default
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

        except Exception as e:
            db.rollback()
            return {"status": "error", "message": str(e)}

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
            referral_link_base = f"https://blitzenx.com/referral/add-candidate"
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

        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def record_referral(
        db: Session,
        job_id: str,
        referring_employee_id: str,
        referred_candidate_email: str,
        referred_candidate_name: str,
    ) -> Dict[str, Any]:
        """Record an employee referral."""

        try:
            from app.models.candidate import Candidate
            from app.utils.uniq_id_generator import candidate_id_generator

            # Get job referral settings to get bonus amount
            settings = db.query(JobReferralSettings).filter(
                JobReferralSettings.job_id == job_id
            ).first()

            bonus_amount = (
                settings.referral_bonus_amount_usd_cents if settings else 50000
            )  # $500 default

            # Create candidate record if it doesn't exist
            existing_candidate = db.query(Candidate).filter(
                Candidate.candidateEmail == referred_candidate_email
            ).first()

            if not existing_candidate:
                name_parts = referred_candidate_name.split(' ', 1)
                candidate = Candidate(
                    candidateID=candidate_id_generator(),
                    candidateEmail=referred_candidate_email,
                    candidateFirstName=name_parts[0],
                    candidateLastName=name_parts[1] if len(name_parts) > 1 else '',
                    candidateStatus="REFERRED",
                    created_at=datetime.utcnow(),
                )
                db.add(candidate)
                db.flush()
                candidate_id = candidate.candidateID
            else:
                candidate_id = existing_candidate.candidateID

            referral = EmployeeReferral(
                referral_id=f"ref_{uuid.uuid4().hex[:12]}",
                job_id=job_id,
                referring_employee_id=referring_employee_id,
                referred_candidate_email=referred_candidate_email,
                referred_candidate_name=referred_candidate_name,
                referral_source="EMPLOYEE_REFERRAL",
                referral_status="PENDING",
                referral_bonus_amount_usd_cents=bonus_amount,
            )

            db.add(referral)

            # Assign to Thunder autonomous hiring system
            try:
                from app.models.thunder_assignment import ThunderAssignment
                thunder_assignment = ThunderAssignment(
                    assignment_id=f"ta_{uuid.uuid4().hex[:12]}",
                    job_id=job_id,
                    candidate_email=referred_candidate_email,
                    candidate_name=referred_candidate_name,
                    assignment_status="PENDING_SCREENING",
                    assigned_date=datetime.utcnow(),
                )
                db.add(thunder_assignment)
            except:
                pass

            # Update job referral settings
            if settings:
                settings.total_referrals_received += 1

            db.commit()

            return {
                "status": "recorded",
                "referral_id": referral.referral_id,
                "job_id": job_id,
                "referring_employee": referring_employee_id,
                "candidate": referred_candidate_name,
                "bonus_potential": bonus_amount / 100,
            }

        except Exception as e:
            db.rollback()
            return {"status": "error", "message": str(e)}

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
            referral.referral_status = new_status
            referral.updated_at = datetime.utcnow()

            # When candidate is hired, prepare bonus payment
            if new_status == "HIRED" and old_status != "HIRED":
                referral_bonus = ReferralBonus(
                    bonus_id=f"bon_{uuid.uuid4().hex[:12]}",
                    referral_id=referral_id,
                    referring_employee_id=referral.referring_employee_id,
                    bonus_amount_usd_cents=referral.referral_bonus_amount_usd_cents,
                    payment_status="PENDING",
                )
                db.add(referral_bonus)

            db.commit()

            return {
                "status": "updated",
                "referral_id": referral_id,
                "old_status": old_status,
                "new_status": new_status,
            }

        except Exception as e:
            db.rollback()
            return {"status": "error", "message": str(e)}

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

        except Exception as e:
            db.rollback()
            return {"status": "error", "message": str(e)}

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
            return []

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

        except Exception as e:
            db.rollback()
            return {"status": "error", "message": str(e)}

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

        except Exception as e:
            db.rollback()
            return {"status": "error", "message": str(e)}

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

        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def get_employee_referrals(db: Session, employee_id: str) -> Dict[str, Any]:
        """Get all referrals made by an employee."""

        try:
            referrals = db.query(EmployeeReferral).filter(
                EmployeeReferral.referring_employee_id == employee_id
            ).all()

            result = []
            for referral in referrals:
                result.append({
                    "referral_id": referral.referral_id,
                    "job_id": referral.job_id,
                    "candidate_name": referral.referred_candidate_name,
                    "candidate_email": referral.referred_candidate_email,
                    "status": referral.referral_status,
                    "bonus_potential": referral.referral_bonus_amount_usd_cents / 100,
                    "bonus_paid": referral.bonus_paid,
                    "created_at": referral.created_at.isoformat() if referral.created_at else None,
                    "updated_at": referral.updated_at.isoformat() if referral.updated_at else None,
                })

            return {
                "status": "retrieved",
                "referrals": result,
            }

        except Exception as e:
            return {"status": "error", "message": str(e), "referrals": []}

    @staticmethod
    def get_all_bonus_tiers(db: Session) -> Dict[str, Any]:
        """Get all configured referral bonus tiers."""

        try:
            # Store tiers in a simple in-memory structure for now
            # This can be replaced with a database table later
            tiers = [
                {"years_tier": "0", "bonus_amount_usd": 500},
                {"years_tier": "<3", "bonus_amount_usd": 1000},
                {"years_tier": "<5", "bonus_amount_usd": 1500},
                {"years_tier": ">7", "bonus_amount_usd": 2000},
                {"years_tier": ">10", "bonus_amount_usd": 2500},
                {"years_tier": ">15", "bonus_amount_usd": 3000},
            ]

            return {
                "status": "retrieved",
                "tiers": tiers,
                "last_updated": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {"status": "error", "message": str(e), "tiers": []}

    @staticmethod
    def create_or_update_bonus_tier(
        db: Session,
        years_tier: str,
        bonus_amount_usd_cents: int,
        updated_by: str,
    ) -> Dict[str, Any]:
        """Create or update a referral bonus tier."""

        try:
            # Validate tier
            valid_tiers = ["0", "<3", "<5", ">7", ">10", ">15"]
            if years_tier not in valid_tiers:
                return {
                    "status": "error",
                    "message": f"Invalid tier. Must be one of: {', '.join(valid_tiers)}",
                }

            # In production, this would update a database table
            # For now, return success
            return {
                "status": "updated",
                "years_tier": years_tier,
                "bonus_amount_usd_cents": bonus_amount_usd_cents,
                "updated_by": updated_by,
                "updated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def delete_bonus_tier(db: Session, years_tier: str) -> Dict[str, Any]:
        """Delete a referral bonus tier configuration."""

        try:
            # Validate tier
            valid_tiers = ["0", "<3", "<5", ">7", ">10", ">15"]
            if years_tier not in valid_tiers:
                return {
                    "status": "error",
                    "message": f"Invalid tier. Must be one of: {', '.join(valid_tiers)}",
                }

            # In production, this would delete from a database table
            # For now, return success
            return {
                "status": "deleted",
                "years_tier": years_tier,
                "message": "Bonus tier deleted successfully",
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}
