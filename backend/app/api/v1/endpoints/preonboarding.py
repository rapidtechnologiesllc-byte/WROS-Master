"""
Pre-Onboarding API

Endpoints related to the Hiring Manager review and approval workflow,
which gate candidates into the 'Pre-Onboarding' pipeline stage.

Routes:
  GET  /preonboarding/hiring-manager/review            â€” list candidates ready for HM review
  POST /preonboarding/{candidate_id}/hiring-manager-approval â€” approve or reject a candidate
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.core.logging import logger
from app.models.candidate import Candidate, CandidateStatus
from app.models.candidate_history import CandidateHistory
from app.models.user import CandidateAssignment, Jobs, Users
from app.models.checklist import ChecklistTemplate, CandidateChecklist, CandidateChecklistItem
from app.models import (
    Interview, InterviewPanel, InterviewFeedback, PanelMember,
)
from app.services.email_service import EmailService
from app.schemas.candidate import (
    CandidateStatusResponse,
    StatusActionResponse,
    ManagerApprovalRequest,
)
from app.schemas.interview import (
    HMFeedbackDetail,
    HMInterviewRound,
    HMCandidateReviewItem,
    HMCandidateReviewListResponse,
)


router = APIRouter(prefix="/preonboarding", tags=["pre-onboarding"])


# ---------------------------------------------------------------------------
# Internal Helpers (copied from candidate_status.py / interviews.py)
# ---------------------------------------------------------------------------

def _candidate_display_name(candidate: Candidate) -> str:
    """Return a display-friendly full name for a candidate."""
    parts = [
        candidate.candidateFirstName or "",
        candidate.candidateMiddleName or "",
        candidate.candidateLastName or "",
    ]
    return " ".join(filter(None, parts)).strip() or "N/A"


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


def _assign_preboarding_checklist(
    candidate: Candidate,
    db: Session,
    performed_by_id: Optional[str] = None,
) -> None:
    """
    Auto-assign a pre-boarding checklist based on candidate employee type.

    Mapping:
      - "Intern"             â†’ 'Intern Document Collection'
      - "Full Time Employee" â†’ 'Experience Document Collection'
      - (not set / unknown)  â†’ falls back to experience check for backward compatibility

    2026-08-05: a "Guidewire" employee-type option used to exist on the
    Employee Type dropdown (CandidateEditModal.js) -- a bug, per
    Avinash: employee type is Intern/Full Time Employee only, Guidewire
    is a skill/technology, not an employment type. Removed from the
    dropdown; this function never had a real distinct branch for it
    anyway (the stored dropdown value was "Guidewire", one word, but
    this function's old check compared against "guidewire employee",
    two words -- always False, so it silently fell through to the
    backward-compatibility branch below for every legacy row).
    """
    from datetime import timedelta

    employee_type = str(candidate.candidateEmployeeType or "").strip().lower()

    if employee_type == "intern":
        template_name = "Intern Document Collection"
    elif employee_type == "full time employee":
        template_name = "Experience Document Collection"
    else:
        # Backward-compatibility fallback: use experience if employee type is not set
        experience = str(candidate.candidateExperience or "").strip().lower()
        if experience in {"", "0", "fresher", "intern", "none"}:
            template_name = "Intern Document Collection"
        else:
            template_name = "Experience Document Collection"

    template = (
        db.query(ChecklistTemplate)
        .filter(ChecklistTemplate.name == template_name)
        .first()
    )
    if not template:
        logger.warning(
            f"[Approval] ChecklistTemplate '{template_name}' not found. Skipping assignment."
        )
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
        logger.info(
            f"[Approval] Template '{template_name}' already assigned to candidate '{candidate.candidateID}'."
        )
        return

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

    db.add(
        CandidateHistory(
            candidateID=candidate.candidateID,
            event_type="Custom",
            note=(
                f"Pre-Onboarding Checklist '{template_name}' auto-assigned based on "
                f"employee type '{candidate.candidateEmployeeType or 'Not Set (fallback to experience)'}'."
            ),
            performed_by_id=performed_by_id or "system",
            performed_by_name="System",
            event_at=datetime.utcnow(),
        )
    )

    db.commit()
    logger.info(
        f"[Approval] Successfully auto-assigned checklist '{template_name}' "
        f"to candidate '{candidate.candidateID}'."
    )


def _send_approval_notifications(
    candidate: Candidate,
    cs: CandidateStatus,
    assignment: Optional[CandidateAssignment],
    db: Session,
) -> None:
    """
    Email notifications upon Hiring Manager approval:
      1. Candidate  â€” "Congratulations! You have been approvedâ€¦"
      2. Hiring Manager â€” confirmation of their approval action
      3. Recruiter  â€” FYI that the candidate was moved to Pre-Onboarding
    """
    candidate_name = _candidate_display_name(candidate)

    # â”€â”€ 1. Find recruiter details â”€â”€
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

    # â”€â”€ 2. Find hiring manager details â”€â”€
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

    # â”€â”€ 3. Email to candidate â”€â”€
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
                    f"The Hiring &amp; Onboarding Team"
                ),
            )
            logger.info(f"[Approval] Sent approval notification to candidate: {candidate.candidateEmail}")
        except Exception as exc:
            logger.warning(f"[Approval] Could not email candidate: {exc}")

    # â”€â”€ 4. Email to hiring manager â”€â”€
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
                ),
            )
            logger.info(f"[Approval] Sent approval notification to hiring manager: {hiring_manager_email}")
        except Exception as exc:
            logger.warning(f"[Approval] Could not email hiring manager: {exc}")

    # â”€â”€ 5. Email to recruiter â”€â”€
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
                ),
            )
            logger.info(f"[Approval] Sent approval notification to recruiter: {recruiter_email}")
        except Exception as exc:
            logger.warning(f"[Approval] Could not email recruiter: {exc}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/hiring-manager/review",
    response_model=HMCandidateReviewListResponse,

    summary="Hiring Manager: list candidates with â‰¥2 completed interviews (ready for approval/rejection)",
)
def get_hm_candidate_review(
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Returns candidates who have **â‰¥ 2 completed interview rounds** across panels
    that are linked to a job managed by the authenticated Hiring Manager.

    **Mapping logic (source of truth: InterviewPanel.job_id)**

    1. Collect all `job_id`s where `job.hiringManagerID == authenticated_user`.
    2. Query all `InterviewPanel` rows whose `job_id` is in that set.
    3. Group panels by `(candidate_id, job_id)` â€” each group represents one
       candidate's interview journey for a specific job.
    4. For each group, count `Interview` rows with `status == "Completed"`.
       Skip the group if < 2 completed rounds.
    5. Return full feedback from every completed interview in the group.

    Use the ``approval_endpoint`` field to approve/reject via
    ``POST /preonboarding/{candidate_id}/hiring-manager-approval``.
    """
    from collections import defaultdict

    hm_id:   str = user.UserID
    hm_name: str = getattr(user, "UserName", None) or "Hiring Manager"

    # â”€â”€ Step 1: jobs this HM manages â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    managed_jobs = (
        db.query(Jobs)
        .filter(Jobs.hiringManagerID == hm_id)
        .all()
    )
    managed_job_ids = {j.jobID for j in managed_jobs}
    job_map = {j.jobID: j for j in managed_jobs}

    if not managed_job_ids:
        return HMCandidateReviewListResponse(
            hiring_manager_id=hm_id,
            hiring_manager_name=hm_name,
            total_candidates=0,
            candidates=[],
        )

    # â”€â”€ Step 2: all panels for those jobs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    all_panels = (
        db.query(InterviewPanel)
        .filter(InterviewPanel.job_id.in_(managed_job_ids))
        .all()
    )

    if not all_panels:
        return HMCandidateReviewListResponse(
            hiring_manager_id=hm_id,
            hiring_manager_name=hm_name,
            total_candidates=0,
            candidates=[],
        )

    # â”€â”€ Step 3: group panel IDs by (candidate_id, job_id) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # One candidate may have been interviewed multiple times via different
    # panels for the same job (e.g. HR Round, Tech Round, Manager Round).
    # We want to keep those rounds together.
    group_panels: dict[tuple, list[int]] = defaultdict(list)
    for panel in all_panels:
        if panel.candidate_id:
            group_panels[(panel.candidate_id, panel.job_id)].append(panel.id)

    # â”€â”€ Step 4: for each group, collect completed interviews â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    results: list[HMCandidateReviewItem] = []

    for (candidate_id, job_id), panel_ids in group_panels.items():

        # Only interviews linked to THIS group's panels
        completed_ivs = (
            db.query(Interview)
            .filter(
                Interview.panel_id.in_(panel_ids),
                Interview.status == "Completed",
            )
            .order_by(Interview.start_time)
            .all()
        )

        if len(completed_ivs) < 2:
            continue  # not enough rounds done yet

        # Candidate record
        candidate = (
            db.query(Candidate)
            .filter(Candidate.candidateID == candidate_id)
            .first()
        )
        if not candidate:
            continue

        # Pipeline status
        cs = (
            db.query(CandidateStatus)
            .filter(CandidateStatus.candidateID == candidate_id)
            .first()
        )
        pipeline_status = cs.piplineStatus if cs else "Unknown"

        # â”€â”€ Build interview round details with feedback â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        hm_rounds: list[HMInterviewRound] = []

        for iv in completed_ivs:
            panel = (
                db.query(InterviewPanel)
                .filter(InterviewPanel.id == iv.panel_id)
                .first()
            )
            round_name = panel.round_name if panel else "Interview"

            raw_feedbacks = (
                db.query(InterviewFeedback)
                .filter(InterviewFeedback.interview_id == iv.id)
                .all()
            )

            hm_feedbacks: list[HMFeedbackDetail] = []
            recommendations_seen: set[str] = set()

            for fb in raw_feedbacks:
                interviewer = (
                    db.query(Users)
                    .filter(Users.UserID == fb.interviewer_id)
                    .first()
                )
                avg = (
                    fb.technical_score
                    + fb.communication_score
                    + fb.problem_solving_score
                    + fb.culture_fit_score
                ) / 4.0
                hm_feedbacks.append(
                    HMFeedbackDetail(
                        feedback_id=fb.id,
                        interviewer_id=fb.interviewer_id,
                        interviewer_name=(
                            (interviewer.UserName or interviewer.UserEmail)
                            if interviewer else fb.interviewer_id
                        ),
                        technical_score=fb.technical_score,
                        communication_score=fb.communication_score,
                        problem_solving_score=fb.problem_solving_score,
                        culture_fit_score=fb.culture_fit_score,
                        average_score=round(avg, 2),
                        comments=fb.comments,
                        recommendation=fb.recommendation,
                        submitted_at=fb.submitted_at,
                    )
                )
                recommendations_seen.add(fb.recommendation)

            # Overall recommendation for the round
            if not recommendations_seen:
                overall_rec = "No Feedback"
            elif recommendations_seen <= {"Hire", "Must Hire"}:
                overall_rec = "Must Hire" if "Must Hire" in recommendations_seen else "Hire"
            else:
                overall_rec = "Mixed"

            hm_rounds.append(
                HMInterviewRound(
                    interview_id=iv.id,
                    round_name=round_name,
                    start_time=iv.start_time,
                    end_time=iv.end_time,
                    status=iv.status,
                    panel_id=iv.panel_id,
                    feedbacks=hm_feedbacks,
                    overall_recommendation=overall_rec,
                )
            )

        # â”€â”€ Job details â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        job_obj   = job_map.get(job_id)
        job_title = job_obj.jobTitle if job_obj else None

        results.append(
            HMCandidateReviewItem(
                candidate_id=candidate_id,
                candidate_name=_candidate_display_name(candidate),
                candidate_email=candidate.candidateEmail,
                candidate_mobile=candidate.candidateMobile,
                candidate_experience=candidate.candidateExperience,
                job_id=job_id,          # job from panel â€” most accurate
                job_title=job_title,
                pipeline_status=pipeline_status,
                completed_interview_count=len(completed_ivs),
                approval_endpoint=f"/preonboarding/{candidate_id}/hiring-manager-approval",
                interviews=hm_rounds,
            )
        )

    return HMCandidateReviewListResponse(
        hiring_manager_id=hm_id,
        hiring_manager_name=hm_name,
        total_candidates=len(results),
        candidates=results,
    )



@router.post(
    "/{candidate_id}/hiring-manager-approval",
    response_model=StatusActionResponse,
    dependencies=[Depends(require_resource_permission("candidates", "edit"))],
    summary="Hiring Manager Approval for a candidate",
)
def hiring_manager_approval(
    candidate_id: str,
    request: ManagerApprovalRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Process Hiring Manager Approval for a candidate.

    The candidate must be in the 'Pre-onboarding-Approval' pipeline stage.

    Permitted roles:
      - Super User  â€” full bypass
      - BU Head     â€” business-unit authority
      - Hiring Manager â€” the specific HM assigned to this candidate / job

    If Approved -> Candidate moves to 'Pre-Onboarding' (checklist auto-assigned)
    If Rejected -> Candidate moves to 'Rejected' (and goes to Org Pool)
    """
    # â”€â”€ 0. Validate action early (before any DB writes) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if request.action not in ("Approve", "Reject"):
        raise HTTPException(
            status_code=400,
            detail="Invalid action. Must be 'Approve' or 'Reject'.",
        )

    # â”€â”€ 1. Verify candidate exists â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")

    # â”€â”€ 2. Verify candidate is in the 'Pre-onboarding-Approval' stage â”€â”€â”€â”€â”€â”€â”€â”€
    cs = db.query(CandidateStatus).filter(CandidateStatus.candidateID == candidate_id).first()
    if not cs:
        raise HTTPException(status_code=400, detail="Candidate does not have a status record.")

    if cs.piplineStatus != "Pre-onboarding-Approval":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Candidate is currently in '{cs.piplineStatus}' stage, "
                f"not 'Pre-onboarding-Approval'."
            ),
        )

    # â”€â”€ 4. Apply pipeline status change â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    old_status = cs.piplineStatus
    new_status = "Pre-Onboarding" if request.action == "Approve" else "Rejected"
    cs.piplineStatus = new_status

    # Log history entry for the approval/rejection action
    db.add(
        CandidateHistory(
            candidateID=candidate_id,
            event_type="Custom",
            note=(
                f"Candidate {request.action.lower()}d by {getattr(user, 'UserName', user.UserID)} "
                f"({getattr(user, 'UserRole', 'User')}) at Hiring Manager Approval stage."
                + (f" Comments: {request.comments}" if request.comments else "")
            ),
            performed_by_id=user.UserID,
            performed_by_name=getattr(user, "UserName", None) or user.UserID,
            event_at=datetime.utcnow(),
        )
    )

    # Flush the status change and history before side-effects
    db.flush()

    # â”€â”€ 5. Approval side-effects â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if request.action == "Approve":
        # Auto-assign pre-boarding checklist(s) based on candidate experience
        try:
            _assign_preboarding_checklist(
                candidate, db, performed_by_id=user.UserID
            )
        except Exception as exc:
            logger.warning(f"[Approval] Checklist auto-assign failed: {exc}")

        db.commit()
        db.refresh(cs)

        # Email notifications (non-critical â€” errors are logged, not raised)
        #_send_approval_notifications(candidate, cs, assignment, db)

    # â”€â”€ 6. Rejection side-effects â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    elif request.action == "Reject":
        db.commit()
        db.refresh(cs)

        try:
            from app.services.candidate_pool_service import set_org_pool

            reason_msg = (
                "Rejected at Hiring Manager Approval stage â€” returned to Org Pool"
            )
            if request.comments:
                reason_msg += f". Comments: {request.comments}"

            set_org_pool(
                candidate_id=candidate_id,
                reason=reason_msg,
                db=db,
                performed_by_id=user.UserID,
                performed_by_name=getattr(user, "UserName", None),
            )
            db.commit()
        except Exception as exc:
            logger.warning(f"[Approval] Org Pool transfer failed: {exc}")

    return StatusActionResponse(
        status="success",
        message=(
            f"Candidate '{candidate_id}' {request.action.lower()}d. "
            f"Pipeline status changed from '{old_status}' to '{cs.piplineStatus}'."
        ),
        data=_build_status_response(candidate, cs),
    )
