"""
Candidate Status Management API

Endpoints for updating and viewing a candidate's:
  - Account status  : 'Active' | 'Inactive'
  - Pipeline status : 'Applied' | 'Screening' | 'Interview' | 'Pre-Boarding' | 'Onboarded' | 'Rejected'

Routes:
  PUT  /status/{candidate_id}   — update status / pipeline status
  GET  /status/{candidate_id}   — get current status for a candidate
  GET  /status/all              — get status summary for all candidates
"""

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_hr_or_admin, require_resource_permission
from app.models.candidate import Candidate, CandidateStatus
from app.models.user import CandidateAssignment, Jobs, Users
from app.models.checklist import ChecklistTemplate, CandidateChecklist, CandidateChecklistItem
from app.models.candidate_history import CandidateHistory
from app.services.email_service import EmailService
from app.core.logging import logger
from app.schemas.candidate import CandidateStatusUpdateRequest, CandidateStatusResponse, AllCandidateStatusResponse, StatusActionResponse, ManagerApprovalRequest


router = APIRouter(prefix="/status", tags=["candidate-status"])


# ---------------------------------------------------------------------------
# Valid choices (kept as constants so the Swagger docs show the options)
# ---------------------------------------------------------------------------

VALID_STATUSES = {"Active", "Inactive"}
VALID_PIPELINE_STATUSES = {
    "Applied",
    "Screening",
    "Interview",
    "Pre-onboarding-Approval",
    "Pre-Onboarding",
    "OfferApproval",
    "Onboarded",
    "Hired",
    "Rejected",
}



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candidate_display_name(candidate: Candidate) -> str:
    """Return a display-friendly full name for a candidate."""
    parts = [
        candidate.candidateFirstName or "",
        candidate.candidateMiddleName or "",
        candidate.candidateLastName or "",
    ]
    return " ".join(filter(None, parts)).strip() or "N/A"


def _assign_preboarding_checklist(candidate: Candidate, db: Session, performed_by_id: Optional[str] = None) -> None:
    """
    Auto-assign pre-boarding checklist based on candidate experience.
    Interns get 'Intern Document Collection', others get 'Experience Document Collection'.
    """
    experience = str(candidate.candidateExperience or "").strip().lower()
    # Check if candidateExperience is considered intern/fresher
    if experience in {"", "0", "fresher", "intern", "none"}:
        template_name = "Intern Document Collection"
    else:
        template_name = "Experience Document Collection"

    # Query ChecklistTemplate by name
    template = db.query(ChecklistTemplate).filter(ChecklistTemplate.name == template_name).first()
    if not template:
        logger.warning(f"[Approval] ChecklistTemplate '{template_name}' not found. Skipping assignment.")
        return

    # Prevent duplicate assignment
    existing_assignment = (
        db.query(CandidateChecklist)
        .filter(
            CandidateChecklist.candidate_id == candidate.candidateID,
            CandidateChecklist.template_id == template.id,
        )
        .first()
    )
    if existing_assignment:
        logger.info(f"[Approval] Template '{template_name}' already assigned to candidate '{candidate.candidateID}'.")
        return

    # Create candidate checklist
    checklist = CandidateChecklist(
        candidate_id=candidate.candidateID,
        template_id=template.id,
        template_name=template.name,
        assigned_by_user_id=performed_by_id or "system",
        status="active",
    )
    db.add(checklist)
    db.flush()

    now = datetime.now()
    for t_item in template.items:
        due_date = (
            now + timedelta(days=t_item.due_days_offset)
            if t_item.due_days_offset is not None
            else None
        )
        c_item = CandidateChecklistItem(
            checklist_id=checklist.id,
            template_item_id=t_item.id,
            title=t_item.title,
            description=t_item.description,
            item_type=t_item.item_type,
            order_index=t_item.order_index,
            status="pending",
            due_date=due_date,
        )
        db.add(c_item)

    db.flush()

    # Activate the first queue item
    first_queue = (
        db.query(CandidateChecklistItem)
        .filter(
            CandidateChecklistItem.checklist_id == checklist.id,
            CandidateChecklistItem.item_type == "queue",
            CandidateChecklistItem.status == "pending",
        )
        .order_by(CandidateChecklistItem.order_index)
        .first()
    )
    if first_queue:
        first_queue.status = "active"
        first_queue.activated_at = datetime.now()

    # Add History record for checklist auto-assignment
    db.add(CandidateHistory(
        candidateID=candidate.candidateID,
        event_type="Custom",
        note=f"Pre-Onboarding Checklist '{template_name}' auto-assigned based on experience '{candidate.candidateExperience or 'Fresher/Intern'}'.",
        performed_by_id=performed_by_id or "system",
        performed_by_name="System",
        event_at=datetime.utcnow(),
    ))

    db.commit()
    logger.info(f"[Approval] Successfully auto-assigned checklist '{template_name}' to candidate '{candidate.candidateID}'.")


def _send_approval_notifications(candidate: Candidate, cs: CandidateStatus, assignment: Optional[CandidateAssignment], db: Session) -> None:
    """
    Email notification upon Hiring Manager approval:
      1. Candidate: "Congratulations! You have been approved..."
      2. Hiring Team (Recruiter and Hiring Manager):
         - Recruiter (job.recuriterID)
         - Hiring Manager (assignment.hiring_manager_id or job.hiringManagerID)
    """
    candidate_name = _candidate_display_name(candidate)
    
    # ── 1. Find recruiter details ──
    recruiter_email: str | None = None
    recruiter_name = "Recruiter"
    job = None
    if candidate.job_id:
        job = db.query(Jobs).filter(Jobs.jobID == candidate.job_id).first()
        if job and job.recuriterID:
            rec = db.query(Users).filter(Users.UserID == job.recuriterID).first()
            if rec:
                recruiter_email = rec.UserEmail
                recruiter_name = rec.UserName or "Recruiter"

    # ── 2. Find hiring manager details ──
    hiring_manager_email: str | None = None
    hiring_manager_name = "Hiring Manager"
    if assignment and assignment.hiring_manager_id:
        hm = db.query(Users).filter(Users.UserID == assignment.hiring_manager_id).first()
        if hm:
            hiring_manager_email = hm.UserEmail
            hiring_manager_name = hm.UserName or "Hiring Manager"
    elif job and job.hiringManagerID:
        hm = db.query(Users).filter(Users.UserID == job.hiringManagerID).first()
        if hm:
            hiring_manager_email = hm.UserEmail
            hiring_manager_name = hm.UserName or "Hiring Manager"

    # ── 3. Send email to candidate ──
    if candidate.candidateEmail:
        try:
            EmailService.send_notification(
                to_email=candidate.candidateEmail,
                heading="Congratulations! Your Application has been Approved",
                message=(
                    f"Dear <strong>{candidate_name}</strong>,<br><br>"
                    f"We are absolutely thrilled to inform you that your application has been "
                    f"<strong>approved</strong> by the Hiring Manager!<br><br>"
                    f"Your next step is the <strong>Pre-Onboarding</strong> phase. We will be "
                    f"assigning your pre-boarding checklists and document collection shortly.<br><br>"
                    f"Welcome to the team! Our onboarding team will contact you soon with further details.<br><br>"
                    f"Best regards,<br>"
                    f"The Hiring & Onboarding Team"
                )
            )
            logger.info(f"[Approval] Sent approval notification to candidate: {candidate.candidateEmail}")
        except Exception as exc:
            logger.warning(f"[Approval] Could not email candidate: {exc}")

    # ── 4. Send email to hiring manager ──
    if hiring_manager_email:
        try:
            EmailService.send_notification(
                to_email=hiring_manager_email,
                heading=f"Candidate Approved: {candidate_name}",
                message=(
                    f"Dear {hiring_manager_name},<br><br>"
                    f"This is to confirm that you have <strong>approved</strong> candidate "
                    f"<strong>{candidate_name}</strong> (Candidate ID: {candidate.candidateID}).<br><br>"
                    f"The candidate has been moved to <strong>Pre-Onboarding</strong> status, and "
                    f"the system has automatically assigned the corresponding pre-boarding checklist."
                )
            )
            logger.info(f"[Approval] Sent approval notification to hiring manager: {hiring_manager_email}")
        except Exception as exc:
            logger.warning(f"[Approval] Could not email hiring manager: {exc}")

    # ── 5. Send email to recruiter ──
    if recruiter_email:
        try:
            EmailService.send_notification(
                to_email=recruiter_email,
                heading=f"Candidate Approved & Moved to Pre-Onboarding: {candidate_name}",
                message=(
                    f"Dear {recruiter_name},<br><br>"
                    f"Hiring Manager <strong>{hiring_manager_name}</strong> has approved candidate "
                    f"<strong>{candidate_name}</strong> (Candidate ID: {candidate.candidateID}).<br><br>"
                    f"The candidate's status is now updated to <strong>Pre-Onboarding</strong>, and "
                    f"the pre-boarding process has been initiated."
                )
            )
            logger.info(f"[Approval] Sent approval notification to recruiter: {recruiter_email}")
        except Exception as exc:
            logger.warning(f"[Approval] Could not email recruiter: {exc}")

def _build_status_response(candidate: Candidate, cs: Optional[CandidateStatus]) -> CandidateStatusResponse:
    name_parts = [
        candidate.candidateFirstName or "",
        candidate.candidateMiddleName or "",
        candidate.candidateLastName or "",
    ]
    candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"

    return CandidateStatusResponse(
        candidate_id=candidate.candidateID,
        candidate_name=candidate_name,
        candidate_email=candidate.candidateEmail,
        status=cs.status if cs else None,
        pipeline_status=cs.piplineStatus if cs else None,
        updated_at=cs.updatedAt if cs else None,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.put(
    "/{candidate_id}",
    response_model=StatusActionResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Update candidate account status and/or pipeline status",
)
def update_candidate_status(
    candidate_id: str,
    request: CandidateStatusUpdateRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Update the `status` (Active / Inactive) and/or `pipeline_status`
    (Applied → Screening → Interview → Pre-Boarding → Onboarded / Rejected)
    for a candidate.

    At least one of `status` or `pipeline_status` must be provided.
    Both fields are optional in a single call — send only what you want to change.
    """
    # Validate at least one field provided
    if request.status is None and request.pipeline_status is None:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'status' or 'pipeline_status' must be provided.",
        )

    # Validate allowed values
    if request.status is not None and request.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{request.status}'. Allowed: {sorted(VALID_STATUSES)}",
        )
    if request.pipeline_status is not None and request.pipeline_status not in VALID_PIPELINE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pipeline_status '{request.pipeline_status}'. "
                   f"Allowed: {sorted(VALID_PIPELINE_STATUSES)}",
        )

    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    # Get or create the CandidateStatus row
    cs = db.query(CandidateStatus).filter(CandidateStatus.candidateID == candidate_id).first()
    if not cs:
        # Auto-create a status row if it doesn't exist (e.g. legacy candidates)
        cs = CandidateStatus(
            candidateID=candidate_id,
            status="Active",
            piplineStatus="Applied",
        )
        db.add(cs)
        db.flush()

    # Apply updates
    changed_fields = []
    if request.status is not None:
        cs.status = request.status
        changed_fields.append(f"status → {request.status}")

    if request.pipeline_status is not None:
        cs.piplineStatus = request.pipeline_status
        changed_fields.append(f"pipeline_status → {request.pipeline_status}")

    db.commit()
    db.refresh(cs)

    # ── Pool ownership transition: Rejected → Org Pool ────────────────────────
    if request.pipeline_status == "Rejected":
        # pyrefly: ignore [missing-import]
        from app.services.candidate_pool_service import set_org_pool
        set_org_pool(
            candidate_id=candidate_id,
            reason="BU rejected candidate at interview stage \u2014 returned to Org Pool",
            db=db,
            performed_by_id=getattr(user, "UserID", None),
            performed_by_name=getattr(user, "UserName", None),
        )
        db.commit()

    # ── Autonomous job closure: Check if job is filled when candidate is hired ──
    # Trigger ONLY if candidate has been converted to employee (has employee record)
    if request.pipeline_status == "Hired" and candidate.job_id:
        from app.services.autonomous_job_closure_service import check_and_close_job_if_filled
        from app.models.employee import Employee

        # Verify employee record exists (candidate has been onboarded)
        employee = db.query(Employee).filter(
            Employee.candidate_id == candidate_id
        ).first()

        if employee:
            closure_result = check_and_close_job_if_filled(db, candidate.job_id)
            if closure_result:
                logger.info(f"[Autonomous] Job {candidate.job_id} auto-closed after hiring {closure_result['hired']} candidates")
        else:
            logger.info(f"[Autonomous] Candidate {candidate_id} marked hired but no employee record yet - skipping job closure check")

    return StatusActionResponse(
        status="success",
        message=f"Candidate '{candidate_id}' updated: {', '.join(changed_fields)}.",
        data=_build_status_response(candidate, cs),
    )


@router.get(
    "/all",
    response_model=AllCandidateStatusResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get status summary for all candidates",
)
def get_all_candidate_statuses(
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
    status: Optional[str] = None,
    pipeline_status: Optional[str] = None,
):
    """
    Returns account status and pipeline status for every candidate.
    Useful for pipeline dashboards and bulk status views.

    **Optional filters (query params):**
    - `status` — filter by account status (`Active` | `Inactive`)
    - `pipeline_status` — filter by pipeline stage
      (`Applied` | `Screening` | `Interview` | `Pre-Onboarding` | `Onboarded` | `Hired` | `Rejected`)

    Both filters are independent and can be combined.
    """
    # Validate filter values when provided
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{status}'. Allowed: {sorted(VALID_STATUSES)}",
        )
    if pipeline_status is not None and pipeline_status not in VALID_PIPELINE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pipeline_status '{pipeline_status}'. Allowed: {sorted(VALID_PIPELINE_STATUSES)}",
        )

    # HRMS-0109 -- scope to the caller's tenant first, then join
    # CandidateStatus only when a filter is active.
    query = db.query(Candidate)

    if status is not None or pipeline_status is not None:
        query = query.join(
            CandidateStatus,
            CandidateStatus.candidateID == Candidate.candidateID,
        )
        if status is not None:
            query = query.filter(CandidateStatus.status == status)
        if pipeline_status is not None:
            query = query.filter(CandidateStatus.piplineStatus == pipeline_status)

    candidates = query.all()

    results = []
    for candidate in candidates:
        cs = db.query(CandidateStatus).filter(
            CandidateStatus.candidateID == candidate.candidateID
        ).first()
        results.append(_build_status_response(candidate, cs))

    return AllCandidateStatusResponse(total=len(results), candidates=results)


@router.get(
    "/{candidate_id}",
    response_model=CandidateStatusResponse,
    dependencies=[Depends(require_resource_permission("candidates", "view"))],
    summary="Get status for a specific candidate",
)
def get_candidate_status(
    candidate_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_hr_or_admin),
):
    """
    Returns the current account status and pipeline status for a single candidate.
    """
    from app.core.bu_scope import get_candidate_by_id_with_bu_scope
    candidate = get_candidate_by_id_with_bu_scope(db, candidate_id, user)
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    cs = db.query(CandidateStatus).filter(
        CandidateStatus.candidateID == candidate_id
    ).first()

    return _build_status_response(candidate, cs)


# NOTE: The hiring-manager-approval endpoint has been moved to:
#   app/api/v1/endpoints/preonboarding.py
#   POST /preonboarding/{candidate_id}/hiring-manager-approval
