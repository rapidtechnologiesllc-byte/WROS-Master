"""Certificates an employee holds (EmployeeCertification): the ONE record of who holds which
certificate, earned when, valid until when. Training and certification dashboards
(training_certification_service) count these rows.

Guidewire level (CEO 2026-10-23, one truth): an employee's CURRENT Guidewire level is not typed
in anywhere; it is the highest guidewire_level among the catalog certificates (Certification.
guidewire_level) they hold, Active and not expired. Employee.guidewire_certification_expected
stays a separate field: it is a development target, not a certificate held.
Employee.guidewire_certification_current is retired (the data migration
guidewire_current_level_to_certificates turned every stored level into a certificate record).
"""
import logging
from datetime import date, datetime, time
from typing import Dict, Iterable, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.certification import CERT_STATUS, GUIDEWIRE_CERT_LEVELS, Certification, EmployeeCertification
from app.models.employee import Employee

logger = logging.getLogger(__name__)

EDITABLE_FIELDS = ("earned_date", "expires_date", "cert_number", "issuer", "status")


class EmployeeCertificationError(ValueError):
    """A certificate record the caller sent is not valid; the REST layer answers 400."""


def _as_datetime(value) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def _add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year, month = day.year + month // 12, month % 12 + 1
    import calendar

    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def catalog(db: Session, tenant_id: Optional[int]) -> List[Certification]:
    """The tenant's certificate catalog (plus legacy rows created before tenant_id existed)."""
    query = db.query(Certification)
    if tenant_id is not None:
        query = query.filter(or_(Certification.tenant_id == tenant_id, Certification.tenant_id.is_(None)))
    return query.order_by(Certification.cert_name).all()


def _catalog_entry(db: Session, certification_id: str, tenant_id: Optional[int]) -> Certification:
    cert = db.query(Certification).filter(Certification.id == certification_id).first()
    if cert is None or (tenant_id is not None and cert.tenant_id not in (tenant_id, None)):
        raise EmployeeCertificationError(f"Certification {certification_id!r} is not in the catalog.")
    return cert


def _validate(earned, expires, status) -> None:
    if earned is None:
        raise EmployeeCertificationError("earned_date is required.")
    if expires is not None and expires < earned:
        raise EmployeeCertificationError(f"expires_date {expires.date()} is before earned_date {earned.date()}.")
    if status not in CERT_STATUS:
        raise EmployeeCertificationError(f"status must be one of {list(CERT_STATUS)}, not {status!r}.")


def list_records(db: Session, employee: Employee) -> List[EmployeeCertification]:
    return (db.query(EmployeeCertification).filter(EmployeeCertification.employee_id == employee.id)
            .order_by(EmployeeCertification.earned_date.desc()).all())


def create_record(db: Session, employee: Employee, *, certification_id: str, earned_date,
                  expires_date=None, cert_number: Optional[str] = None, issuer: Optional[str] = None,
                  status: str = "Active") -> EmployeeCertification:
    """Record a certificate the employee holds. Without an expiry date the catalog's validity
    (Certification.validity_months) sets it; a catalog entry with no validity never expires."""
    cert = _catalog_entry(db, certification_id, employee.tenant_id)
    earned = _as_datetime(earned_date)
    if expires_date is None and earned is not None and cert.validity_months:
        expires_date = _add_months(earned.date(), cert.validity_months)
    expires = _as_datetime(expires_date)
    _validate(earned, expires, status)
    duplicate = db.query(EmployeeCertification.id).filter(
        EmployeeCertification.employee_id == employee.id, EmployeeCertification.certification_id == cert.id,
        EmployeeCertification.earned_date == earned,
    ).first()
    if duplicate is not None:
        raise EmployeeCertificationError(f"{cert.cert_name} earned on {earned.date()} is already recorded.")
    record = EmployeeCertification(
        tenant_id=employee.tenant_id, employee_id=employee.id, certification_id=cert.id,
        status=status, earned_date=earned, expires_date=expires,
        cert_number=(cert_number or "").strip() or None, issuer=(issuer or "").strip() or None,
    )
    db.add(record)
    db.flush()
    logger.info(f"[Certification] {employee.id} holds {cert.cert_code} (record {record.id})")
    return record


def update_record(db: Session, record: EmployeeCertification, changes: Dict) -> EmployeeCertification:
    unknown = set(changes) - set(EDITABLE_FIELDS)
    if unknown:
        raise EmployeeCertificationError(f"Cannot edit {sorted(unknown)}; editable: {list(EDITABLE_FIELDS)}.")
    if "earned_date" in changes and changes["earned_date"] is None:
        raise EmployeeCertificationError("earned_date cannot be cleared.")
    earned = _as_datetime(changes.get("earned_date", record.earned_date))
    expires = _as_datetime(changes.get("expires_date", record.expires_date))
    status = changes.get("status", record.status)
    if status is None:
        raise EmployeeCertificationError("status cannot be cleared.")
    _validate(earned, expires, status)
    record.earned_date, record.expires_date, record.status = earned, expires, status
    for field in ("cert_number", "issuer"):
        if field in changes:
            setattr(record, field, (changes[field] or "").strip() or None)
    db.add(record)
    return record


def delete_record(db: Session, record: EmployeeCertification) -> None:
    logger.info(f"[Certification] record {record.id} of {record.employee_id} deleted")
    db.delete(record)


def current_guidewire_levels(db: Session, employee_ids: Iterable[str],
                             now: Optional[datetime] = None) -> Dict[str, Optional[str]]:
    """{employee_id: highest Guidewire level held (Active, not expired) or None}."""
    ids = list({i for i in employee_ids if i})
    if not ids:
        return {}
    now = now or datetime.utcnow()
    rank = {level: i for i, level in enumerate(GUIDEWIRE_CERT_LEVELS)}
    out: Dict[str, Optional[str]] = {i: None for i in ids}
    rows = (db.query(EmployeeCertification.employee_id, Certification.guidewire_level)
            .join(Certification, Certification.id == EmployeeCertification.certification_id)
            .filter(EmployeeCertification.employee_id.in_(ids), EmployeeCertification.status == "Active",
                    Certification.guidewire_level.isnot(None),
                    or_(EmployeeCertification.expires_date.is_(None), EmployeeCertification.expires_date >= now))
            .all())
    for employee_id, level in rows:
        if level in rank and (out[employee_id] is None or rank[level] > rank[out[employee_id]]):
            out[employee_id] = level
    return out
