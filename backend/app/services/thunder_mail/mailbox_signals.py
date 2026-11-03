"""What a person's own mailbox says (CEO 2026-11-03: "we need to read and process every email to find
new jobs, new candidate, client updates and escalations").

Rules first (production has no model key; prod_no_ai_keys_rules_first): every email in a connected
person's Outlook is read once (mail_poll_service.poll_connected_mailboxes) and goes to exactly one place:
- a reply in one of our candidate threads: Thunder;
- an email to or from a client's people: the client's History, and
    * escalation words -> a HIGH task for the client's owner / account manager (else the reader),
    * a request to hire -> a task to create the job (jobs are not opened from an email by
      themselves: a new job emails matching candidates, and a misread email must not do that);
- an employee's email with escalation words: a HIGH task for their reporting manager;
- anything else that is not bulk or automatic: the mailbox intake (forward_intake_service), as a
  forwarded email would be -- a new candidate, candidate news, a note on an employee; an email it
  cannot tie to anyone is set aside quietly (never a task: it is the person's own mail).
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import Users

logger = logging.getLogger(__name__)

ESCALATION_PATTERN = re.compile(
    r"\b(escalat\w*|complain\w*|complaint|unhappy|not happy|dissatisf\w*|not satisfied|disappoint\w*|"
    r"unacceptable|serious concern|poor performance|underperform\w*|replace (the |this )?(consultant|resource)|"
    r"terminate (the |this |our )?(contract|engagement|resource)|end the engagement)\b",
    re.IGNORECASE,
)
HIRE_PATTERN = re.compile(
    r"\b(job description|requirement for|new requirement|opening for|open position|need (a|an|\d+) \w+|"
    r"looking for (a|an|\d+) \w+|hiring for|headcount|new role|additional resource|backfill)\b",
    re.IGNORECASE,
)
DEDUPE_WINDOW = timedelta(days=2)


def is_bulk(headers: Dict[str, str]) -> bool:
    """A newsletter or mailing list (never anyone's business with us)."""
    return bool(headers.get("list-unsubscribe") or headers.get("list-id"))


def _text(message: Dict) -> str:
    return f"{message.get('subject') or ''}\n{(message.get('uniqueBody') or {}).get('content') or ''}"


def _task_once(db: Session, *, title: str, description: str, priority: str, tenant_id: Optional[int],
               owner_id: Optional[str], link: Optional[str], category: str) -> Optional[int]:
    """One task per email signal: the same email reaching two people's mailboxes raises it once."""
    from app.services.task_service import create_task

    if db.query(Task.id).filter(Task.title == title, Task.category == category,
                                Task.created_at >= datetime.utcnow() - DEDUPE_WINDOW).first():
        return None
    task = create_task(db, title=title[:300], description=description[:8000], priority=priority, tenant_id=tenant_id,
                       assigned_to_user_id=owner_id, created_by_user_id=None, category=category, link=link,
                       visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if owner_id else "ORG_WIDE",
                       due_date=datetime.utcnow())
    return task.id


def client_signals(db: Session, message: Dict, sender: str, clients: List, reader: Users) -> List[int]:
    """Escalation and hiring requests in a client email (already logged on the client's History)."""
    text, subject = _text(message), (message.get("subject") or "(no subject)").strip()
    snippet = ((message.get("uniqueBody") or {}).get("content") or "").strip()[:1500]
    tasks = []
    for client in clients:
        owner = client.client_owner_user_id or client.account_manager_user_id or reader.UserID
        if ESCALATION_PATTERN.search(text):
            tasks.append(_task_once(
                db, title=f"Escalation from {client.company_name}: {subject}", priority="HIGH",
                description=(f"{sender} wrote to {reader.UserEmail} and it reads as an escalation. Respond today.\n\n"
                             f"{snippet}"),
                tenant_id=client.tenant_id, owner_id=owner, link=f"/clients/{client.id}", category="CLIENT_ESCALATION"))
        if HIRE_PATTERN.search(text):
            tasks.append(_task_once(
                db, title=f"New role request from {client.company_name}: {subject}", priority="HIGH",
                description=(f"{sender} wrote to {reader.UserEmail} about a role to fill. Create the job (Jobs > "
                             f"Create job, client {client.company_name}) so recruiting starts.\n\n{snippet}"),
                tenant_id=client.tenant_id, owner_id=owner, link=f"/clients/{client.id}", category="CLIENT_JOB_REQUEST"))
    return [t for t in tasks if t]


def employee_escalation(db: Session, message: Dict, sender: str, reader: Users) -> Optional[int]:
    """An employee writing with escalation words: their reporting manager hears of it."""
    from app.models.employee import Employee

    if not ESCALATION_PATTERN.search(_text(message)):
        return None
    employee = db.query(Employee).filter(or_(func.lower(Employee.email) == sender,
                                             func.lower(Employee.personal_email) == sender)).first()
    if employee is None:
        return None
    subject = (message.get("subject") or "(no subject)").strip()
    snippet = ((message.get("uniqueBody") or {}).get("content") or "").strip()[:1500]
    return _task_once(
        db, title=f"Escalation from {employee.first_name} {employee.last_name}: {subject}", priority="HIGH",
        description=f"{sender} wrote to {reader.UserEmail} and it reads as an escalation.\n\n{snippet}",
        tenant_id=employee.tenant_id, owner_id=employee.reporting_manager_user_id or reader.UserID,
        link=f"/employees/{employee.id}", category="EMPLOYEE_ESCALATION")
