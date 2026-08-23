"""
Ticket SLA breach flagging.

Deliberately NOT a second scheduled job -- Task.due_date is kept in
sync with whichever SLA deadline (response, then resolution) is
currently live (see ticket_service.create_task()/record_first_response()),
so the existing hourly task_escalation_service.escalate_overdue_tasks()
job already detects a ticket SLA breach for free. This module's one
job is to flag WHICH SLA breached, for reporting -- called from
task_escalation_service as each TICKET-type task escalates, not run
as its own separate scan.
"""
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.ticket import TicketDetail


def flag_sla_breach(db: Session, task: Task) -> None:
    if task.task_type != "TICKET":
        return
    detail = db.query(TicketDetail).filter(TicketDetail.task_id == task.id).first()
    if not detail:
        return
    if detail.first_response_at is None:
        detail.response_breached = True
    else:
        detail.resolution_breached = True
    db.add(detail)
