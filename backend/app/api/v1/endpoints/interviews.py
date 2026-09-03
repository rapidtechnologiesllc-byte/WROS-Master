from datetime import datetime, timedelta, timezone
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_internal_user, require_resource_permission
from app.models import (
    Users, Candidate, Interview, InterviewPanel,
    InterviewFeedback, PanelMember,
    CandidateStatus, CandidateAssignment, Jobs,
    CandidateHistory,
    ChecklistTemplate, CandidateChecklist, CandidateChecklistItem, ChecklistTemplateItem,
    InterviewRehireReview,
)
from app.utils.uniq_id_generator import panel_id_generator
from app.services.email_service import EmailService
from app.services.message_queue_service import MessageQueueService
from app.services.interview_sequencing_service import (
    PriorRoundNotPassed,
    enforce_interview_sequencing_gate,
    get_hm_candidate_review_list,
)
from app.services.interview_rehire_guard_service import (
    RehireReviewAlreadyDecided,
    RehireReviewNotFound,
    candidate_has_past_no_hire,
    decide_rehire_review,
    get_pending_rehire_reviews,
    submit_rehire_request,
)
from app.services.interview_feedback_task_service import (
    close_pending_feedback_task,
    sync_pending_feedback_tasks_for_interview,
)
from app.core.scheduler import scheduler
from app.core.logging import logger
from app.schemas.interview import (
    # Panel schemas
    InterviewPanelCreate, InterviewPanelResponse, InterviewPanelWithDetails,
    # Panel member schemas
    PanelMemberCreate, PanelMemberResponse, PanelMemberWithDetails,
    # Interview schemas
    InterviewCreate, InterviewUpdate, InterviewResponse, InterviewDetailedResponse,
    # Feedback schemas
    InterviewFeedbackCreate, InterviewFeedbackUpdate, 
    InterviewFeedbackResponse, InterviewFeedbackWithDetails,
    # Statistics and history
    InterviewStatistics, CandidateInterviewHistory, InterviewerWorkload,
    # My Interviews
    MyInterviewItem, MyInterviewFeedback, MyInterviewsResponse,
    # Common responses
    DeleteResponse, BulkDeleteResponse,
    # Hiring Manager review
    HMFeedbackDetail, HMInterviewRound, HMCandidateReviewItem, HMCandidateReviewListResponse,
    # Rehire guard
    RehireReviewResponse, RehireReviewListResponse, RehireReviewDecideRequest,
)

router = APIRouter(prefix="/interviews", tags=["interviews"])


# ============================================
# Internal Helpers
# ============================================

def _candidate_display_name(candidate: Candidate) -> str:
    """Return a display-friendly full name for a candidate."""
    parts = [
        candidate.candidateFirstName or "",
        candidate.candidateMiddleName or "",
        candidate.candidateLastName or "",
    ]
    return " ".join(filter(None, parts)).strip() or "N/A"


def _check_and_auto_submit_for_hire(interview: Interview, db: Session) -> None:
    """
    After a feedback submission, check whether the candidate qualifies for
    automatic submission to the hiring manager for approval.

    Conditions (ALL must be true):
      1. Candidate's current pipeline status is still 'Interview'.
      2. The candidate has >= 2 completed interviews.

    If all conditions pass, the pipeline status is moved to 'Pre-onboarding-Approval' and
    the hiring manager receives an email notification.
    """
    candidate_id = interview.candidate_id

    # --- Condition 1: must be in 'Interview' stage ---
    cs = (
        db.query(CandidateStatus)
        .filter(CandidateStatus.candidateID == candidate_id)
        .first()
    )
    if not cs or cs.piplineStatus != "Interview":
        return

    # --- Condition 2: >= 2 completed interviews ---
    completed_interviews = (
        db.query(Interview)
        .filter(
            Interview.candidate_id == candidate_id,
            Interview.status == "Completed",
        )
        .all()
    )
    if len(completed_interviews) < 2:
        return

    # --- All conditions met â†' auto-promote to 'Pre-onboarding-Approval' ---
    old_status = cs.piplineStatus
    cs.piplineStatus = "Pre-onboarding-Approval"

    # Log history
    db.add(CandidateHistory(
        candidateID=candidate_id,
        event_type="Custom",
        note=(
            f"Candidate auto-submitted for Hiring Manager approval after "
            f"{len(completed_interviews)} completed interviews."
        ),
        performed_by_id="system",
        performed_by_name="Auto-Hire Engine",
        event_at=datetime.utcnow(),
    ))
    db.commit()

    logger.info(
        f"[AutoHire] Candidate '{candidate_id}' promoted "
        f"'{old_status}' â†' 'Pre-onboarding-Approval' after {len(completed_interviews)} completed interviews."
    )

    # --- Notify the hiring manager ---
    candidate = (
        db.query(Candidate)
        .filter(Candidate.candidateID == candidate_id)
        .first()
    )
    candidate_name = _candidate_display_name(candidate) if candidate else candidate_id

    hiring_manager_email: str | None = None
    hiring_manager_name: str = "Hiring Manager"

    # Priority 1: HM from the job linked to the interview's panel
    # (the panel now stores the job the candidate was interviewed for)
    panel = (
        db.query(InterviewPanel)
        .filter(InterviewPanel.id == interview.panel_id)
        .first()
    )
    if panel and panel.job_id:
        job = db.query(Jobs).filter(Jobs.jobID == panel.job_id).first()
        if job and job.hiringManagerID:
            hm = db.query(Users).filter(Users.UserID == job.hiringManagerID).first()
            if hm:
                hiring_manager_email = hm.UserEmail
                hiring_manager_name = hm.UserName or "Hiring Manager"
                logger.info(
                    f"[AutoHire] HM resolved from panel job '{panel.job_id}': {hiring_manager_email}"
                )

    # Priority 2: CandidateAssignment table
    if not hiring_manager_email:
        assignment = (
            db.query(CandidateAssignment)
            .filter(CandidateAssignment.candidate_id == candidate_id)
            .first()
        )
        if assignment and assignment.hiring_manager_id:
            hm = db.query(Users).filter(Users.UserID == assignment.hiring_manager_id).first()
            if hm:
                hiring_manager_email = hm.UserEmail
                hiring_manager_name = hm.UserName or "Hiring Manager"
                logger.info(
                    f"[AutoHire] HM resolved from CandidateAssignment: {hiring_manager_email}"
                )

    # Priority 3: job linked directly to the candidate record
    if not hiring_manager_email and candidate and candidate.job_id:
        job = db.query(Jobs).filter(Jobs.jobID == candidate.job_id).first()
        if job and job.hiringManagerID:
            hm = db.query(Users).filter(Users.UserID == job.hiringManagerID).first()
            if hm:
                hiring_manager_email = hm.UserEmail
                hiring_manager_name = hm.UserName or "Hiring Manager"
                logger.info(
                    f"[AutoHire] HM resolved from candidate.job_id '{candidate.job_id}': {hiring_manager_email}"
                )

    if hiring_manager_email:
        try:
            EmailService.send_notification(
                to_email=hiring_manager_email,
                heading="Action Required: Candidate Ready for Your Approval",
                message=(
                    f"Dear {hiring_manager_name},<br><br>"
                    f"Candidate <strong>{candidate_name}</strong> has successfully completed "
                    f"{len(completed_interviews)} interview round(s).<br><br>"
                    f"Please log in to the HRMS portal to review and approve or reject this candidate.<br><br>"
                    f"Candidate ID: <strong>{candidate_id}</strong>"
                ),
            )
            logger.info(f"[AutoHire] Approval-request email sent to hiring manager: {hiring_manager_email}")
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[AutoHire] Could not send hiring manager email: {exc}")
    else:
        logger.warning(f"[AutoHire] No hiring manager email found for candidate '{candidate_id}'.")


# ---------------------------------------------------------------------------
# Feedback submitted --" email notification
# ---------------------------------------------------------------------------

def _notify_feedback_submitted(
    interview: Interview,
    feedback: InterviewFeedback,
    submitter: Users,
    db: Session,
) -> None:
    """
    DEFECT-13 CRITICAL: Send INDIVIDUAL, ROLE-SPECIFIC notifications when feedback is submitted.

    Each stakeholder gets a personalized email based on their position in the org hierarchy:
    - Hiring Manager: Gets executive summary, can take action
    - BU Head: Gets strategic overview
    - Panel Members: Get feedback confirmation
    - HR Manager: Gets administrative notification

    Fire-and-forget; failures are logged but never raise.
    """
    try:
        from app.services.interview_feedback_notification_service import (
            InterviewFeedbackNotificationService
        )

        # Trigger the notification service
        InterviewFeedbackNotificationService.notify_feedback_submitted(
            db=db,
            interview_id=interview.id,
            feedback_summary=feedback.recommendation or "Feedback submitted",
        )

        logger.info(
            f"[FeedbackNotify-DEFECT13] Individual role-specific notifications sent "
            f"for interview #{interview.id}"
        )

    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[FeedbackNotify-DEFECT13] Non-critical notification error: {exc}")


# ---------------------------------------------------------------------------
# Feedback reminder scheduler --" fires after interview ends
# ---------------------------------------------------------------------------

def _schedule_feedback_reminders(interview: Interview, db: Session) -> None:
    """
    Schedule two APScheduler one-shot jobs per panel member who has NOT yet
    submitted feedback:

      - Job 1: 1 hour  after interview.end_time  (id: feedback_reminder_{iv}_{member}_1h)
      - Job 2: 24 hours after interview.end_time  (id: feedback_reminder_{iv}_{member}_24h)

    Both jobs re-check at fire-time whether feedback has been submitted and
    skip silently if it has. This prevents duplicate reminders after late submission.

    If end_time is None, falls back to start_time + 1 hour as the baseline.
    """
    IST = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(IST)

    interview_id = interview.id

    # â"€â"€ Baseline: interview end time (or start + 1 h as fallback) â"€â"€â"€â"€â"€â"€â"€â"€â"€
    raw_end = interview.end_time or (
        interview.start_time + timedelta(hours=1) if interview.start_time else None
    )
    if raw_end is None:
        logger.warning(
            f"[FeedbackReminder] Cannot schedule reminders for interview {interview_id}: "
            "no end_time and no start_time."
        )
        return

    end_ist = raw_end.replace(tzinfo=IST) if raw_end.tzinfo is None else raw_end

    # â"€â"€ Collect panel members â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
    panel = db.query(InterviewPanel).filter(
        InterviewPanel.id == interview.panel_id
    ).first()
    if not panel:
        return

    members = db.query(PanelMember).filter(
        PanelMember.panel_id == panel.id
    ).all()
    if not members:
        return

    round_name   = panel.round_name or "Interview"
    candidate = db.query(Candidate).filter(
        Candidate.candidateID == interview.candidate_id
    ).first()
    candidate_name = _candidate_display_name(candidate) if candidate else interview.candidate_id

    reminder_configs = [
        (timedelta(hours=1),   "1 hour",   "1h"),
        (timedelta(hours=24),  "24 hours", "24h"),
    ]

    for member in members:
        member_id = member.interviewer_id

        # Fix 1: skip members who already submitted --" no point reminding them
        already_done = db.query(InterviewFeedback).filter(
            InterviewFeedback.interview_id == interview_id,
            InterviewFeedback.interviewer_id == member_id,
        ).first()
        if already_done:
            logger.info(
                f"[FeedbackReminder] Skipping reminder scheduling for member "
                f"{member_id} on interview {interview_id} -- feedback already submitted."
            )
            continue

        for delta, label, suffix in reminder_configs:
            fire_at = end_ist + delta

            if fire_at <= now:
                logger.info(
                    f"[FeedbackReminder] Skipping {suffix} reminder for member "
                    f"{member_id} on interview {interview_id} -- already past."
                )
                continue

            job_id = f"feedback_reminder_{interview_id}_{member_id}_{suffix}"

            # Capture loop-local values for the async closure
            _fire_at       = fire_at
            _label         = label
            _member_id     = member_id
            _interview_id  = interview_id
            _candidate_name = candidate_name
            _round_name    = round_name

            async def _send_feedback_reminder(
                __interview_id=_interview_id,
                __member_id=_member_id,
                __label=_label,
                __candidate_name=_candidate_name,
                __round_name=_round_name,
            ):
                """Async APScheduler job --" send feedback reminder if not yet submitted."""
                from app.core.database import SessionLocal
                _db = SessionLocal()
                try:
                    # Re-check: has this member already submitted feedback?
                    iv = _db.query(Interview).filter(
                        Interview.id == __interview_id
                    ).first()
                    if not iv:
                        return

                    already_submitted = _db.query(InterviewFeedback).filter(
                        InterviewFeedback.interview_id == __interview_id,
                        InterviewFeedback.interviewer_id == __member_id,
                    ).first()
                    if already_submitted:
                        logger.info(
                            f"[FeedbackReminder] Skipping {__label} reminder for member "
                            f"{__member_id} on interview {__interview_id} -- feedback already submitted."
                        )
                        return

                    interviewer = _db.query(Users).filter(
                        Users.UserID == __member_id
                    ).first()
                    if not interviewer or not interviewer.UserEmail:
                        return

                    interviewer_name = interviewer.UserName or interviewer.UserEmail

                    EmailService.send_event_notification(
                        to_email=interviewer.UserEmail,
                        recipient_name=interviewer_name,
                        event_type="action_required",
                        heading=(
                            f"Reminder: Please Submit Your Interview Feedback "
                            f"-- {__candidate_name} | {__round_name}"
                        ),
                        message=(
                            f"Dear <strong>{interviewer_name}</strong>,<br><br>"
                            f"This is a <strong>{__label}</strong> reminder to submit your feedback "
                            f"for the <strong>{__round_name}</strong> interview with candidate "
                            f"<strong>{__candidate_name}</strong>.<br><br>"
                            f"Your feedback has not yet been submitted. Please log in to the "
                            f"HRMS portal and complete your evaluation at your earliest convenience."
                        ),
                        metadata={
                            "Candidate": __candidate_name,
                            "Round":     __round_name,
                            "Reminder":  f"{__label} after interview ended",
                        },
                    )
                    logger.info(
                        f"[FeedbackReminder] {__label} reminder sent to {interviewer.UserEmail} "
                        f"for interview {__interview_id}."
                    )

                except Exception as exc:
                    logger.error(f"Error: {str(exc)}", exc_info=True)
                    logger.error(
                        f"[FeedbackReminder] Error in reminder job for interview "
                        f"{__interview_id}, member {__member_id}: {exc}"
                    )
                finally:
                    _db.close()

            try:
                scheduler.add_job(
                    _send_feedback_reminder,
                    trigger="date",
                    run_date=_fire_at,
                    id=job_id,
                    replace_existing=True,
                )
                logger.info(
                    f"[FeedbackReminder] Scheduled {suffix} reminder for member "
                    f"{member_id} on interview {interview_id} at {_fire_at.isoformat()} (IST)"
                )
            except Exception as exc:
                logger.error(f"Error: {str(exc)}", exc_info=True)
                logger.warning(
                    f"[FeedbackReminder] Could not schedule {suffix} reminder "
                    f"for member {member_id}: {exc}"
                )


def _cancel_feedback_reminders(interview_id: int, member_id: str) -> None:
    """
    Cancel any pending APScheduler feedback-reminder jobs for a specific
    panel member on a given interview.

    Removes both the 1 h and 24 h reminder jobs if they exist.  Safe to call
    even when the jobs were never scheduled or have already fired.
    """
    for suffix in ("1h", "24h"):
        job_id = f"feedback_reminder_{interview_id}_{member_id}_{suffix}"
        try:
            job = scheduler.get_job(job_id)
            if job:
                scheduler.remove_job(job_id)
                logger.info(
                    f"[FeedbackReminder] Cancelled {suffix} reminder for member "
                    f"{member_id} on interview {interview_id} (feedback submitted)."
                )
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(
                f"[FeedbackReminder] Could not cancel {suffix} reminder "
                f"for member {member_id} on interview {interview_id}: {exc}"
            )


def _cancel_all_feedback_reminders(interview_id: int, db: Session) -> None:
    """
    Cancel ALL pending feedback-reminder jobs (both 1 h and 24 h) for every
    panel member on the given interview.  Used when an interview is cancelled,
    completed, or deleted so no stale reminder emails are sent.
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        return
    members = db.query(PanelMember).filter(
        PanelMember.panel_id == interview.panel_id
    ).all()
    for member in members:
        _cancel_feedback_reminders(interview_id, member.interviewer_id)


def _cancel_interview_reminders(interview_id: int) -> None:
    """
    Cancel the pre-interview reminder jobs (1 h and 15 min before start_time).
    Used when an interview is deleted or cancelled.
    """
    for suffix in ("1h", "15m"):
        job_id = f"interview_reminder_{interview_id}_{suffix}"
        try:
            job = scheduler.get_job(job_id)
            if job:
                scheduler.remove_job(job_id)
                logger.info(
                    f"[InterviewReminder] Cancelled {suffix} pre-interview reminder "
                    f"for interview {interview_id}."
                )
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(
                f"[InterviewReminder] Could not cancel {suffix} reminder "
                f"for interview {interview_id}: {exc}"
            )


def _schedule_interview_reminder(interview: Interview, db: Session) -> None:
    """
    Register (or replace) one-shot APScheduler jobs for the interview reminder.

    Two reminders are scheduled:
      - 1 hour  before start_time  (job id: interview_reminder_{id}_1h)
      - 15 mins before start_time  (job id: interview_reminder_{id}_15m)

    FIX: The DB stores start_time as a *naive* local time (IST, UTC+5:30).
    APScheduler is configured with timezone="UTC", so a naive datetime passed
    as run_date is interpreted as UTC --" causing reminders to fire 5.5 h late.
    We attach the IST offset to make the datetime timezone-aware, which
    APScheduler then correctly converts to its UTC timeline.

    Safe to call on both create and update --" replaces any existing jobs so the
    reminder always matches the current start_time.
    """
    IST = timezone(timedelta(hours=5, minutes=30))  # UTC+05:30

    # Treat the naive DB timestamp as IST, then make it timezone-aware
    if interview.start_time.tzinfo is None:
        start_ist = interview.start_time.replace(tzinfo=IST)
    else:
        start_ist = interview.start_time

    # Gate check using local time (also interpreted as IST on this server)
    now_local = datetime.now(IST)

    # Schedule points: 1 hour and 15 minutes before the interview
    reminder_configs = [
        (timedelta(hours=1),  "1 hour",    f"interview_reminder_{interview.id}_1h"),
        (timedelta(minutes=15), "15 minutes", f"interview_reminder_{interview.id}_15m"),
    ]

    interview_id   = interview.id

    for delta, label, job_id in reminder_configs:
        fire_at = start_ist - delta

        if fire_at <= now_local:
            logger.info(
                f"[InterviewReminder] Skipping '{label}' reminder for interview {interview_id} "
                f"-- fire time {fire_at.isoformat()} is already past."
            )
            continue

        # Capture loop variables for the closure
        _fire_at   = fire_at
        _label     = label
        _job_id    = job_id

        async def _send_reminder(
            _interview_id=interview_id,
            _reminder_label=_label,
        ):
            """Async job executed by APScheduler."""
            from app.core.database import SessionLocal
            _db = SessionLocal()
            try:
                iv = _db.query(Interview).filter(Interview.id == _interview_id).first()
                if not iv:
                    logger.warning(
                        f"[InterviewReminder] Interview {_interview_id} not found at reminder time."
                    )
                    return

                cand  = _db.query(Candidate).filter(Candidate.candidateID == iv.candidate_id).first()
                panel = _db.query(InterviewPanel).filter(InterviewPanel.id == iv.panel_id).first()
                round_name = panel.round_name if panel else "Interview"
                start_str  = iv.start_time.strftime("%d %b %Y, %I:%M %p") if iv.start_time else "N/A"
                end_str    = iv.end_time.strftime("%d %b %Y, %I:%M %p")   if iv.end_time   else "N/A"

                # â"€â"€ Email to candidate â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
                if cand and cand.candidateEmail:
                    cand_name = _candidate_display_name(cand)
                    try:
                        EmailService.send_notification(
                            to_email=cand.candidateEmail,
                            heading=f"Reminder: Your {round_name} Interview is in {_reminder_label}",
                            message=(
                                f"Dear <strong>{cand_name}</strong>,<br><br>"
                                f"This is a reminder that your <strong>{round_name}</strong> interview "
                                f"is scheduled to begin in <strong>{_reminder_label}</strong>.<br><br>"
                                f"<strong>Start:</strong> {start_str}<br>"
                                f"ðŸ• <strong>End:</strong>   {end_str}<br>"
                                + (f"<strong>Meeting Link:</strong> "
                                   f"<a href='{iv.meeting_link}'>{iv.meeting_link}</a><br>"
                                   if iv.meeting_link else "")
                                + "<br>Please ensure you are ready and join on time. Best of luck!"
                            ),
                        )
                        logger.info(
                            f"[InterviewReminder] [{_reminder_label}] Reminder sent to candidate "
                            f"{cand.candidateEmail}"
                        )
                    except Exception as exc:
                        logger.error(f"Error: {str(exc)}", exc_info=True)
                        logger.warning(f"[InterviewReminder] Could not email candidate: {exc}")

                # â"€â"€ Emails to panel members â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€â"€
                if panel:
                    members = _db.query(PanelMember).filter(PanelMember.panel_id == panel.id).all()
                    for member in members:
                        interviewer = _db.query(Users).filter(
                            Users.UserID == member.interviewer_id
                        ).first()
                        if interviewer and interviewer.UserEmail:
                            cand_name = _candidate_display_name(cand) if cand else iv.candidate_id
                            try:
                                EmailService.send_notification(
                                    to_email=interviewer.UserEmail,
                                    heading=(
                                        f"Reminder: Interview in {_reminder_label} "
                                        f"-- {round_name}"
                                    ),
                                    message=(
                                        f"Dear <strong>{interviewer.UserName or 'Interviewer'}</strong>,<br><br>"
                                        f"This is a reminder that the <strong>{round_name}</strong> interview "
                                        f"for candidate <strong>{cand_name}</strong> begins in "
                                        f"<strong>{_reminder_label}</strong>.<br><br>"
                                        f"<strong>Start:</strong> {start_str}<br>"
                                        f"ðŸ• <strong>End:</strong>   {end_str}<br>"
                                        + (f"<strong>Meeting Link:</strong> "
                                           f"<a href='{iv.meeting_link}'>{iv.meeting_link}</a><br>"
                                           if iv.meeting_link else "")
                                    ),
                                )
                                logger.info(
                                    f"[InterviewReminder] [{_reminder_label}] Reminder sent to "
                                    f"panel member {interviewer.UserEmail}"
                                )
                            except Exception as exc:
                                logger.error(f"Error: {str(exc)}", exc_info=True)
                                logger.warning(
                                    f"[InterviewReminder] Could not email panel member "
                                    f"{interviewer.UserID}: {exc}"
                                )
            except Exception as exc:
                logger.error(f"Error: {str(exc)}", exc_info=True)
                logger.error(f"[InterviewReminder] Unexpected error in reminder job: {exc}")
            finally:
                _db.close()

        try:
            scheduler.add_job(
                _send_reminder,
                trigger="date",
                run_date=_fire_at,          # timezone-aware IST â†' scheduler converts to UTC
                id=_job_id,
                replace_existing=True,
            )
            logger.info(
                f"[InterviewReminder] Scheduled [{_label}] reminder for interview "
                f"{interview_id} at {_fire_at.isoformat()} (IST)"
            )
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(
                f"[InterviewReminder] Could not schedule [{_label}] reminder "
                f"for interview {interview_id}: {exc}"
            )


def _resolve_hiring_manager_id_for_interview(db: Session, interview: Interview) -> str | None:
    """Backlog item, 2026-08-05: same 3-priority HM resolution
    _check_and_auto_submit_for_hire() already uses, kept as its own
    standalone helper (not a refactor of that already-tested function)
    so this new call site can't regress it. Returns a Users.UserID or
    None -- callers must handle "no HM resolvable" without raising."""
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
    if panel and panel.job_id:
        job = db.query(Jobs).filter(Jobs.jobID == panel.job_id).first()
        if job and job.hiringManagerID:
            return job.hiringManagerID

    assignment = db.query(CandidateAssignment).filter(CandidateAssignment.candidate_id == interview.candidate_id).first()
    if assignment and assignment.hiring_manager_id:
        return assignment.hiring_manager_id

    candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
    if candidate and candidate.job_id:
        job = db.query(Jobs).filter(Jobs.jobID == candidate.job_id).first()
        if job and job.hiringManagerID:
            return job.hiringManagerID

    return None


def _create_hm_review_task(db: Session, interview: Interview) -> None:
    """Backlog item, 2026-08-05 (wros_hm_candidate_review_task_link_backlog):
    a real Task ("Review interview feedback for [Candidate]") once all
    interviewers for a candidate's current round have submitted --
    Interview.status flips to "Completed" is the real, already-shipped
    signal for that (see completeInterviewIfAllPanelDone() on the
    frontend, which only PUTs status=Completed once every panel member
    is done). Deep-links to HmCandidateReviewScreen via the Task
    description rather than a dedicated Task field -- no generic
    "related entity" column exists on Task for a non-document link.
    Fire-and-forget: a Task-creation bug must never break marking an
    interview Completed, which has already committed by the time this
    runs."""
    try:
        candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
        candidate_name = _candidate_display_name(candidate) if candidate else interview.candidate_id
        hm_user_id = _resolve_hiring_manager_id_for_interview(db, interview)

        from app.services.task_service import create_task
        task = create_task(
            db,
            title=f"Review interview feedback: {candidate_name}",
            description=(
                f"All panel members have submitted feedback for {candidate_name}'s interview round. "
                f"Review it on the Hiring Manager Candidate Review screen (/hiring-manager-review)."
            ),
            priority="MEDIUM",
            assigned_to_user_id=hm_user_id,
            visibility_scope="ORG_WIDE" if hm_user_id is None else "ASSIGNEE_MANAGER_DEPARTMENT",
            task_type="GENERAL",
            category="INTERVIEW_REVIEW",
        )
        # Backlog item, 2026-08-05 (Task feedback-pending vs HM-decision-
        # pending split): link candidate_id/interview_id so this task is
        # real queryable-per-round, distinct from any pending-feedback
        # Task (category=INTERVIEW_FEEDBACK) on the same interview.
        task.candidate_id = interview.candidate_id
        task.interview_id = interview.id
        db.add(task)
        db.commit()
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[HMReviewTask] Failed to create review task for interview {interview.id}: {exc}")


# ============================================
# NOTE: Hiring Manager review endpoint moved
# ============================================
# GET /hiring-manager/review has been moved to:
#   app/api/v1/endpoints/preonboarding.py
#   GET /preonboarding/hiring-manager/review


# ============================================
# Interview Panel Endpoints
# ============================================

@router.post(
    "/panels/create",
    dependencies=[Depends(get_current_user)],
    response_model=InterviewPanelResponse,
    status_code=201,
)
def create_interview_panel(
    request: InterviewPanelCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Create a new interview panel for a candidate.

    Args:
        request: InterviewPanelCreate with candidate_id, round_name, and optional job_id
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        InterviewPanelResponse with panel details including job info

    Raises:
        HTTPException: If candidate or job not found
    """
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )

    # Validate job if provided
    job = None
    if request.job_id:
        job = db.query(Jobs).filter(Jobs.jobID == request.job_id).first()
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job with ID {request.job_id} not found"
            )

    # R-05: this candidate's next round cannot be created until their
    # most recent prior round has actually passed. First round is
    # always allowed (nothing to sequence against yet).
    try:
        enforce_interview_sequencing_gate(db, request.candidate_id)
    except PriorRoundNotPassed as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Rehire guard: a candidate with a past no-hire (Reject) outcome on
    # any prior round/job needs a written justification, reviewed by AI
    # and escalated to the hiring manager when not clearly justified,
    # before a new round can be scheduled. Fail-closed -- the panel is
    # never created in the same request unless AI actually clears it.
    rehire_review_id = None
    rehire_cleared_by = None
    if candidate_has_past_no_hire(db, request.candidate_id):
        if not request.rehire_justification or not request.rehire_justification.strip():
            raise HTTPException(
                status_code=400,
                detail=(
                    "This candidate has a past no-hire outcome on record. A written "
                    "justification is required to schedule a new interview round."
                ),
            )
        review = submit_rehire_request(
            db,
            request.candidate_id,
            _candidate_display_name(candidate),
            request.round_name,
            request.job_id,
            user.UserID,
            request.rehire_justification,
        )
        if review.status != "AI_CLEARED":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "rehire_review_pending",
                    "review_id": review.id,
                    "msg": (
                        "This candidate has a past no-hire outcome. The justification "
                        "has been sent to the hiring manager for approval before this "
                        "round can be scheduled."
                    ),
                    "ai_reasoning": review.ai_reasoning,
                },
            )
        rehire_review_id = review.id
        rehire_cleared_by = "AI"

    # Create panel
    panel = InterviewPanel(
        candidate_id=request.candidate_id,
        round_name=request.round_name,
        job_id=request.job_id,
    )

    db.add(panel)
    db.commit()
    db.refresh(panel)

    return InterviewPanelResponse(
        id=panel.id,
        candidate_id=panel.candidate_id,
        round_name=panel.round_name,
        job_id=panel.job_id,
        job_title=job.jobTitle if job else None,
        created_at=panel.created_at,
        rehire_review_id=rehire_review_id,
        rehire_cleared_by=rehire_cleared_by,
    )


@router.get(
    "/panels/{panel_id}",
    response_model=InterviewPanelWithDetails,
    dependencies=[Depends(require_resource_permission("interviews", "view"))],
)
def get_interview_panel(
    panel_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get details of a specific interview panel.
    
    Args:
        panel_id: ID of the panel
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewPanelWithDetails including member and interview counts
        
    Raises:
        HTTPException: If panel not found
    """
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == panel_id).first()
    if not panel:
        raise HTTPException(
            status_code=404,
            detail=f"Interview panel with ID {panel_id} not found"
        )

    # Get candidate details
    candidate = db.query(Candidate).filter(Candidate.candidateID == panel.candidate_id).first()
    candidate_name = "N/A"
    if candidate:
        name_parts = [
            candidate.candidateFirstName or "",
            candidate.candidateMiddleName or "",
            candidate.candidateLastName or ""
        ]
        candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"

    # Resolve job title
    job_title = None
    if panel.job_id:
        job = db.query(Jobs).filter(Jobs.jobID == panel.job_id).first()
        job_title = job.jobTitle if job else None

    # Count members and interviews
    member_count = db.query(PanelMember).filter(PanelMember.panel_id == panel_id).count()
    interview_count = db.query(Interview).filter(Interview.panel_id == panel_id).count()

    return InterviewPanelWithDetails(
        id=panel.id,
        candidate_id=panel.candidate_id,
        candidate_name=candidate_name,
        round_name=panel.round_name,
        job_id=panel.job_id,
        job_title=job_title,
        created_at=panel.created_at,
        member_count=member_count,
        interview_count=interview_count
    )


@router.get(
    "/panels",
    response_model=List[InterviewPanelWithDetails],
    dependencies=[Depends(require_resource_permission("interviews", "view"))],
)
def get_all_interview_panels(
    candidate_id: Optional[str] = Query(None, description="Filter by candidate ID"),
    round_name: Optional[str] = Query(None, description="Filter by round name"),
    job_id: Optional[str] = Query(None, description="Filter by job ID"),
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get all interview panels with optional filtering.

    Args:
        candidate_id: Optional filter by candidate ID
        round_name: Optional filter by round name
        job_id: Optional filter by job ID
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        List of InterviewPanelWithDetails
    """
    query = db.query(InterviewPanel)

    if candidate_id:
        query = query.filter(InterviewPanel.candidate_id == candidate_id)
    if round_name:
        query = query.filter(InterviewPanel.round_name == round_name)
    if job_id:
        query = query.filter(InterviewPanel.job_id == job_id)

    panels = query.all()

    results = []
    for panel in panels:
        # Get candidate details
        candidate = db.query(Candidate).filter(Candidate.candidateID == panel.candidate_id).first()
        candidate_name = "N/A"
        if candidate:
            name_parts = [
                candidate.candidateFirstName or "",
                candidate.candidateMiddleName or "",
                candidate.candidateLastName or ""
            ]
            candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"

        # Resolve job title
        job_title = None
        if panel.job_id:
            job = db.query(Jobs).filter(Jobs.jobID == panel.job_id).first()
            job_title = job.jobTitle if job else None

        # Count members and interviews
        member_count = db.query(PanelMember).filter(PanelMember.panel_id == panel.id).count()
        interview_count = db.query(Interview).filter(Interview.panel_id == panel.id).count()

        results.append(InterviewPanelWithDetails(
            id=panel.id,
            candidate_id=panel.candidate_id,
            candidate_name=candidate_name,
            round_name=panel.round_name,
            job_id=panel.job_id,
            job_title=job_title,
            created_at=panel.created_at,
            member_count=member_count,
            interview_count=interview_count
        ))

    return results


@router.delete(
    "/panels/{panel_id}",
    dependencies=[Depends(get_current_user)],
    response_model=DeleteResponse,

)
def delete_interview_panel(
    panel_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Delete an interview panel and all associated data.
    
    Args:
        panel_id: ID of the panel to delete
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        DeleteResponse with success message
        
    Raises:
        HTTPException: If panel not found
    """
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == panel_id).first()
    if not panel:
        raise HTTPException(
            status_code=404,
            detail=f"Interview panel with ID {panel_id} not found"
        )
    
    # Delete associated interviews and their feedback
    interviews = db.query(Interview).filter(Interview.panel_id == panel_id).all()
    for interview in interviews:
        db.query(InterviewFeedback).filter(InterviewFeedback.interview_id == interview.id).delete()
    
    # Delete interviews
    db.query(Interview).filter(Interview.panel_id == panel_id).delete()
    
    # Delete panel members
    db.query(PanelMember).filter(PanelMember.panel_id == panel_id).delete()
    
    # Delete panel
    db.delete(panel)
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Interview panel {panel_id} and all associated data deleted successfully"
    )


# ============================================
# Rehire Guard Endpoints (2026-08-05)
# ============================================

def _rehire_review_to_response(db: Session, review: InterviewRehireReview) -> RehireReviewResponse:
    candidate = db.query(Candidate).filter(Candidate.candidateID == review.candidate_id).first()
    requester = db.query(Users).filter(Users.UserID == review.requested_by).first() if review.requested_by else None
    job = db.query(Jobs).filter(Jobs.jobID == review.job_id).first() if review.job_id else None

    return RehireReviewResponse(
        id=review.id,
        candidate_id=review.candidate_id,
        candidate_name=_candidate_display_name(candidate) if candidate else None,
        round_name=review.round_name,
        job_id=review.job_id,
        job_title=job.jobTitle if job else None,
        requested_by=review.requested_by,
        requested_by_name=requester.UserName if requester else None,
        justification=review.justification,
        past_no_hire_panel_ids=review.past_no_hire_panel_ids,
        status=review.status,
        ai_decision=review.ai_decision,
        ai_reasoning=review.ai_reasoning,
        ai_confidence=float(review.ai_confidence) if review.ai_confidence is not None else None,
        decided_by=review.decided_by,
        decided_at=review.decided_at,
        decision_note=review.decision_note,
        resulting_panel_id=review.resulting_panel_id,
        created_at=review.created_at,
    )


@router.get(
    "/rehire-reviews",
    dependencies=[Depends(get_current_user)],
    response_model=RehireReviewListResponse,

)
def list_rehire_reviews(
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user),
):
    """
    Pending rehire-guard reviews awaiting a hiring manager's decision --
    candidates with a past no-hire outcome whose re-interview
    justification was NOT clearly justified enough for AI to auto-clear.
    No InterviewPanel exists for any of these yet.
    """
    reviews = get_pending_rehire_reviews(db)
    return RehireReviewListResponse(
        total=len(reviews),
        reviews=[_rehire_review_to_response(db, r) for r in reviews],
    )


@router.post(
    "/rehire-reviews/{review_id}/decide",
    dependencies=[Depends(get_current_user)],
    response_model=RehireReviewResponse,

)
def decide_rehire_review_endpoint(
    review_id: int,
    request: RehireReviewDecideRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user),
):
    """
    Hiring manager approves or rejects a pending rehire review. Approve
    creates the real interview panel for the first time -- it does not
    exist until this call succeeds. Reject leaves no panel, ever.
    """
    decision = (request.decision or "").strip().lower()
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    try:
        review = decide_rehire_review(db, review_id, decision, user.UserID, request.note)
    except RehireReviewNotFound:
        raise HTTPException(status_code=404, detail=f"Rehire review {review_id} not found")
    except RehireReviewAlreadyDecided as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return _rehire_review_to_response(db, review)


def _panel_diversity_warning(db: Session, panel: InterviewPanel, interviewer_id: str) -> str | None:
    """Backlog item, 2026-08-05 (wros_interview_regrouping_and_rehire_guard_priority):
    Avinash -- "we also need to ensure that same panel is not used if
    different jobs, different clients but same candidate ... allows us
    to get different perspective on the candidate." Advisory only (same
    "advisory where it can decide" posture as Task priority validation)
    -- a recruiter may have a real reason to reuse an interviewer (e.g.
    no one else has the required skill), so this warns rather than
    blocks. Only flags OTHER panels for the same candidate on a
    DIFFERENT job -- reusing the same interviewer across rounds of the
    SAME job (e.g. L1 and L2 both by the same panel) is normal and not
    a diversity concern."""
    past_panels = (
        db.query(InterviewPanel)
        .join(PanelMember, PanelMember.panel_id == InterviewPanel.id)
        .filter(
            InterviewPanel.candidate_id == panel.candidate_id,
            InterviewPanel.id != panel.id,
            PanelMember.interviewer_id == interviewer_id,
        )
        .all()
    )
    if not past_panels:
        return None

    if panel.job_id is not None:
        past_panels = [p for p in past_panels if p.job_id != panel.job_id]
        if not past_panels:
            return None

    return (
        f"Interviewer {interviewer_id} already served on a panel for this candidate "
        f"on {len(past_panels)} other job(s) -- consider a different interviewer for "
        f"a fresh perspective."
    )


# ============================================
# Panel Member Endpoints
# ============================================

@router.post(
    "/panel-members/assign",
    dependencies=[Depends(get_current_user)],
    response_model=PanelMemberResponse,
    status_code=201,

)
def assign_panel_member(
    request: PanelMemberCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Assign an interviewer to an interview panel.
    
    Args:
        request: PanelMemberCreate with panel_id and interviewer_id
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        PanelMemberResponse with assignment details
        
    Raises:
        HTTPException: If panel or interviewer not found, or already assigned
    """
    # Verify panel exists
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(
            status_code=404,
            detail=f"Interview panel with ID {request.panel_id} not found"
        )
    
    # Verify interviewer exists
    interviewer = db.query(Users).filter(Users.UserID == request.interviewer_id).first()
    if not interviewer:
        raise HTTPException(
            status_code=404,
            detail=f"Interviewer with ID {request.interviewer_id} not found"
        )
    
    # Check if already assigned
    existing = db.query(PanelMember).filter(
        PanelMember.panel_id == request.panel_id,
        PanelMember.interviewer_id == request.interviewer_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Interviewer {request.interviewer_id} is already assigned to panel {request.panel_id}"
        )
    
    diversity_warning = _panel_diversity_warning(db, panel, request.interviewer_id)

    # Create panel member
    panel_member = PanelMember(
        panel_id=request.panel_id,
        interviewer_id=request.interviewer_id
    )

    db.add(panel_member)
    db.commit()
    db.refresh(panel_member)

    # Fix 5: schedule feedback reminders for this new member on any
    # active (Scheduled) interviews already linked to their panel.
    try:
        active_interviews = (
            db.query(Interview)
            .filter(
                Interview.panel_id == request.panel_id,
                Interview.status == "Scheduled",
            )
            .all()
        )
        for iv in active_interviews:
            _schedule_feedback_reminders(iv, db)
            sync_pending_feedback_tasks_for_interview(db, iv)
            logger.info(
                f"[FeedbackReminder] Scheduled reminders for new panel member "
                f"{request.interviewer_id} on interview {iv.id}."
            )
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(
            f"[FeedbackReminder] Could not schedule reminders for new panel member "
            f"{request.interviewer_id}: {exc}"
        )

    return PanelMemberResponse(
        id=panel_member.id,
        panel_id=panel_member.panel_id,
        interviewer_id=panel_member.interviewer_id,
        diversity_warning=diversity_warning,
    )


@router.get(
    "/panel-members/{panel_id}",
    response_model=List[PanelMemberWithDetails],
    dependencies=[Depends(require_resource_permission("interviews", "view"))],
)
def get_panel_members(
    panel_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get all members of a specific panel.

    Args:
        panel_id: ID of the panel
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        List of PanelMemberWithDetails

    Raises:
        HTTPException: If panel not found
    """
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == panel_id).first()
    if not panel:
        raise HTTPException(
            status_code=404,
            detail=f"Interview panel with ID {panel_id} not found"
        )

    members = db.query(PanelMember).filter(PanelMember.panel_id == panel_id).all()

    results = []
    for member in members:
        interviewer = db.query(Users).filter(Users.UserID == member.interviewer_id).first()
        if interviewer:
            bu_name = None
            if interviewer.business_unit:
                bu_name = interviewer.business_unit.name
            results.append(PanelMemberWithDetails(
                id=member.id,
                panel_id=member.panel_id,
                interviewer_id=member.interviewer_id,
                interviewer_name=interviewer.UserName or "N/A",
                interviewer_email=interviewer.UserEmail,
                interviewer_role=interviewer.UserRole,
                business_unit_name=bu_name
            ))

    return results


@router.delete(
    "/panel-members/{member_id}",
    dependencies=[Depends(get_current_user)],
    response_model=DeleteResponse,

)
def remove_panel_member(
    member_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Remove an interviewer from a panel.
    
    Args:
        member_id: ID of the panel member to remove
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        DeleteResponse with success message
        
    Raises:
        HTTPException: If panel member not found
    """
    member = db.query(PanelMember).filter(PanelMember.id == member_id).first()
    if not member:
        raise HTTPException(
            status_code=404,
            detail=f"Panel member with ID {member_id} not found"
        )
    
    db.delete(member)
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Panel member {member_id} removed successfully"
    )


# ============================================
# Interview Endpoints
# ============================================

@router.post(
    "/create",
    dependencies=[Depends(get_current_user)],
    response_model=InterviewResponse,
    status_code=201,

)
def create_interview(
    request: InterviewCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Create a new interview.

    Args:
        request: InterviewCreate with interview details
        db: Database session
        user: Authenticated HR/Admin user

    Returns:
        InterviewResponse with interview details

    Raises:
        HTTPException: If panel or candidate not found, or time validation fails
    """
    # Verify panel exists
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == request.panel_id).first()
    if not panel:
        raise HTTPException(
            status_code=404,
            detail=f"Interview panel with ID {request.panel_id} not found"
        )

    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.candidateID == request.candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {request.candidate_id} not found"
        )

    # Validate time
    if request.end_time <= request.start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    # Create interview
    interview = Interview(
        panel_id=request.panel_id,
        candidate_id=request.candidate_id,
        start_time=request.start_time,
        end_time=request.end_time,
        meeting_link=request.meeting_link,
        outlook_event_id=request.outlook_event_id,
        status=request.status
    )

    db.add(interview)

    # Queue interview_scheduled message (BEFORE commit for atomicity)
    MessageQueueService.enqueue(
        message_type="interview_scheduled",
        payload={
            "interview_id": interview.id,
            "candidate_id": request.candidate_id,
            "panel_id": request.panel_id,
            "start_time": request.start_time.isoformat() if hasattr(request.start_time, 'isoformat') else str(request.start_time),
            "end_time": request.end_time.isoformat() if hasattr(request.end_time, 'isoformat') else str(request.end_time),
            "meeting_link": request.meeting_link,
            "candidate_email": candidate.candidateEmail,
            "candidate_name": f"{candidate.candidateFirstName or ''} {candidate.candidateLastName or ''}".strip(),
        },
        resource_id=request.candidate_id,
        queue_type="EMAIL_QUEUE",
        created_by=user.UserID,
        db=db,
    )

    # ATOMIC COMMIT
    db.commit()
    db.refresh(interview)

    # Schedule pre-interview reminder (1 h and 15 min before start)
    _schedule_interview_reminder(interview, db)

    # Schedule post-interview feedback reminders (1 h and 24 h after end)
    try:
        _schedule_feedback_reminders(interview, db)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[FeedbackReminder] Scheduler error on create (non-critical): {exc}")

    # Backlog item, 2026-08-05: real Task Dashboard entries for each
    # panel member's pending feedback, scoped to this exact round --
    # additive to the email reminders above, not a replacement.
    sync_pending_feedback_tasks_for_interview(db, interview)

    return InterviewResponse(
        id=interview.id,
        panel_id=interview.panel_id,
        candidate_id=interview.candidate_id,
        start_time=interview.start_time,
        end_time=interview.end_time,
        meeting_link=interview.meeting_link,
        outlook_event_id=interview.outlook_event_id,
        status=interview.status
    )


# ============================================
# My Interviews Endpoint
# ============================================

@router.get(
    "/my-interviews",
    dependencies=[Depends(get_current_user)],
    response_model=MyInterviewsResponse,
    summary="Get my interviews",
    description=(
        "Returns all interviews where the authenticated user is a panel member. "
        "For completed interviews, includes any feedback the user has already submitted for that candidate."
    ),
)
def get_my_interviews(
    status: Optional[str] = Query(None, description="Filter by interview status (Scheduled, Completed, Cancelled)"),
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get all interviews where the current user is a panel member.

    - Lists every interview across all panels the user has been assigned to.
    - If the interview is **Completed**, the user's own feedback for that
      interview is embedded in ``my_feedback`` (``None`` when not yet submitted).
    - ``feedback_submitted`` is ``True`` when the user has already given feedback.
    - ``pending_feedback`` in the summary counts completed interviews with no
      feedback from the user yet.

    Args:
        status: Optional filter (Scheduled | Completed | Cancelled)
        db: Database session
        user: Authenticated HR/Admin user (must be a panel member)

    Returns:
        MyInterviewsResponse with aggregated interview list
    """
    current_user_id: str = user.UserID

    # Find all panels where this user is a member
    memberships = (
        db.query(PanelMember)
        .filter(PanelMember.interviewer_id == current_user_id)
        .all()
    )

    if not memberships:
        return MyInterviewsResponse(
            interviewer_id=current_user_id,
            interviewer_name=user.UserName or "N/A",
            total_interviews=0,
            pending_feedback=0,
            interviews=[]
        )

    panel_ids = [m.panel_id for m in memberships]

    # Fetch all interviews for those panels
    interview_query = db.query(Interview).filter(Interview.panel_id.in_(panel_ids))
    if status:
        interview_query = interview_query.filter(Interview.status == status)

    interviews = interview_query.order_by(Interview.start_time.desc()).all()

    results = []
    pending_feedback = 0

    for interview in interviews:
        # Panel / round information
        panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
        round_name = panel.round_name if panel else "N/A"

        # Candidate information
        candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
        candidate_name = "N/A"
        candidate_email = "N/A"
        if candidate:
            name_parts = [
                candidate.candidateFirstName or "",
                candidate.candidateMiddleName or "",
                candidate.candidateLastName or ""
            ]
            candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
            candidate_email = candidate.candidateEmail or "N/A"

        # Check if this user has submitted feedback for this interview
        my_feedback_record = (
            db.query(InterviewFeedback)
            .filter(
                InterviewFeedback.interview_id == interview.id,
                InterviewFeedback.interviewer_id == current_user_id
            )
            .first()
        )

        feedback_submitted = my_feedback_record is not None
        my_feedback_schema = None

        if interview.status == "Completed":
            if my_feedback_record:
                avg_score = (
                    my_feedback_record.technical_score +
                    my_feedback_record.communication_score +
                    my_feedback_record.problem_solving_score +
                    my_feedback_record.culture_fit_score
                ) / 4.0
                my_feedback_schema = MyInterviewFeedback(
                    feedback_id=my_feedback_record.id,
                    technical_score=my_feedback_record.technical_score,
                    communication_score=my_feedback_record.communication_score,
                    problem_solving_score=my_feedback_record.problem_solving_score,
                    culture_fit_score=my_feedback_record.culture_fit_score,
                    average_score=round(avg_score, 2),
                    comments=my_feedback_record.comments,
                    recommendation=my_feedback_record.recommendation,
                    submitted_at=my_feedback_record.submitted_at
                )
            else:
                # Completed but no feedback from this user yet
                pending_feedback += 1

        results.append(MyInterviewItem(
            interview_id=interview.id,
            panel_id=interview.panel_id,
            round_name=round_name,
            candidate_id=interview.candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            start_time=interview.start_time,
            end_time=interview.end_time,
            meeting_link=interview.meeting_link,
            status=interview.status,
            feedback_submitted=feedback_submitted,
            my_feedback=my_feedback_schema
        ))

    return MyInterviewsResponse(
        interviewer_id=current_user_id,
        interviewer_name=user.UserName or "N/A",
        total_interviews=len(results),
        pending_feedback=pending_feedback,
        interviews=results
    )


@router.get(
    "/{interview_id}",
    response_model=InterviewDetailedResponse,
    dependencies=[Depends(require_resource_permission("interviews", "view"))],
)
def get_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get details of a specific interview.
    
    Args:
        interview_id: ID of the interview
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewDetailedResponse with complete interview details
        
    Raises:
        HTTPException: If interview not found
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=404,
            detail=f"Interview with ID {interview_id} not found"
        )
    
    # Get panel details
    panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
    panel_round_name = panel.round_name if panel else "N/A"
    
    # Get candidate details
    candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
    candidate_name = "N/A"
    candidate_email = "N/A"
    if candidate:
        name_parts = [
            candidate.candidateFirstName or "",
            candidate.candidateMiddleName or "",
            candidate.candidateLastName or ""
        ]
        candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
        candidate_email = candidate.candidateEmail
    
    # Count feedback
    feedback_count = db.query(InterviewFeedback).filter(
        InterviewFeedback.interview_id == interview_id
    ).count()
    
    return InterviewDetailedResponse(
        id=interview.id,
        panel_id=interview.panel_id,
        panel_round_name=panel_round_name,
        candidate_id=interview.candidate_id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        start_time=interview.start_time,
        end_time=interview.end_time,
        meeting_link=interview.meeting_link,
        outlook_event_id=interview.outlook_event_id,
        status=interview.status,
        feedback_count=feedback_count,
        feedback_status=interview.feedback_status,
    )


@router.get(
    "",
    response_model=List[InterviewDetailedResponse],
    dependencies=[Depends(require_resource_permission("interviews", "view"))],
)
def get_all_interviews(
    candidate_id: Optional[str] = Query(None, description="Filter by candidate ID"),
    panel_id: Optional[int] = Query(None, description="Filter by panel ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get all interviews with optional filtering.
    
    Args:
        candidate_id: Optional filter by candidate ID
        panel_id: Optional filter by panel ID
        status: Optional filter by status
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        List of InterviewDetailedResponse
    """
    query = db.query(Interview)
    
    if candidate_id:
        query = query.filter(Interview.candidate_id == candidate_id)
    if panel_id:
        query = query.filter(Interview.panel_id == panel_id)
    if status:
        query = query.filter(Interview.status == status)
    
    interviews = query.all()
    
    results = []
    for interview in interviews:
        # Get panel details
        panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
        panel_round_name = panel.round_name if panel else "N/A"
        
        # Get candidate details
        candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
        candidate_name = "N/A"
        candidate_email = "N/A"
        if candidate:
            name_parts = [
                candidate.candidateFirstName or "",
                candidate.candidateMiddleName or "",
                candidate.candidateLastName or ""
            ]
            candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
            candidate_email = candidate.candidateEmail
        
        # Count feedback
        feedback_count = db.query(InterviewFeedback).filter(
            InterviewFeedback.interview_id == interview.id
        ).count()
        
        results.append(InterviewDetailedResponse(
            id=interview.id,
            panel_id=interview.panel_id,
            panel_round_name=panel_round_name,
            candidate_id=interview.candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            start_time=interview.start_time,
            end_time=interview.end_time,
            meeting_link=interview.meeting_link,
            outlook_event_id=interview.outlook_event_id,
            status=interview.status,
            feedback_count=feedback_count,
            feedback_status=interview.feedback_status,
        ))
    
    return results


@router.put(
    "/{interview_id}",
    dependencies=[Depends(get_current_user)],
    response_model=InterviewResponse,

)
def update_interview(
    interview_id: int,
    request: InterviewUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Update an existing interview.
    
    Args:
        interview_id: ID of the interview to update
        request: InterviewUpdate with fields to update
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewResponse with updated interview details
        
    Raises:
        HTTPException: If interview not found or validation fails
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=404,
            detail=f"Interview with ID {interview_id} not found"
        )

    previous_status = interview.status

    # Update only provided fields
    if request.start_time is not None:
        interview.start_time = request.start_time
    if request.end_time is not None:
        interview.end_time = request.end_time
    if request.meeting_link is not None:
        interview.meeting_link = request.meeting_link
    if request.outlook_event_id is not None:
        interview.outlook_event_id = request.outlook_event_id
    if request.status is not None:
        interview.status = request.status
    
    # Validate time if both are set
    if interview.end_time <= interview.start_time:
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )
    
    db.commit()
    db.refresh(interview)

    # Reschedule pre-interview reminder (replaces existing jobs)
    _schedule_interview_reminder(interview, db)

    # Fix 2: if the interview is now Cancelled or Completed, kill all reminder
    # jobs; otherwise reschedule them with the latest end_time.
    if interview.status in ("Cancelled", "Completed"):
        try:
            _cancel_all_feedback_reminders(interview.id, db)
            logger.info(
                f"[FeedbackReminder] Cancelled all feedback reminders for interview "
                f"{interview.id} (status: {interview.status})."
            )
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[FeedbackReminder] Cancel-all error on update (non-critical): {exc}")
    else:
        try:
            _schedule_feedback_reminders(interview, db)
        except Exception as exc:
            logger.error(f"Error: {str(exc)}", exc_info=True)
            logger.warning(f"[FeedbackReminder] Scheduler error on update (non-critical): {exc}")

    # Backlog item, 2026-08-05: create the HM review Task the first time
    # (and only the first time) this interview round transitions into
    # Completed -- re-PUTs of an already-Completed interview must not
    # spawn duplicate tasks.
    if interview.status == "Completed" and previous_status != "Completed":
        _create_hm_review_task(db, interview)

    return InterviewResponse(
        id=interview.id,
        panel_id=interview.panel_id,
        candidate_id=interview.candidate_id,
        start_time=interview.start_time,
        end_time=interview.end_time,
        meeting_link=interview.meeting_link,
        outlook_event_id=interview.outlook_event_id,
        status=interview.status
    )


@router.delete(
    "/{interview_id}",
    dependencies=[Depends(get_current_user)],
    response_model=DeleteResponse,

)
def delete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Delete an interview and all associated feedback.
    
    Args:
        interview_id: ID of the interview to delete
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        DeleteResponse with success message
        
    Raises:
        HTTPException: If interview not found
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=404,
            detail=f"Interview with ID {interview_id} not found"
        )
    
    # Fix 3: cancel all scheduler jobs BEFORE removing DB records so the
    # helper functions can still read panel membership from the database.
    try:
        _cancel_all_feedback_reminders(interview_id, db)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[FeedbackReminder] Cancel-all error on delete (non-critical): {exc}")
    try:
        _cancel_interview_reminders(interview_id)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[InterviewReminder] Cancel error on delete (non-critical): {exc}")

    # Delete all associated feedback
    db.query(InterviewFeedback).filter(InterviewFeedback.interview_id == interview_id).delete()

    # Delete the interview
    db.delete(interview)
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Interview {interview_id} and all associated feedback deleted successfully"
    )


# ============================================
# Interview Feedback Endpoints
# ============================================

@router.post(
    "/feedback/submit",
    response_model=InterviewFeedbackResponse,
    status_code=201,
    dependencies=[Depends(require_resource_permission("interviews", "edit"))],
)
def submit_interview_feedback(
    request: InterviewFeedbackCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Submit interview feedback.
    
    Args:
        request: InterviewFeedbackCreate with feedback details
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewFeedbackResponse with feedback details
        
    Raises:
        HTTPException: If interview or interviewer not found, or validation fails
    """
    # Verify interview exists
    interview = db.query(Interview).filter(Interview.id == request.interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=404,
            detail=f"Interview with ID {request.interview_id} not found"
        )
    
    # Verify interviewer exists
    interviewer = db.query(Users).filter(Users.UserID == request.interviewer_id).first()
    if not interviewer:
        raise HTTPException(
            status_code=404,
            detail=f"Interviewer with ID {request.interviewer_id} not found"
        )
    
    # Validate recommendation
    valid_recommendations = ["No Hire","Not sure","Average","Hire","Must Hire"]
    if request.recommendation not in valid_recommendations:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid recommendation. Must be one of: {', '.join(valid_recommendations)}"
        )
    
    # Fix 4: block duplicate submissions from the same interviewer
    existing_feedback = db.query(InterviewFeedback).filter(
        InterviewFeedback.interview_id == request.interview_id,
        InterviewFeedback.interviewer_id == request.interviewer_id,
    ).first()
    if existing_feedback:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Interviewer {request.interviewer_id} has already submitted feedback "
                f"for interview {request.interview_id}."
            ),
        )

    # Create feedback
    feedback = InterviewFeedback(
        interview_id=request.interview_id,
        interviewer_id=request.interviewer_id,
        technical_score=request.technical_score,
        communication_score=request.communication_score,
        problem_solving_score=request.problem_solving_score,
        culture_fit_score=request.culture_fit_score,
        comments=request.comments,
        recommendation=request.recommendation
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    close_pending_feedback_task(db, request.interview_id, request.interviewer_id)

    # Auto-complete interview status when last panel member submits feedback
    try:
        # Get all panel members assigned to this interview's panel
        panel_members = (
            db.query(PanelMember)
            .filter(PanelMember.panel_id == interview.panel_id)
            .all()
        )
        panel_member_ids = {pm.interviewer_id for pm in panel_members}

        if panel_member_ids:
            # Get all interviewers who have submitted feedback for this interview
            submitted_ids = {
                fb.interviewer_id
                for fb in db.query(InterviewFeedback)
                .filter(InterviewFeedback.interview_id == interview.id)
                .all()
            }

            # If every panel member has now submitted feedback, mark interview as Completed
            if panel_member_ids.issubset(submitted_ids):
                if interview.status != "Completed":
                    interview.status = "Completed"
                    interview.feedback_status = "Completed"
                    db.commit()
                    logger.info(
                        f"[FeedbackComplete] Interview #{interview.id} marked as Completed - "
                        f"all {len(panel_member_ids)} panel member(s) have submitted feedback."
                    )

                    # Wire SLM: Record interview outcome
                    try:
                        from app.services.slm_job_metadata_service import SLMJobMetadataService
                        if interview.job_id:
                            SLMJobMetadataService.record_hiring_outcome(
                                db=db,
                                job_id=str(interview.job_id),
                                candidate_interviewed=True
                            )
                            logger.info(f"[SLM] Recorded interview completion for job: {interview.job_id}")
                    except Exception as e:
                        logger.error(f"Error: {str(e)}", exc_info=True)
                        logger.error(f"[SLM] Failed to record interview outcome: {e}", exc_info=True)
                        # Continue - SLM failure should not block interview processing

                    _create_hm_review_task(db, interview)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[FeedbackComplete] Auto-complete check failed non-critically: {exc}")

    # Auto-hire check: promote to Approval if all interviews are Hire/Must Hire
    try:
        _check_and_auto_submit_for_hire(interview, db)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[AutoHire] check failed non-critically: {exc}")

    # â"€â"€ Notify HM + HR + panel members that feedback was submitted â"€â"€â"€â"€â"€â"€â"€â"€
    try:
        _notify_feedback_submitted(interview, feedback, user, db)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[FeedbackNotify] Notification error (non-critical): {exc}")

    # â"€â"€ Cancel pending feedback reminders for the member who just submitted â"€â"€
    try:
        _cancel_feedback_reminders(interview.id, request.interviewer_id)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[FeedbackReminder] Cancel error (non-critical): {exc}")

    return InterviewFeedbackResponse(
        id=feedback.id,
        interview_id=feedback.interview_id,
        interviewer_id=feedback.interviewer_id,
        technical_score=feedback.technical_score,
        communication_score=feedback.communication_score,
        problem_solving_score=feedback.problem_solving_score,
        culture_fit_score=feedback.culture_fit_score,
        comments=feedback.comments,
        recommendation=feedback.recommendation,
        submitted_at=feedback.submitted_at
    )


@router.get(
    "/feedback/interview/{interview_id}",
    response_model=List[InterviewFeedbackWithDetails],
    dependencies=[Depends(require_resource_permission("interviews", "view"))],
)
def get_feedback_by_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get all feedback for a specific interview.
    
    Args:
        interview_id: ID of the interview
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        List of InterviewFeedbackWithDetails
        
    Raises:
        HTTPException: If interview not found
    """
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(
            status_code=404,
            detail=f"Interview with ID {interview_id} not found"
        )
    
    feedbacks = db.query(InterviewFeedback).filter(
        InterviewFeedback.interview_id == interview_id
    ).all()
    
    results = []
    for feedback in feedbacks:
        interviewer = db.query(Users).filter(Users.UserID == feedback.interviewer_id).first()
        
        # Calculate average score
        avg_score = (
            feedback.technical_score +
            feedback.communication_score +
            feedback.problem_solving_score +
            feedback.culture_fit_score
        ) / 4.0
        
        results.append(InterviewFeedbackWithDetails(
            id=feedback.id,
            interview_id=feedback.interview_id,
            interviewer_id=feedback.interviewer_id,
            interviewer_name=interviewer.UserName if interviewer else "N/A",
            interviewer_email=interviewer.UserEmail if interviewer else "N/A",
            technical_score=feedback.technical_score,
            communication_score=feedback.communication_score,
            problem_solving_score=feedback.problem_solving_score,
            culture_fit_score=feedback.culture_fit_score,
            average_score=round(avg_score, 2),
            comments=feedback.comments,
            recommendation=feedback.recommendation,
            submitted_at=feedback.submitted_at
        ))
    
    return results


@router.get(
    "/feedback/{feedback_id}",
    response_model=InterviewFeedbackWithDetails,
    dependencies=[Depends(require_resource_permission("feedback", "view"))]
)
def get_feedback_by_id(
    feedback_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get specific feedback details.
    
    Args:
        feedback_id: ID of the feedback
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewFeedbackWithDetails
        
    Raises:
        HTTPException: If feedback not found
    """
    feedback = db.query(InterviewFeedback).filter(InterviewFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(
            status_code=404,
            detail=f"Feedback with ID {feedback_id} not found"
        )
    
    interviewer = db.query(Users).filter(Users.UserID == feedback.interviewer_id).first()
    
    # Calculate average score
    avg_score = (
        feedback.technical_score +
        feedback.communication_score +
        feedback.problem_solving_score +
        feedback.culture_fit_score
    ) / 4.0
    
    return InterviewFeedbackWithDetails(
        id=feedback.id,
        interview_id=feedback.interview_id,
        interviewer_id=feedback.interviewer_id,
        interviewer_name=interviewer.UserName if interviewer else "N/A",
        interviewer_email=interviewer.UserEmail if interviewer else "N/A",
        technical_score=feedback.technical_score,
        communication_score=feedback.communication_score,
        problem_solving_score=feedback.problem_solving_score,
        culture_fit_score=feedback.culture_fit_score,
        average_score=round(avg_score, 2),
        comments=feedback.comments,
        recommendation=feedback.recommendation,
        submitted_at=feedback.submitted_at
    )


@router.put(
    "/feedback/{feedback_id}",
    response_model=InterviewFeedbackResponse,
    dependencies=[Depends(require_resource_permission("feedback", "update"))]
)
def update_interview_feedback(
    feedback_id: int,
    request: InterviewFeedbackUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Update existing interview feedback.
    
    Args:
        feedback_id: ID of the feedback to update
        request: InterviewFeedbackUpdate with fields to update
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewFeedbackResponse with updated feedback
        
    Raises:
        HTTPException: If feedback not found or validation fails
    """
    feedback = db.query(InterviewFeedback).filter(InterviewFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(
            status_code=404,
            detail=f"Feedback with ID {feedback_id} not found"
        )
    
    # Update only provided fields
    if request.technical_score is not None:
        feedback.technical_score = request.technical_score
    if request.communication_score is not None:
        feedback.communication_score = request.communication_score
    if request.problem_solving_score is not None:
        feedback.problem_solving_score = request.problem_solving_score
    if request.culture_fit_score is not None:
        feedback.culture_fit_score = request.culture_fit_score
    if request.comments is not None:
        feedback.comments = request.comments
    if request.recommendation is not None:
        # Validate recommendation
        valid_recommendations = ["Hire", "Hold", "Reject"]
        if request.recommendation not in valid_recommendations:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid recommendation. Must be one of: {', '.join(valid_recommendations)}"
            )
        feedback.recommendation = request.recommendation
    
    db.commit()
    db.refresh(feedback)
    
    return InterviewFeedbackResponse(
        id=feedback.id,
        interview_id=feedback.interview_id,
        interviewer_id=feedback.interviewer_id,
        technical_score=feedback.technical_score,
        communication_score=feedback.communication_score,
        problem_solving_score=feedback.problem_solving_score,
        culture_fit_score=feedback.culture_fit_score,
        comments=feedback.comments,
        recommendation=feedback.recommendation,
        submitted_at=feedback.submitted_at
    )


@router.delete(
    "/feedback/{feedback_id}",
    response_model=DeleteResponse,
    dependencies=[Depends(require_resource_permission("feedback", "delete"))]
)
def delete_interview_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Delete interview feedback.
    
    Args:
        feedback_id: ID of the feedback to delete
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        DeleteResponse with success message
        
    Raises:
        HTTPException: If feedback not found
    """
    feedback = db.query(InterviewFeedback).filter(InterviewFeedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(
            status_code=404,
            detail=f"Feedback with ID {feedback_id} not found"
        )
    
    db.delete(feedback)
    db.commit()
    
    return DeleteResponse(
        status="Success",
        message=f"Feedback {feedback_id} deleted successfully"
    )


# ============================================
# Statistics and Analytics Endpoints
# ============================================

@router.get(
    "/statistics",
    response_model=InterviewStatistics,
    dependencies=[Depends(require_resource_permission("statistic", "view"))]
)
def get_interview_statistics(
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get overall interview statistics.
    
    Args:
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewStatistics with counts and averages
    """
    total_interviews = db.query(Interview).count()
    scheduled = db.query(Interview).filter(Interview.status == "Scheduled").count()
    completed = db.query(Interview).filter(Interview.status == "Completed").count()
    cancelled = db.query(Interview).filter(Interview.status == "Cancelled").count()
    total_panels = db.query(InterviewPanel).count()
    total_feedback = db.query(InterviewFeedback).count()
    
    # Calculate average feedback score
    avg_score = None
    if total_feedback > 0:
        feedbacks = db.query(InterviewFeedback).all()
        total_score = sum(
            (f.technical_score + f.communication_score + 
             f.problem_solving_score + f.culture_fit_score) / 4.0
            for f in feedbacks
        )
        avg_score = round(total_score / total_feedback, 2)
    
    return InterviewStatistics(
        total_interviews=total_interviews,
        scheduled=scheduled,
        completed=completed,
        cancelled=cancelled,
        total_panels=total_panels,
        total_feedback=total_feedback,
        average_feedback_score=avg_score
    )


@router.get("/candidate-history/{candidate_id}", response_model=CandidateInterviewHistory, dependencies=[Depends(require_resource_permission("candidates", "view"))],
 )
def get_candidate_interview_history(
    candidate_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get complete interview history for a candidate.
    
    Args:
        candidate_id: ID of the candidate
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        CandidateInterviewHistory with all interview details
        
    Raises:
        HTTPException: If candidate not found
    """
    candidate = db.query(Candidate).filter(Candidate.candidateID == candidate_id).first()
    if not candidate:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate with ID {candidate_id} not found"
        )
    
    # Get candidate name
    name_parts = [
        candidate.candidateFirstName or "",
        candidate.candidateMiddleName or "",
        candidate.candidateLastName or ""
    ]
    candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
    
    # Get all interviews
    interviews = db.query(Interview).filter(Interview.candidate_id == candidate_id).all()
    
    total_interviews = len(interviews)
    scheduled_interviews = sum(1 for i in interviews if i.status == "Scheduled")
    completed_interviews = sum(1 for i in interviews if i.status == "Completed")
    cancelled_interviews = sum(1 for i in interviews if i.status == "Cancelled")
    
    # Build detailed interview list
    interview_details = []
    for interview in interviews:
        panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
        panel_round_name = panel.round_name if panel else "N/A"
        # 2026-08-05 -- surfaces InterviewPanel.job_id so the frontend can
        # group a candidate's interview history by job (a candidate can
        # legitimately be interviewed for more than one job over time).
        job_id = panel.job_id if panel else None
        job_title = None
        if job_id:
            job = db.query(Jobs).filter(Jobs.jobID == job_id).first()
            job_title = job.jobTitle if job else None

        feedback_count = db.query(InterviewFeedback).filter(
            InterviewFeedback.interview_id == interview.id
        ).count()

        interview_details.append(InterviewDetailedResponse(
            id=interview.id,
            panel_id=interview.panel_id,
            panel_round_name=panel_round_name,
            job_id=job_id,
            job_title=job_title,
            candidate_id=interview.candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate.candidateEmail,
            start_time=interview.start_time,
            end_time=interview.end_time,
            meeting_link=interview.meeting_link,
            outlook_event_id=interview.outlook_event_id,
            status=interview.status,
            feedback_count=feedback_count
        ))
    
    return CandidateInterviewHistory(
        candidate_id=candidate_id,
        candidate_name=candidate_name,
        candidate_email=candidate.candidateEmail,
        total_interviews=total_interviews,
        scheduled_interviews=scheduled_interviews,
        completed_interviews=completed_interviews,
        cancelled_interviews=cancelled_interviews,
        interviews=interview_details
    )


@router.get(
    "/interviewer-workload/{interviewer_id}",
    response_model=InterviewerWorkload,
    dependencies=[Depends(require_resource_permission("interviewer-workload", "view"))]
)
def get_interviewer_workload(
    interviewer_id: str,
    db: Session = Depends(get_db),
    user = Depends(get_current_internal_user)
):
    """
    Get workload statistics for an interviewer.
    
    Args:
        interviewer_id: ID of the interviewer
        db: Database session
        user: Authenticated HR/Admin user
        
    Returns:
        InterviewerWorkload with statistics and upcoming interviews
        
    Raises:
        HTTPException: If interviewer not found
    """
    interviewer = db.query(Users).filter(Users.UserID == interviewer_id).first()
    if not interviewer:
        raise HTTPException(
            status_code=404,
            detail=f"Interviewer with ID {interviewer_id} not found"
        )
    
    # Get panel memberships
    panel_memberships = db.query(PanelMember).filter(
        PanelMember.interviewer_id == interviewer_id
    ).all()
    
    total_panels = len(panel_memberships)
    panel_ids = [m.panel_id for m in panel_memberships]
    
    # Get all interviews for these panels
    interviews = db.query(Interview).filter(Interview.panel_id.in_(panel_ids)).all() if panel_ids else []
    
    total_interviews = len(interviews)
    scheduled_interviews = sum(1 for i in interviews if i.status == "Scheduled")
    completed_interviews = sum(1 for i in interviews if i.status == "Completed")
    
    # Get feedback submitted by this interviewer
    feedback_submitted = db.query(InterviewFeedback).filter(
        InterviewFeedback.interviewer_id == interviewer_id
    ).count()
    
    # Get upcoming interviews (scheduled, future)
    now = datetime.utcnow()
    upcoming = [i for i in interviews if i.status == "Scheduled" and i.start_time > now]
    
    upcoming_details = []
    for interview in upcoming[:10]:  # Limit to 10 upcoming
        panel = db.query(InterviewPanel).filter(InterviewPanel.id == interview.panel_id).first()
        panel_round_name = panel.round_name if panel else "N/A"
        
        candidate = db.query(Candidate).filter(Candidate.candidateID == interview.candidate_id).first()
        candidate_name = "N/A"
        candidate_email = "N/A"
        if candidate:
            name_parts = [
                candidate.candidateFirstName or "",
                candidate.candidateMiddleName or "",
                candidate.candidateLastName or ""
            ]
            candidate_name = " ".join(filter(None, name_parts)).strip() or "N/A"
            candidate_email = candidate.candidateEmail
        
        feedback_count = db.query(InterviewFeedback).filter(
            InterviewFeedback.interview_id == interview.id
        ).count()
        
        upcoming_details.append(InterviewDetailedResponse(
            id=interview.id,
            panel_id=interview.panel_id,
            panel_round_name=panel_round_name,
            candidate_id=interview.candidate_id,
            candidate_name=candidate_name,
            candidate_email=candidate_email,
            start_time=interview.start_time,
            end_time=interview.end_time,
            meeting_link=interview.meeting_link,
            outlook_event_id=interview.outlook_event_id,
            status=interview.status,
            feedback_count=feedback_count
        ))
    
    return InterviewerWorkload(
        interviewer_id=interviewer_id,
        interviewer_name=interviewer.UserName or "N/A",
        interviewer_email=interviewer.UserEmail,
        total_panels=total_panels,
        total_interviews=total_interviews,
        scheduled_interviews=scheduled_interviews,
        completed_interviews=completed_interviews,
        feedback_submitted=feedback_submitted,
        upcoming_interviews=upcoming_details
    )


@router.get(
    "/hm-review/my-candidates", response_model=HMCandidateReviewListResponse,
    dependencies=[Depends(get_current_user)],
    summary="S-102/HRMS-P207 -- the caller's own hiring-manager candidate review list: profile + all interview feedback per candidate",
)
def get_my_hiring_manager_candidate_review(
    db: Session = Depends(get_db),
    user=Depends(get_current_internal_user),
):
    """
    Real fix, 2026-08-05 -- this route used to take hiring_manager_id as
    a client-supplied path parameter, gated only by "any internal user
    is logged in," with no check that the caller WAS that hiring
    manager. Any authenticated internal user could view any OTHER
    hiring manager's full candidate review + interview feedback by
    guessing/enumerating a UserID -- a real IDOR, not just a UX
    inconvenience with the frontend's old "enter Hiring Manager User
    ID" text field. Fixed the same way employee self-service resolves
    "my" data: derive from the authenticated caller, never trust a
    client-supplied identity.

    Wires app.schemas.interview's HMCandidateReviewListResponse and its
    nested schemas -- already fully defined, imported here. See
    interview_sequencing_service.get_hm_candidate_review_list()'s own
    docstring for what's deliberately not derived here (a "Must Hire"
    tier with no defined threshold; the "must view all feedback before
    approving" BR, which belongs to the existing, separate PUT
    /status/{candidate_id} approval endpoint, not this read-only list).
    """
    result = get_hm_candidate_review_list(db, user)
    return HMCandidateReviewListResponse(**result)
