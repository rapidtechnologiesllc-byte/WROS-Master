"""Certificate expiry monitor (CEO 2026-11-02, after JobDiva's "List of expiring Licenses and
Certifications" email: "HRMS should be doing it similar on its own").

Daily (scheduled job certification_expiry). Every certificate an employee holds with an expiry date
is checked against settings.CERT_EXPIRY_ALERT_DAYS (e.g. 180, 90, 30 days before, and 0 = on the
day). Each threshold alerts once per certificate term (CertificationExpiryAlert): the employee and
their reporting manager are emailed, the employee's timeline notes it, and one renewal task per
term goes to the reporting manager (else the employee). A run that missed days still alerts once,
for the closest threshold crossed. A certificate past its expiry is marked Expired. Certificates
that lapsed more than CERT_EXPIRY_LOOKBACK_DAYS ago, and employees who have left, are not alerted.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.certification import Certification, CertificationExpiryAlert, EmployeeCertification
from app.models.employee import Employee
from app.models.task import Task
from app.models.user import Users

logger = logging.getLogger(__name__)

RENEW_DAYS_BEFORE = 60  # the renewal task is due this long before the certificate expires
URGENT_DAYS = 30  # a renewal this close (or overdue) is HIGH priority
CLOSED_TASK_STATUSES = ("COMPLETED", "CANCELLED")


def alert_thresholds() -> List[int]:
    """settings.CERT_EXPIRY_ALERT_DAYS as whole days (0 = on expiry), largest first. Misconfigured = fail fast."""
    raw = settings.CERT_EXPIRY_ALERT_DAYS or ""
    try:
        days = sorted({int(part) for part in raw.split(",") if part.strip()}, reverse=True)
    except ValueError as exc:
        raise ValueError(f"CERT_EXPIRY_ALERT_DAYS must be a comma list of whole days (e.g. 180,90,30,0), "
                         f"got {raw!r}") from exc
    if not days or any(d < 0 for d in days):
        raise ValueError(f"CERT_EXPIRY_ALERT_DAYS must list days of 0 or more (e.g. 180,90,30,0), got {raw!r}")
    return days


def renewal_task(db: Session, employee: Employee, cert_name: str, expires: datetime, number: Optional[str], *,
                 tenant_id: Optional[int], owner_id: Optional[str], created_by: Optional[str]) -> Task:
    """The one open renewal task for this employee's certificate and expiry date: reused when it
    exists (whoever raised it -- this monitor or a forwarded alert), else created."""
    from app.services.task_service import create_task

    name = f"{employee.first_name} {employee.last_name}".strip()
    title = f"Renew {cert_name} for {name} (expires {expires:%d %b %Y})"[:255]
    existing = db.query(Task).filter(Task.category == "CERTIFICATION", Task.link == f"/employees/{employee.id}",
                                     Task.title == title, Task.status.notin_(CLOSED_TASK_STATUSES)).first()
    if existing is not None:
        return existing
    now = datetime.utcnow()
    return create_task(db, title=title,
                       description=f"{name}'s {cert_name} expires on {expires:%d %b %Y}."
                                   + (f" Certificate {number}." if number else "")
                                   + " Arrange the renewal, then update the certificate on their profile.",
                       priority="HIGH" if expires - now < timedelta(days=URGENT_DAYS) else "MEDIUM",
                       tenant_id=tenant_id, assigned_to_user_id=owner_id, created_by_user_id=created_by,
                       visibility_scope="ASSIGNEE_MANAGER_DEPARTMENT" if owner_id else "ORG_WIDE",
                       due_date=max(now, expires - timedelta(days=RENEW_DAYS_BEFORE)),
                       category="CERTIFICATION", link=f"/employees/{employee.id}")


def _recipients(db: Session, employee: Employee) -> List[Users]:
    """The reporting manager and the employee (whoever has a user account), each once."""
    ids = [i for i in (employee.reporting_manager_user_id, employee.wros_user_id) if i]
    users = {u.UserID: u for u in db.query(Users).filter(Users.UserID.in_(ids)).all()} if ids else {}
    return [users[i] for i in dict.fromkeys(ids) if i in users]


def _when(days_left: int, expires: datetime) -> str:
    if days_left < 0:
        return f"expired on {expires:%d %b %Y}"
    if days_left == 0:
        return "expires today"
    return f"expires on {expires:%d %b %Y} ({days_left} days)"


def _alert(db: Session, record: EmployeeCertification, employee: Employee, cert: Certification,
           crossed: List[int], days_left: int) -> Optional[int]:
    """Claim the crossed thresholds, then the task, timeline entry and emails. Returns the task id
    (None when another run claimed them first). The caller commits."""
    from app.services.activity_timeline_service import write_timeline_entry
    from app.services.staff_mail_service import queue_staff_email

    try:
        # claim first (the unique key): a concurrent run cannot raise the same alert
        with db.begin_nested():
            marks = [CertificationExpiryAlert(tenant_id=record.tenant_id, employee_certification_id=record.id,
                                              expires_date=record.expires_date, threshold_days=t) for t in crossed]
            db.add_all(marks)
            db.flush()
    except IntegrityError:
        logger.info(f"[CertExpiry] certificate {record.id}: alert already raised")
        return None
    expires, name = record.expires_date, f"{employee.first_name} {employee.last_name}".strip()
    if days_left < 0 and record.status == "Active":
        record.status = "Expired"
    task = renewal_task(db, employee, cert.cert_name, expires, record.cert_number, tenant_id=record.tenant_id,
                        owner_id=employee.reporting_manager_user_id or employee.wros_user_id, created_by=None)
    for mark in marks:
        mark.task_id = task.id
    when = _when(days_left, expires)
    write_timeline_entry(db, entity_type="employee", entity_id=employee.id, action="certification_expiry",
                         tenant_id=record.tenant_id, actor_type="SYSTEM",
                         description=f"{cert.cert_name} {when}"
                                     + (f" (certificate {record.cert_number})" if record.cert_number else "")
                                     + " -- certificate expiry monitor.")
    db.flush()
    recipients = _recipients(db, employee)
    if not recipients:
        logger.warning(f"[CertExpiry] {employee.id}: no reporting manager or user account; task {task.id} is org-wide")
    for user in recipients:
        whose = "Your" if user.UserID == employee.wros_user_id else f"{name}'s"
        queue_staff_email(user, key=f"cert-expiry-{record.id}-{expires:%Y%m%d}-{min(crossed)}-{user.UserID}",
                          subject=f"{cert.cert_name} for {name} {when}"[:200],
                          paragraphs=[f"{whose} {cert.cert_name} {when}."
                                      + (f" Certificate number {record.cert_number}." if record.cert_number else ""),
                                      "Please arrange the renewal and update the certificate on the employee profile "
                                      "once it is renewed."],
                          link_path=f"/employees/{employee.id}", link_label="Open the employee profile")
    return task.id


def run_expiry_monitor(db: Session, today: Optional[date] = None) -> Dict:
    """Daily job. Idempotent per certificate term and threshold; one bad row does not stop the others."""
    today = today or date.today()
    thresholds = alert_thresholds()
    start = datetime.combine(today - timedelta(days=settings.CERT_EXPIRY_LOOKBACK_DAYS), datetime.min.time())
    end = datetime.combine(today + timedelta(days=max(thresholds) + 1), datetime.min.time())
    rows = (db.query(EmployeeCertification, Employee, Certification)
            .join(Employee, Employee.id == EmployeeCertification.employee_id)
            .join(Certification, Certification.id == EmployeeCertification.certification_id)
            .filter(EmployeeCertification.expires_date.isnot(None), EmployeeCertification.expires_date >= start,
                    EmployeeCertification.expires_date < end, EmployeeCertification.status != "Revoked",
                    Employee.status != "EXITED")
            .all())
    result = {"checked": len(rows), "alerted": 0, "failed": 0}
    for record, employee, cert in rows:
        days_left = (record.expires_date.date() - today).days
        done = {t for (t,) in db.query(CertificationExpiryAlert.threshold_days).filter(
            CertificationExpiryAlert.employee_certification_id == record.id,
            CertificationExpiryAlert.expires_date == record.expires_date)}
        crossed = [t for t in thresholds if days_left <= t and t not in done]
        if not crossed:
            continue
        try:
            if _alert(db, record, employee, cert, crossed, days_left) is not None:
                result["alerted"] += 1
            db.commit()
        except Exception as exc:  # one bad row must not stop the others; logged and counted
            db.rollback()
            logger.error(f"[CertExpiry] certificate {record.id} failed: {exc}", exc_info=True)
            result["failed"] += 1
    logger.info(f"[CertExpiry] {result}")
    return result
