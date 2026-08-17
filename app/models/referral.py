"""Employee Referral Model - Track referrals and bonus payments."""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, ForeignKey
from datetime import datetime
from app.models.base import Base


class EmployeeReferral(Base):
    """Track employee referrals and bonus payments."""

    __tablename__ = "employee_referrals"

    referral_id = Column(String(50), primary_key=True)  # "ref_001"

    # Foreign keys
    job_id = Column(String(50), nullable=False)  # Which job
    referring_employee_id = Column(String(50), nullable=False)  # Who referred
    referred_candidate_id = Column(String(36))  # The candidate they referred (can be null initially)

    # Referral details
    referred_candidate_email = Column(String(255))  # Email of referred person
    referred_candidate_name = Column(String(255))  # Name of referred person
    referral_source = Column(String(50), default="EMPLOYEE_REFERRAL")  # Source = EMPLOYEE_REFERRAL

    # Tracking
    referral_status = Column(String(50), default="PENDING")
    # PENDING -> CANDIDATE_REJECTED -> (end)
    #        -> CANDIDATE_SCREENING -> INTERVIEW_SCHEDULED -> INTERVIEWED -> OFFERED -> ACCEPTED -> HIRED -> BONUS_PAID

    # Bonus tracking
    referral_bonus_amount_usd_cents = Column(Integer)  # Bonus amount if hired
    bonus_paid = Column(Boolean, default=False)
    bonus_paid_date = Column(DateTime)
    bonus_payment_id = Column(String(100))  # Link to finance payment record

    # Notifications
    recruiter_notified = Column(Boolean, default=False)
    recruiter_notified_at = Column(DateTime)
    finance_notified = Column(Boolean, default=False)
    finance_notified_at = Column(DateTime)
    hr_notified = Column(Boolean, default=False)
    hr_notified_at = Column(DateTime)
    employee_notified = Column(Boolean, default=False)
    employee_notified_at = Column(DateTime)

    # Audit trail
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = Column(Text)


class JobReferralSettings(Base):
    """Job-level referral settings."""

    __tablename__ = "job_referral_settings"

    settings_id = Column(String(50), primary_key=True)
    job_id = Column(String(50), nullable=False, unique=True)

    # Referral configuration
    enable_referrals = Column(Boolean, default=True)  # Allow referrals for this job?
    referral_bonus_amount_usd_cents = Column(Integer)  # Standard bonus for this job
    referral_email_template = Column(String(100))  # Email template to use

    # Email tracking
    referral_emails_sent = Column(Integer, default = False)  # How many sent
    referral_emails_opened = Column(Integer, default = False)  # How many opened
    referral_links_clicked = Column(Integer, default = False)  # How many clicked
    total_referrals_received = Column(Integer, default = False)  # Total referrals for job

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReferralBonus(Base):
    """Finance tracking for referral bonuses paid."""

    __tablename__ = "referral_bonuses"

    bonus_id = Column(String(50), primary_key=True)
    referral_id = Column(String(50), nullable=False)  # Link to EmployeeReferral

    # Bonus details
    referring_employee_id = Column(String(50), nullable=False)
    bonus_amount_usd_cents = Column(Integer, nullable=False)

    # Payment tracking
    payment_status = Column(String(50), default="PENDING")  # PENDING, APPROVED, PAID, REJECTED
    invoice_number = Column(String(100))
    payment_date = Column(DateTime)

    # Notifications
    finance_notified_at = Column(DateTime)
    hr_notified_at = Column(DateTime)
    employee_notified_at = Column(DateTime)

    # Audit
    approved_by = Column(String(50))  # User who approved
    approved_at = Column(DateTime)
    paid_via = Column(String(50))  # PAYROLL, ACH, CHECK, etc.

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
