"""
Executive Signal & Culture Agent -- quarterly feedback cycle,
recognition draft-and-approve, dissatisfaction triage.

Advisory-only throughout, per the redesigned CEO-agent decision
([[wros_ceo_agent_backlog]], 2026-08-04):
- Recognition messages are DRAFTED, never auto-sent -- approve_and_send_recognition()
  is the one function that ever actually sends one, and it requires an
  explicit approved_by (Avinash, in practice) every time.
- Concern triage resolves genuinely simple stuff itself (a small,
  real FAQ set) and creates a real Task (S-434) for anything else --
  never pretends to be Avinash, never resolves something real on its
  own authority.
- Feedback cycle summarization surfaces flagged responses for Avinash
  to act on (via a real Task), it doesn't act on any of them itself.
"""
import re
from datetime import date, datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.executive_signal import (
    EmployeeConcernIntake, EmployeeFeedbackCycle, EmployeeFeedbackResponse, RecognitionMessageDraft,
)

NEGATIVE_KEYWORDS = (
    "unhappy", "quit", "leaving", "toxic", "burnout", "burned out", "underpaid",
    "overworked", "hate", "miserable", "disrespect", "harassment", "unsafe",
)

RECOGNITION_TEMPLATES = {
    "BIRTHDAY": "Happy Birthday, {name}! Wishing you a fantastic year ahead. Thank you for everything you bring to BlitzenX.",
    "WORK_ANNIVERSARY": "Happy work anniversary, {name}! Thank you for {years} year(s) with BlitzenX -- your contributions genuinely matter.",
    "RECOGNITION": "Just wanted to say -- great work, {name}. It hasn't gone unnoticed.",
}

FAQ_RESOLUTIONS = {
    "pto": "You can view and request PTO from the Employee Portal under Time Off. If your request isn't showing up, check with your reporting manager first.",
    "benefits": "Benefits enrollment details are in your onboarding documents. For specific plan questions, HR can pull up your exact coverage.",
    "payroll": "Payroll runs on the standard BlitzenX cycle. If a specific payment looks wrong, this needs a real look -- not something to guess an answer to.",
}


# ── Quarterly feedback cycle ──────────────────────────────────────────

def start_quarterly_cycle(db: Session, quarter_label: str, *, tenant_id=None) -> EmployeeFeedbackCycle:
    cycle = EmployeeFeedbackCycle(quarter_label=quarter_label, tenant_id=tenant_id, status="OPEN")
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def _flag_response(response_text: str) -> bool:
    """Real, honest v1: a small negative-keyword heuristic, not an LLM
    sentiment call -- this fires unattended across every response in a
    cycle, so a deterministic, reviewable rule is safer than a fresh
    LLM judgment call per response. Flags for human review, never acts
    on its own conclusion."""
    text = (response_text or "").lower()
    return any(kw in text for kw in NEGATIVE_KEYWORDS)


def submit_feedback(db: Session, cycle: EmployeeFeedbackCycle, employee: Employee, response_text: str) -> EmployeeFeedbackResponse:
    response = EmployeeFeedbackResponse(
        cycle_id=cycle.id, employee_id=employee.id, response_text=response_text,
        is_flagged=_flag_response(response_text),
    )
    db.add(response)
    db.commit()
    db.refresh(response)
    return response


def close_cycle_and_summarize(db: Session, cycle: EmployeeFeedbackCycle, *, closed_by: Optional[str] = None) -> Dict:
    """Closes the cycle and routes the summary + any flagged concerns to
    Avinash as a real Task -- never resolves anything itself."""
    from app.services.task_service import create_task

    responses = db.query(EmployeeFeedbackResponse).filter(EmployeeFeedbackResponse.cycle_id == cycle.id).all()
    flagged = [r for r in responses if r.is_flagged]

    cycle.status = "CLOSED"
    cycle.closed_at = datetime.utcnow()
    db.add(cycle)

    summary = {
        "cycle_id": cycle.id, "quarter_label": cycle.quarter_label,
        "response_count": len(responses), "flagged_count": len(flagged),
        "flagged_employee_ids": [r.employee_id for r in flagged],
    }

    review_task = create_task(
        db,
        title=f"Review {cycle.quarter_label} feedback cycle summary",
        description=(
            f"{len(responses)} response(s), {len(flagged)} flagged for a real look. "
            f"Flagged employee IDs: {', '.join(summary['flagged_employee_ids']) or 'none'}."
        ),
        priority="HIGH" if flagged else "MEDIUM",
        created_by_user_id=closed_by,
    )
    summary["review_task_id"] = review_task.id

    db.commit()
    return summary


# ── Recognition draft-and-approve ─────────────────────────────────────

def generate_birthday_drafts(db: Session, *, today: Optional[date] = None) -> List[RecognitionMessageDraft]:
    today = today or date.today()
    employees = db.query(Employee).filter(Employee.status != "EXITED").all()

    drafts = []
    for employee in employees:
        if not employee.date_of_birth:
            continue
        if (employee.date_of_birth.month, employee.date_of_birth.day) != (today.month, today.day):
            continue

        existing = db.query(RecognitionMessageDraft).filter(
            RecognitionMessageDraft.employee_id == employee.id, RecognitionMessageDraft.occasion == "BIRTHDAY",
            RecognitionMessageDraft.created_at >= datetime(today.year, today.month, today.day),
        ).first()
        if existing:
            continue  # idempotent -- already drafted today

        name = employee.first_name or "there"
        draft = RecognitionMessageDraft(
            employee_id=employee.id, occasion="BIRTHDAY",
            draft_text=RECOGNITION_TEMPLATES["BIRTHDAY"].format(name=name),
        )
        db.add(draft)
        drafts.append(draft)

    db.commit()
    return drafts


def approve_and_send_recognition(db: Session, draft: RecognitionMessageDraft, *, approved_by: str) -> RecognitionMessageDraft:
    """The one function that ever actually sends a recognition message
    -- requires an explicit human approver every time, sent genuinely
    signed as them, never staged as spontaneously hand-written when it
    wasn't."""
    from app.services.notification_service import send_notification
    from app.models.user import Users

    if draft.status != "DRAFT":
        raise ValueError(f"Recognition draft {draft.id} is already {draft.status!r} -- cannot re-send.")

    employee = db.query(Employee).filter(Employee.id == draft.employee_id).first()
    recipient = db.query(Users).filter(Users.UserID == employee.wros_user_id).first() if employee and employee.wros_user_id else None

    draft.status = "APPROVED"
    draft.approved_by = approved_by
    if recipient:
        send_notification(
            db, calling_context_tenant_id=recipient.tenant_id, recipient=recipient,
            priority_tier="P2", message=draft.draft_text,
        )
        draft.status = "SENT"
        draft.sent_at = datetime.utcnow()

    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def reject_recognition(db: Session, draft: RecognitionMessageDraft) -> RecognitionMessageDraft:
    draft.status = "REJECTED"
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


# ── Dissatisfaction triage ────────────────────────────────────────────

def _match_faq(message_text: str) -> Optional[str]:
    text = (message_text or "").lower()
    for keyword, resolution in FAQ_RESOLUTIONS.items():
        if keyword in text:
            return resolution
    return None


def submit_concern(db: Session, employee: Employee, message_text: str) -> EmployeeConcernIntake:
    intake = EmployeeConcernIntake(employee_id=employee.id, message_text=message_text)
    db.add(intake)
    db.flush()
    _triage(db, intake)
    db.commit()
    db.refresh(intake)
    return intake


def _triage(db: Session, intake: EmployeeConcernIntake) -> EmployeeConcernIntake:
    resolution = _match_faq(intake.message_text)
    if resolution:
        intake.category = "RESOLVED"
        intake.resolution_text = resolution
    else:
        from app.services.task_service import create_task

        employee = db.query(Employee).filter(Employee.id == intake.employee_id).first()
        task = create_task(
            db,
            title=f"Book time with {employee.first_name if employee else intake.employee_id} -- real concern raised",
            description=intake.message_text,
            priority="HIGH",
        )
        intake.category = "ESCALATED"
        intake.created_task_id = task.id
    db.add(intake)
    return intake
