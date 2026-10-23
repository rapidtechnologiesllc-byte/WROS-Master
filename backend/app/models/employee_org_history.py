"""Where an employee sat, day by day: business unit and delivery center (employer company and its
country) -- the cost object their cost is charged to (CEO 2026-10-22: cost object = BU x location).

Effective-dated and written automatically: a new employee gets a row from their joining date, and
every change of Employee.bu_id or Employee.company_id adds a row effective that day (the
before_flush hook below), so no write path can move someone without history. The P&L charges each
day to the row in force that day, so moving an employee never rewrites a past month. Existing
employees are backfilled once from their current values (db_contract data migration)."""
from datetime import date

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, event, func, inspect, select
from sqlalchemy.orm import Session

from app.models.base import Base


class EmployeeOrgHistory(Base):
    __tablename__ = "employee_org_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    employee_id = Column(String(512), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    bu_id = Column(Integer, ForeignKey("business_units.id"), nullable=True, index=True)
    company_id = Column(String(512), ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    country = Column(String(2), nullable=True, index=True)  # ISO 3166-1 alpha-2 of the delivery center
    effective_from = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


def country_of_company(session: Session, company_id) -> str:
    """ISO country of a delivery center (Location.country is free text: "India", "IN", ...)."""
    if not company_id:
        return None
    from app.models.location import Location
    from app.services.employment_type_policy import country_code

    with session.no_autoflush:
        company = session.get(Location, company_id)
    return country_code(company.country) if company is not None and company.country else None


@event.listens_for(Session, "before_flush")
def _record_org_changes(session: Session, flush_context, instances) -> None:
    from app.models.employee import Employee

    for obj in list(session.new):
        if isinstance(obj, Employee):
            if obj.id is None:
                from app.models.employee import _new_uuid

                obj.id = _new_uuid()
            session.add(EmployeeOrgHistory(
                tenant_id=obj.tenant_id, employee_id=obj.id, bu_id=obj.bu_id, company_id=obj.company_id,
                country=country_of_company(session, obj.company_id), effective_from=obj.joining_date or date.today()))
    for obj in list(session.dirty):
        if not isinstance(obj, Employee):
            continue
        state = inspect(obj)
        if not (state.attrs.bu_id.history.has_changes() or state.attrs.company_id.history.has_changes()):
            continue
        today = date.today()
        effective = max(today, obj.joining_date) if obj.joining_date else today
        with session.no_autoflush:
            has_history = session.query(EmployeeOrgHistory.id).filter(
                EmployeeOrgHistory.employee_id == obj.id).first() is not None
        if not has_history and obj.joining_date and obj.joining_date < effective:
            # first move of someone with no history yet: keep where they sat until today (the row
            # as stored, before this flush writes the change)
            with session.no_autoflush:
                stored = session.execute(select(Employee.bu_id, Employee.company_id)
                                         .where(Employee.id == obj.id)).first()
            old_bu, old_company = stored if stored else (obj.bu_id, obj.company_id)
            session.add(EmployeeOrgHistory(
                tenant_id=obj.tenant_id, employee_id=obj.id, bu_id=old_bu, company_id=old_company,
                country=country_of_company(session, old_company), effective_from=obj.joining_date))
        session.add(EmployeeOrgHistory(
            tenant_id=obj.tenant_id, employee_id=obj.id, bu_id=obj.bu_id, company_id=obj.company_id,
            country=country_of_company(session, obj.company_id), effective_from=effective))
