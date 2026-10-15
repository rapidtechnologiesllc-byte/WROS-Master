"""Training and Certification Dashboard Service.

Every figure is counted from real rows (Employee, EmployeeCertification,
Jobs) and, when business_unit_id is given, scoped to that BU's employees
(Employee.bu_id). No placeholder numbers: an empty BU shows zeros.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.certification import CERTIFICATION_LEVELS, Certification, EmployeeCertification
from app.models.employee import Employee

# Employees who have joined and not left
_WORKING_STATUSES_EXCLUDED = ("PRE_JOINING", "EXITED")
# Job statuses that mean "open for recruitment" (jobs are created "active")
_OPEN_JOB_STATUSES = ("active", "open", "public")


def _in_bus(column, business_unit_id):
    """business_unit_id is one BU id or a collection (a partner's BUs)."""
    if isinstance(business_unit_id, (list, tuple, set, frozenset)):
        return column.in_(list(business_unit_id))
    return column == business_unit_id


def _employee_name(employee: Employee) -> str:
    return " ".join(filter(None, [employee.first_name, employee.last_name]))


def _bu_employees(db: Session, business_unit_id: int = None):
    query = db.query(Employee)
    if business_unit_id:
        query = query.filter(_in_bus(Employee.bu_id, business_unit_id))
    return query


def get_buddy_program_overview(db: Session, business_unit_id: int = None) -> dict:
    """Buddy Program status counts from Employee.buddy_program_status."""
    counts = dict(
        _bu_employees(db, business_unit_id)
        .with_entities(Employee.buddy_program_status, func.count(Employee.id))
        .group_by(Employee.buddy_program_status)
        .all()
    )
    month_start = date.today().replace(day=1)
    completed_this_month = _bu_employees(db, business_unit_id).filter(
        Employee.buddy_program_status == "GRADUATED",
        Employee.buddy_program_graduation_date >= month_start,
    ).count()

    in_progress = counts.get("IN_PROGRESS", 0)
    extended = counts.get("EXTENDED", 0)
    return {
        "total_in_program": in_progress + extended,
        "on_track": in_progress,
        # Extended = did not graduate on schedule
        "at_risk": extended,
        "completed_this_month": completed_this_month,
        "graduated_total": counts.get("GRADUATED", 0),
        "not_started": counts.get("NOT_STARTED", 0),
    }


def _bu_certifications(db: Session, business_unit_id: int = None):
    query = db.query(EmployeeCertification).join(Employee, Employee.id == EmployeeCertification.employee_id)
    if business_unit_id:
        query = query.filter(_in_bus(Employee.bu_id, business_unit_id))
    return query


def get_certification_summary(db: Session, business_unit_id: int = None) -> dict:
    """Active certifications by level, plus expiring (30 days) and expired."""
    now = datetime.utcnow()
    by_level = dict(
        _bu_certifications(db, business_unit_id)
        .join(Certification, Certification.id == EmployeeCertification.certification_id)
        .filter(EmployeeCertification.status == "Active")
        .with_entities(Certification.level, func.count(EmployeeCertification.id))
        .group_by(Certification.level)
        .all()
    )
    level_counts = {level: by_level.get(level, 0) for level in CERTIFICATION_LEVELS}

    expiring_soon = _bu_certifications(db, business_unit_id).filter(
        EmployeeCertification.status == "Active",
        EmployeeCertification.expires_date.between(now, now + timedelta(days=30)),
    ).count()
    expired = _bu_certifications(db, business_unit_id).filter(
        EmployeeCertification.expires_date < now,
    ).count()

    return {
        "by_level": level_counts,
        "total_active": sum(level_counts.values()),
        "expiring_within_30_days": expiring_soon,
        "already_expired": expired,
    }


def get_employee_training_status(db: Session, employee_id: str = None, business_unit_id: int = None) -> list:
    """Certification count and latest certification date per employee."""
    query = db.query(
        Employee,
        func.count(EmployeeCertification.id).label("cert_count"),
        func.max(EmployeeCertification.earned_date).label("last_cert_date"),
    ).outerjoin(
        EmployeeCertification, EmployeeCertification.employee_id == Employee.id
    ).filter(
        Employee.status.notin_(_WORKING_STATUSES_EXCLUDED)
    ).group_by(Employee.id)

    if employee_id:
        query = query.filter(Employee.id == employee_id)
    if business_unit_id:
        query = query.filter(_in_bus(Employee.bu_id, business_unit_id))

    return [
        {
            "employee_id": employee.id,
            "employee_name": _employee_name(employee),
            "certification_count": cert_count or 0,
            "last_certified_date": last_cert_date.isoformat() if last_cert_date else None,
            "next_action": "Review expiring certifications" if cert_count else "Assign certification",
        }
        for employee, cert_count, last_cert_date in query.all()
    ]


def get_training_pipeline_status(db: Session, business_unit_id: int = None) -> dict:
    """Pre-onboarding (offer accepted, not joined) and HTD training track."""
    pre_onboarding = _bu_employees(db, business_unit_id).filter(Employee.status == "PRE_JOINING").count()
    in_htd_track = _bu_employees(db, business_unit_id).filter(
        Employee.htd_track == True,  # noqa: E712
        Employee.htd_phase.notin_(("COMPLETED", "EXITED")),
    ).count()
    return {
        "in_pre_onboarding": pre_onboarding,
        "in_training_modules": in_htd_track,
    }


def get_open_positions(db: Session, business_unit_id: int = None) -> int:
    """Jobs currently open for recruitment in the BU."""
    from app.models.user import Jobs

    query = db.query(func.count(Jobs.jobID)).filter(func.lower(Jobs.jobStatus).in_(_OPEN_JOB_STATUSES))
    if business_unit_id:
        query = query.filter(_in_bus(Jobs.business_unit_id, business_unit_id))
    return query.scalar() or 0


def get_core_certified_employees(db: Session, business_unit_id: int = None) -> list:
    """Core-certified employees: Employee.core_certified, set when their BU Head approves (CEO
    2026-10-14, app.services.core_certification_service). The same flag that gates Core jobs,
    so this list and who can be submitted to a Core client never disagree. Technical
    certificates flagged is_core_certification are tracked separately (get_next_training_steps)."""
    rows = (_bu_employees(db, business_unit_id)
            .filter(Employee.core_certified.is_(True), Employee.status != "EXITED")
            .order_by(Employee.core_certified_date.desc()).all())
    return [
        {
            "name": _employee_name(employee),
            "certification": "Core (BU Head approved)",
            "earned_date": employee.core_certified_date.isoformat() if employee.core_certified_date else None,
        }
        for employee in rows
    ]


def get_next_training_steps(db: Session, employee_id: str = None, business_unit_id: int = None) -> list:
    """Recommended next steps, derived from the real counts above."""
    if employee_id:
        current_cert_ids = [
            row[0] for row in db.query(EmployeeCertification.certification_id).filter(
                EmployeeCertification.employee_id == employee_id,
                EmployeeCertification.status == "Active",
            ).all()
        ]
        next_certs = db.query(Certification).filter(
            ~Certification.id.in_(current_cert_ids),
            Certification.is_core_certification == True,  # noqa: E712
        ).limit(3).all()
        return [
            {
                "action": "Pursue certification",
                "certification": cert.cert_name,
                "level": cert.level,
                "priority": "High",
            }
            for cert in next_certs
        ]

    actions = []
    certs = get_certification_summary(db, business_unit_id)
    if certs["expiring_within_30_days"]:
        actions.append({
            "action": "Review expiring certifications",
            "description": f"{certs['expiring_within_30_days']} certifications expire within 30 days",
            "priority": "High",
        })
    not_started = get_buddy_program_overview(db, business_unit_id)["not_started"]
    if not_started:
        actions.append({
            "action": "Enroll in buddy program",
            "description": f"{not_started} employees have not started the buddy program",
            "priority": "High",
        })
    logger.debug(f"[TrainingDashboard] {len(actions)} next steps for BU {business_unit_id}")
    return actions
