"""Client onboarding: between the client selecting a candidate (submission OFFER_EXTENDED)
and the employee starting on the client's project.

start(db, submission)          -> PENDING row, proposed start = the job's required start date,
                                  and a task for the account manager to get the date confirmed
confirm_start(db, row, date)   -> START_CONFIRMED (the client confirmed the start date)
run_start_date_job(db)         -> daily: on the confirmed date, the submission becomes PLACED,
                                  the employee is allocated from that date, row STARTED
A submission can't be PLACED until its client onboarding is START_CONFIRMED.
"""
import logging
from datetime import date, datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.client_onboarding import ClientOnboarding
from app.models.employee import Employee
from app.models.submission import Submission

logger = logging.getLogger(__name__)


class ClientOnboardingError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def for_submission(db: Session, submission_id: str) -> Optional[ClientOnboarding]:
    return db.query(ClientOnboarding).filter(ClientOnboarding.submission_id == submission_id).first()


def start(db: Session, submission: Submission) -> ClientOnboarding:
    """Idempotent; flushes, the caller commits."""
    from app.models.user import Jobs
    from app.services.task_service import create_task

    row = for_submission(db, submission.id)
    if row is not None:
        return row
    demand = db.query(Jobs).filter(Jobs.jobID == submission.demand_id).first()
    employee = db.query(Employee).filter(Employee.candidate_id == submission.candidate_id,
                                         Employee.status != "EXITED").first()
    row = ClientOnboarding(tenant_id=submission.tenant_id, submission_id=submission.id,
                           candidate_id=submission.candidate_id, employee_id=employee.id if employee else None,
                           demand_id=submission.demand_id, client_id=submission.client_id, status="PENDING",
                           proposed_start_date=getattr(demand, "required_start_date", None))
    db.add(row)
    db.flush()
    owner = getattr(demand, "hiringManagerID", None) or submission.submitted_by_user_id
    task = create_task(db, title=f"Confirm client start date: {submission.candidate_id}",
                       description=(f"The client selected this candidate for '{getattr(demand, 'jobTitle', '')}'. "
                                    f"Complete the client's onboarding and record the start date they confirm "
                                    f"(client onboarding #{row.id}; proposed {row.proposed_start_date})."),
                       priority="HIGH", tenant_id=submission.tenant_id, category="CLIENT_ONBOARDING",
                       assigned_to_user_id=owner,
                       visibility_scope="ORG_WIDE" if not owner else "ASSIGNEE_MANAGER_DEPARTMENT")
    task.candidate_id = submission.candidate_id
    db.add(task)
    logger.info(f"[ClientOnboarding] {row.id} started for submission {submission.id}")
    return row


def confirm_start(db: Session, row: ClientOnboarding, start_date: date, confirmed_by: str) -> ClientOnboarding:
    if row.status not in ("PENDING", "START_CONFIRMED"):
        raise ClientOnboardingError(f"Client onboarding is {row.status}.")
    submission = db.query(Submission).filter(Submission.id == row.submission_id).first()
    if submission is None or submission.status != "OFFER_EXTENDED":
        raise ClientOnboardingError("The client's selection is no longer open (submission is not OFFER_EXTENDED).", 409)
    row.status, row.confirmed_start_date = "START_CONFIRMED", start_date
    row.confirmed_by, row.confirmed_at = confirmed_by, datetime.utcnow()
    return row


def placement_start_date(db: Session, submission: Submission) -> date:
    """PLACED needs a confirmed client start date; returns it (raises otherwise)."""
    row = for_submission(db, submission.id)
    if row is None or row.status not in ("START_CONFIRMED", "STARTED") or row.confirmed_start_date is None:
        raise ClientOnboardingError("The client has not confirmed a start date (client onboarding pending).", 409)
    return row.confirmed_start_date


def mark_started(db: Session, submission: Submission) -> None:
    from app.models.employee_allocation import HOLDING_STATUSES, EmployeeAllocation

    row = for_submission(db, submission.id)
    if row is None:
        return
    employee = db.query(Employee).filter(Employee.candidate_id == submission.candidate_id).first()
    allocation = None if employee is None else db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee.id, EmployeeAllocation.demand_id == submission.demand_id,
        EmployeeAllocation.status.in_(HOLDING_STATUSES)).first()
    row.status = "STARTED"
    row.allocation_id = allocation.id if allocation else row.allocation_id
    row.employee_id = employee.id if employee else row.employee_id


def run_start_date_job(db: Session, today: Optional[date] = None) -> Dict:
    """Daily: confirmed start dates that have arrived become placements (allocation from that date)."""
    from app.services.hiring_pipeline_service import notify
    from app.services.submission_service import update_client_response

    today = today or date.today()
    due = db.query(ClientOnboarding).filter(ClientOnboarding.status == "START_CONFIRMED",
                                            ClientOnboarding.confirmed_start_date <= today).all()
    result = {"due": len(due), "placed": 0, "failed": 0}
    for row in due:
        submission = db.query(Submission).filter(Submission.id == row.submission_id).first()
        try:
            update_client_response(db, submission, "PLACED", client_feedback="Started on the confirmed date")
            db.commit()
            notify(submission.candidate_id, "placed", submission.id)
            result["placed"] += 1
        except Exception as exc:
            db.rollback()
            result["failed"] += 1
            logger.error(f"[ClientOnboarding] placing submission {row.submission_id} failed: {exc}", exc_info=True)
    logger.info(f"[ClientOnboarding] start-date job {result}")
    return result
