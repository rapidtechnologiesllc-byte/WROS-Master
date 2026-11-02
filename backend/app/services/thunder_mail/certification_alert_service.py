"""Certification-expiry alerts forwarded to the mailbox (CEO 2026-11-02: JobDiva's "List of expiring
Licenses and Certifications" for current employees).

Read by rules, no model: the alert's table (Candidate | License/Certification | State | Country |
License/Certification # | Expiry Date) is read from the email's HTML. Each row is matched to an
employee by name (first and last name; middle names ignored) and recorded as that employee's
certificate (employee_certification_service's one record of who holds what): the expiry date and
certificate number are set, the catalog entry is created when the name is new. A renewal task goes
to the employee's reporting manager (else whoever forwarded the alert), the same open task the daily
expiry monitor (certification_expiry_monitor) uses, so the two never duplicate it.
Rows that match no employee are listed on one task for the forwarder; nothing is dropped.
"""
import logging
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.certification import Certification, EmployeeCertification
from app.models.employee import Employee
from app.models.user import Users

logger = logging.getLogger(__name__)

ALERT_PATTERN = re.compile(r"expiring licen[cs]es and certifications|licen[cs]es/certifications that are "
                           r"(already )?expired", re.I)
DATE_PATTERN = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")


def is_certification_alert(subject: str, text: str) -> bool:
    return bool(ALERT_PATTERN.search(f"{subject or ''}\n{text or ''}"))


class _Tables(HTMLParser):
    """Every table row as a list of cell texts."""

    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_alert(html: str) -> List[Dict]:
    """[{person, certification, number, expires}] from the alert's table (dates are DD/MM/YYYY)."""
    parser = _Tables()
    parser.feed(html or "")
    found, columns = [], None
    for cells in parser.rows:
        lowered = [c.lower() for c in cells]
        if "candidate" in lowered and any("expiry" in c for c in lowered):
            columns = {"person": lowered.index("candidate"),
                       "certification": next(i for i, c in enumerate(lowered) if c.startswith("license/certification")
                                             and "#" not in c),
                       "number": next((i for i, c in enumerate(lowered) if "#" in c), None),
                       "expires": next(i for i, c in enumerate(lowered) if "expiry" in c)}
            continue
        if columns is None or len(cells) <= columns["expires"]:
            continue
        date = DATE_PATTERN.match(cells[columns["expires"]])
        if not date or not cells[columns["person"]]:
            continue
        day, month, year = (int(g) for g in date.groups())
        found.append({"person": cells[columns["person"]], "certification": cells[columns["certification"]],
                      "number": cells[columns["number"]] if columns["number"] is not None else None,
                      "expires": datetime(year, month, day)})
    return found


def _employee(db: Session, tenant_id: Optional[int], person: str) -> Optional[Employee]:
    words = person.split()
    if len(words) < 2:
        return None
    matches = db.query(Employee).filter(func.lower(Employee.first_name) == words[0].lower(),
                                        func.lower(Employee.last_name) == words[-1].lower())
    if tenant_id is not None:
        matches = matches.filter(Employee.tenant_id == tenant_id)
    matches = matches.all()
    return matches[0] if len(matches) == 1 else None  # two people with that name: a person decides


def _catalog(db: Session, tenant_id: Optional[int], name: str) -> Certification:
    cert = db.query(Certification).filter(func.lower(Certification.cert_name) == name.lower(),
                                          Certification.tenant_id == tenant_id).first()
    if cert is None:
        code = "ALERT-" + re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:60] + f"-T{tenant_id or 0}"
        cert = Certification(tenant_id=tenant_id, cert_name=name, cert_code=code, validity_months=None,
                             description="Added from a certification-expiry alert")
        db.add(cert)
        db.flush()
    return cert


def record_alert(db: Session, rows: List[Dict], *, tenant_id: Optional[int], forwarder: Users,
                 received: Optional[datetime]) -> Dict:
    """Record each row on its employee and plan the renewal; list unmatched rows. Commits."""
    from app.services.activity_timeline_service import write_timeline_entry
    from app.services.certification_expiry_monitor import renewal_task
    from app.services.task_service import create_task

    now = datetime.utcnow()
    recorded, unmatched, task_ids = [], [], []
    for item in rows:
        employee = _employee(db, tenant_id, item["person"])
        if employee is None:
            unmatched.append(item)
            continue
        cert = _catalog(db, tenant_id, item["certification"])
        record = db.query(EmployeeCertification).filter_by(employee_id=employee.id, certification_id=cert.id).first()
        if record is None:
            record = EmployeeCertification(tenant_id=tenant_id, employee_id=employee.id, certification_id=cert.id,
                                           earned_date=min(received or now, item["expires"]))
            db.add(record)
        record.expires_date, record.cert_number = item["expires"], item["number"] or record.cert_number
        record.status = "Expired" if item["expires"] < now else "Active"
        db.flush()
        name = f"{employee.first_name} {employee.last_name}"
        write_timeline_entry(db, entity_type="employee", entity_id=employee.id, action="certification_expiry",
                             tenant_id=tenant_id, actor_id=forwarder.UserID, actor_type="USER",
                             description=f"{item['certification']} expires {item['expires']:%d %b %Y}"
                                         + (f" (certificate {item['number']})" if item["number"] else "")
                                         + " -- from a certification-expiry alert.")
        task = renewal_task(db, employee, item["certification"], item["expires"], item["number"],
                            tenant_id=tenant_id, owner_id=employee.reporting_manager_user_id or forwarder.UserID,
                            created_by=forwarder.UserID)
        recorded.append({"employee_id": employee.id, "certification": item["certification"],
                         "expires": item["expires"].date().isoformat()})
        task_ids.append(task.id)
    if unmatched:
        lines = "\n".join(f"- {u['person']}: {u['certification']} expires {u['expires']:%d %b %Y}" for u in unmatched)
        task = create_task(db, title=f"Certification alert: {len(unmatched)} person(s) not matched to an employee",
                           description="These rows match no employee (or more than one with that name). Add the "
                                       f"certificate on the right profile:\n{lines}",
                           priority="MEDIUM", tenant_id=tenant_id, assigned_to_user_id=forwarder.UserID,
                           created_by_user_id=forwarder.UserID, due_date=now, category="CERTIFICATION")
        task_ids.append(task.id)
    db.commit()
    logger.info(f"[CertAlert] {len(recorded)} certificate(s) recorded, {len(unmatched)} unmatched")
    return {"recorded": recorded, "unmatched": [u["person"] for u in unmatched], "task_ids": task_ids}
