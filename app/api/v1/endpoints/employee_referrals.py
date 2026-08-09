"""Employee Referral API - Job referrals and bonus tracking."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.services.employee_referral_service import EmployeeReferralService
from app.services.referral_access_control import ReferralAccessControl
# from app.core.dependencies import get_current_user_or_none  # TODO: Implement auth

router = APIRouter(prefix="/referrals", tags=["referrals"])


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


@router.post("/setup-job-referrals")
def setup_job_referrals(
    request: CreateJobReferralRequest,
    db: Session = Depends(get_db),
):
    """
    Set up referrals for a job and send emails to all employees.

    **When to call:** After a job is created, if you want to enable employee referrals

    **What it does:**
    1. Creates referral settings for the job (with bonus amount)
    2. Prepares emails to send to all employees
    3. Includes referral link and bonus details in email

    **Required fields:**
    - job_id: Job identifier
    - job_title: Title of the job (e.g., "Senior Guidewire Developer")
    - job_description: Brief description of the role
    - enable_referrals: true/false (default true)
    - referral_bonus_amount_usd_cents: Bonus if hired (default $500)

    **Response includes:**
    - List of emails ready to send with referral links
    - Referral link format: `https://blitzenx.com/referral/add-candidate?job_id=XXX&ref_emp=YYY`

    **Example:**
    ```json
    {
      "job_id": "job_001",
      "job_title": "Senior Guidewire Developer",
      "job_description": "Lead role for Guidewire implementation",
      "enable_referrals": true,
      "referral_bonus_amount_usd_cents": 75000
    }
    ```
    """

    # Create referral settings
    settings_result = EmployeeReferralService.create_job_referral_settings(
        db,
        request.job_id,
        request.enable_referrals,
        request.referral_bonus_amount_usd_cents,
    )

    if settings_result["status"] != "created":
        raise HTTPException(status_code=500, detail=settings_result.get("message"))

    # Prepare referral emails
    email_result = EmployeeReferralService.send_referral_emails_for_job(
        db,
        request.job_id,
        request.job_title,
        request.job_description,
        request.referral_bonus_amount_usd_cents,
    )

    return {
        "status": "setup_complete",
        "job_id": request.job_id,
        "referral_settings": settings_result,
        "emails_ready": email_result,
        "action_required": "Send referral emails to employees",
        "referral_bonus_display": f"${request.referral_bonus_amount_usd_cents / 100:.2f}",
    }


@router.post("/record-referral")
def record_referral(
    request: RecordReferralRequest,
    db: Session = Depends(get_db),
):
    """
    Record an employee referral when they submit a candidate.

    **When to call:** When an employee submits a referral via the referral link

    **What it does:**
    1. Creates a referral record linking employee to candidate to job
    2. Tracks referral bonus amount
    3. Sets referral status to PENDING

    **Required fields:**
    - job_id: Which job the referral is for
    - referred_candidate_email: Email of referred candidate
    - referred_candidate_name: Name of referred candidate

    **Referral statuses:**
    - PENDING: Referral recorded, awaiting screening
    - CANDIDATE_SCREENING: Being reviewed
    - INTERVIEW_SCHEDULED: Interview setup
    - INTERVIEWED: Interview completed
    - OFFERED: Job offer extended
    - ACCEPTED: Candidate accepted offer
    - HIRED: Candidate onboarded
    - BONUS_PAID: Referral bonus paid to employee

    **Example:**
    ```json
    {
      "job_id": "job_001",
      "referred_candidate_email": "john.doe@external.com",
      "referred_candidate_name": "John Doe"
    }
    ```
    """

    # TODO: Implement auth - get current_user from session
    # if not current_user:
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    # Record the referral
    result = EmployeeReferralService.record_referral(
        db,
        request.job_id,
        "temp_employee_id",  # TODO: Use current_user.id when auth is implemented
        request.referred_candidate_email,
        request.referred_candidate_name,
    )

    if result["status"] != "recorded":
        raise HTTPException(status_code=500, detail=result.get("message"))

    return {
        "status": "referral_recorded",
        "referral_id": result["referral_id"],
        "job_id": result["job_id"],
        "candidate": result["candidate"],
        "bonus_potential": result["bonus_potential"],
        "message": f"Thank you for referring {result['candidate']}! If hired, you'll receive ${result['bonus_potential']:.2f}",
    }


@router.put("/update-referral-status/{referral_id}")
def update_referral_status(
    referral_id: str,
    new_status: str = Query(..., description="New status for the referral"),
    db: Session = Depends(get_db),
):
    """
    Update referral status as candidate progresses through pipeline.

    **Call this whenever:**
    - Candidate scheduled for interview
    - Candidate is interviewed
    - Offer is sent
    - Candidate is hired/onboarded

    **Valid statuses:**
    - CANDIDATE_REJECTED: Not qualified
    - CANDIDATE_SCREENING: Being reviewed
    - INTERVIEW_SCHEDULED: Interview scheduled
    - INTERVIEWED: Interview completed
    - OFFERED: Offer sent
    - ACCEPTED: Offer accepted
    - HIRED: Onboarded and working

    **Example:**
    ```json
    PUT /referrals/update-referral-status/ref_001?new_status=HIRED
    ```

    **When HIRED status is set:**
    - Referral bonus record created
    - Finance notified
    - Bonus marked as pending payment
    """

    result = EmployeeReferralService.update_referral_status(db, referral_id, new_status)

    if result["status"] != "updated":
        raise HTTPException(status_code=404, detail=result.get("message"))

    return result


@router.get("/pending-bonuses")
def get_pending_bonuses(
    db: Session = Depends(get_db),
):
    """
    Get all pending referral bonuses (for Finance team).

    **Response includes:**
    - Bonus ID
    - Referring employee ID
    - Bonus amount
    - Candidate name
    - When to review and approve for payment

    **Next step:** Approve and process these bonuses via `/referrals/mark-bonus-paid`
    """

    bonuses = EmployeeReferralService.get_pending_bonuses(db)

    total_amount = sum(b["bonus_amount"] for b in bonuses)

    return {
        "status": "retrieved",
        "total_pending_bonuses": len(bonuses),
        "total_amount": total_amount,
        "bonuses": bonuses,
        "action_required": f"Review and approve {len(bonuses)} pending bonuses totaling ${total_amount:.2f}",
    }


@router.post("/mark-bonus-paid/{bonus_id}")
def mark_bonus_paid(
    bonus_id: str,
    request: MarkBonusPaidRequest,
    db: Session = Depends(get_db),
):
    """
    Mark a referral bonus as paid.

    **When to call:** After finance approves and processes payment

    **What it does:**
    1. Marks bonus as PAID
    2. Records payment date and method
    3. Notifies employee about payment
    4. Updates referral tracking

    **Payment methods:**
    - PAYROLL: Added to next paycheck
    - ACH: Direct deposit
    - CHECK: Mailed check
    - OTHER: Other method

    **Example:**
    ```json
    {
      "bonus_id": "bon_001",
      "paid_via": "PAYROLL"
    }
    ```

    **Triggers notifications to:**
    - Finance (payment recorded)
    - HR (bonus paid)
    - Employee (bonus paid notification)
    """

    result = EmployeeReferralService.mark_bonus_paid(db, bonus_id, paid_via=request.paid_via)

    if result["status"] != "paid":
        raise HTTPException(status_code=404, detail=result.get("message"))

    # Notify stakeholders
    finance_notify = EmployeeReferralService.notify_finance_about_bonus(db, bonus_id)
    employee_notify = EmployeeReferralService.notify_employee_about_bonus(db, bonus_id)

    return {
        "status": "bonus_paid",
        "bonus_id": bonus_id,
        "amount": result["amount"],
        "paid_date": result["paid_date"],
        "paid_via": result["paid_via"],
        "notifications": {
            "finance": finance_notify["status"],
            "employee": employee_notify["status"],
            "message": employee_notify.get("message"),
        },
    }


@router.get("/job-referral-stats/{job_id}")
def get_job_referral_stats(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Get referral statistics for a specific job.

    **Returns:**
    - Total referrals received
    - Referrals currently pending
    - Referrals converted to hire
    - Conversion rate %
    - Total bonuses owed
    - Bonuses already paid

    **Use this to:**
    - Track referral program ROI for each job
    - Identify which jobs drive most referrals
    - Track pending bonus liabilities
    """

    stats = EmployeeReferralService.get_referral_stats_for_job(db, job_id)

    if stats.get("status") == "error":
        raise HTTPException(status_code=404, detail=stats.get("message"))

    return {
        "status": "retrieved",
        "job_id": job_id,
        **stats,
    }


@router.get("/dashboard/referrals")
def get_referral_dashboard(
    db: Session = Depends(get_db),
):
    """
    Get role-based referral dashboard for logged-in user.

    **Returns different views based on user role:**

    **CEO:** Org-wide referral metrics
    - Total referrals across all BUs
    - Total hired from referrals
    - Conversion rate
    - Total bonuses owed and paid
    - Pending bonuses

    **Workforce Manager:** Same as CEO (corporate view)

    **BU Head/Partner:** Their BU's referrals
    - Referrals in their BU
    - BU-specific stats
    - Top referrers in their BU
    - Pending bonuses in their BU

    **HR Manager:** Their BU's referrals
    - Referrals by status (pending, screening, interviewed, offered, hired)
    - Referral pipeline insights

    **Finance:** All pending bonuses
    - Bonuses ready for payment
    - Payment status tracking
    - Pending amount totals

    **Employee:** Personal referrals
    - Their referrals and status
    - Bonuses earned vs pending
    - Bonus payout timeline
    """

    # TODO: Implement auth - get current_user from session
    # if not current_user:
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    # Get user's role and BU from session/database
    # For now, assume role and bu_context are available on current_user
    user_role = "EMPLOYEE"  # TODO: Get from current_user.role
    user_bu = None  # TODO: Get from current_user.business_unit

    dashboard = ReferralAccessControl.get_dashboard_view_for_role(
        db,
        "temp_user_id",  # TODO: Use current_user.id when auth is implemented
        user_role,
        user_bu,
    )

    return {
        "status": "retrieved",
        "user_role": user_role,
        "user_bu": user_bu,
        "dashboard": dashboard,
    }


@router.get("/referrals/all")
def get_all_referrals(
    db: Session = Depends(get_db),
):
    """
    Get all referrals visible to this user (role-based filtering).

    **Visibility rules:**
    - CEO: All referrals
    - Workforce Manager: All referrals
    - BU Head/Partner: Their BU's referrals only
    - HR Manager: Their BU's referrals only
    - Finance: All referrals
    - Employee: Only their own referrals
    """

    # TODO: Implement auth - get current_user from session
    # if not current_user:
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    user_role = "EMPLOYEE"  # TODO: Get from current_user.role
    user_bu = None  # TODO: Get from current_user.business_unit

    referrals = ReferralAccessControl.get_referrals_for_user(
        db,
        "temp_user_id",  # TODO: Use current_user.id when auth is implemented
        user_role,
        user_bu,
    )

    return {
        "status": "retrieved",
        "total_referrals": len(referrals),
        "referrals": referrals,
    }


@router.get("/bonuses/all")
def get_all_bonuses(
    db: Session = Depends(get_db),
):
    """
    Get all bonuses visible to this user (role-based filtering).

    **Visibility rules:**
    - CEO: All bonuses
    - Workforce Manager: All bonuses
    - Finance: All bonuses (for payment processing)
    - BU Head/Partner: Their BU's bonuses only
    - HR Manager: Their BU's bonuses only
    - Employee: Only their own bonuses
    """

    # TODO: Implement auth - get current_user from session
    # if not current_user:
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    user_role = "EMPLOYEE"  # TODO: Get from current_user.role
    user_bu = None  # TODO: Get from current_user.business_unit

    bonuses = ReferralAccessControl.get_bonuses_for_user(
        db,
        "temp_user_id",  # TODO: Use current_user.id when auth is implemented
        user_role,
        user_bu,
    )

    total_amount = sum(b["bonus_amount"] for b in bonuses)

    return {
        "status": "retrieved",
        "total_bonuses": len(bonuses),
        "total_amount": total_amount,
        "bonuses": bonuses,
    }
