"""Whether an employee may go to a client (CEO 2026-10-14). One rule set, checked at every step
that puts someone in front of a client: client submission, PLACED, direct allocation, Core Pull.

Two delivery models: Staff Augmentation (SPECIALITY) and Core (direct client, CORE). Every new
hire proves themselves on Staff Aug first, then is Core-certified and moved to a Core client.

- Buddy Program GRADUATED, for both models (no exception for employees from before the
  hiring pipeline);
- no OPEN escalation (app.models.employee_escalation);
- Core-certified when the job is Core.

For a client submission the employee must also be free (allocation_blockers): an active Core
allocation holds them until they are released, and an active Staff Aug allocation holds them
from another Staff Aug job but not from a Core one (moving Staff Aug people to Core is the
goal). An allocation ending within ROLL_OFF_WINDOW_DAYS is rolling off and holds no one.

Each blocker is {"error", "message", "violation_type"}: the shape create_submission() returns
to the recruiter and logs to SubmissionViolation."""
import logging
from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.employee_escalation import EmployeeEscalation

logger = logging.getLogger(__name__)

DEPLOYABLE_BUDDY_STATUS = "GRADUATED"
CORE = "CORE"
DELIVERY_LINE_LABELS = {"CORE": "Core (direct client)", "SPECIALITY": "Staff Aug"}


class EmployeeNotDeployable(Exception):
    """The employee may not be deployed at this client; carries every blocker, not just the first."""

    def __init__(self, blockers: List[dict]):
        self.blockers = blockers
        super().__init__("; ".join(b["message"] for b in blockers))


def _blocker(error: str, message: str) -> dict:
    return {"error": error, "message": message, "violation_type": error}


def delivery_line(db: Session, *, project_id: Optional[str], client_id: Optional[str]) -> Optional[str]:
    """CORE or SPECIALITY: the project's delivery engine when there is a project, else the
    client's line type. None when neither says (a legacy client with no line type)."""
    if project_id:
        from app.models.project import Project

        project = db.query(Project).filter(Project.id == project_id).first()
        if project is not None and project.delivery_engine:
            return project.delivery_engine
    if client_id:
        client = db.query(Client).filter(Client.id == client_id).first()
        if client is not None:
            return client.line_type
    return None


def job_line(db: Session, job) -> Optional[str]:
    return delivery_line(db, project_id=getattr(job, "project_id", None), client_id=job.client_id)


def deployment_blockers(db: Session, employee: Employee, job=None) -> List[dict]:
    """Buddy, escalation and (for a Core job) Core certification. Job-independent when job is None."""
    blockers = []
    if employee.buddy_program_status != DEPLOYABLE_BUDDY_STATUS:
        blockers.append(_blocker(
            "BUDDY_NOT_GRADUATED",
            f"Buddy Program is {employee.buddy_program_status.replace('_', ' ').lower()}; "
            "it must be graduated before any client deployment.",
        ))
    open_escalations = db.query(EmployeeEscalation).filter(
        EmployeeEscalation.employee_id == employee.id, EmployeeEscalation.status == "OPEN",
    ).count()
    if open_escalations:
        blockers.append(_blocker(
            "OPEN_ESCALATION",
            f"{open_escalations} open escalation(s) on this employee; a Director must resolve them first.",
        ))
    if job is not None and job_line(db, job) == CORE and not employee.core_certified:
        blockers.append(_blocker(
            "CORE_CERTIFICATION_REQUIRED",
            "This is a Core (direct client) job; the employee is not Core-certified.",
        ))
    return blockers


def is_rolling_off(allocation: EmployeeAllocation, today: Optional[date] = None) -> bool:
    today = today or date.today()
    return allocation.end_date is not None and allocation.end_date <= today + timedelta(days=settings.ROLL_OFF_WINDOW_DAYS)


def allocation_blockers(db: Session, employee: Employee, job=None) -> List[dict]:
    """Active allocations that hold the employee from this job (see the module docstring)."""
    target = job_line(db, job) if job is not None else None
    held = []
    active = db.query(EmployeeAllocation).filter(
        EmployeeAllocation.employee_id == employee.id, EmployeeAllocation.status == "ACTIVE",
    ).all()
    for allocation in active:
        if is_rolling_off(allocation):
            continue
        line = delivery_line(db, project_id=allocation.project_id, client_id=allocation.client_id)
        if line == CORE:
            held.append("a Core project (until released)")
        elif job is not None and target != CORE:
            held.append("a Staff Aug project (only a move to Core is allowed)")
    if not held:
        return []
    return [_blocker("NOT_ON_BENCH", f"Allocated to {', '.join(sorted(set(held)))}; rolling off means an "
                                     f"end date within {settings.ROLL_OFF_WINDOW_DAYS} days.")]


def submission_blockers(db: Session, employee: Employee, job=None) -> List[dict]:
    """Everything employee-side that stops a client submission to this job (any job when None)."""
    return deployment_blockers(db, employee, job) + allocation_blockers(db, employee, job)


def assert_deployable(db: Session, employee: Employee, job) -> None:
    blockers = deployment_blockers(db, employee, job)
    if blockers:
        logger.info(f"[Deployment] {employee.id} blocked at job {job.id}: {[b['error'] for b in blockers]}")
        raise EmployeeNotDeployable(blockers)
