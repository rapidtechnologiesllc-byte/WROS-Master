"""
EPIC-16 Timesheet Nag Cascade. Throwaway SQLite -- never the real database.
"""
import os
import tempfile
import logging
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet
from app.models.timesheet_nag import TimesheetNagLog
from app.models.user import Users
from app.services.timesheet_nag_service import scan_missing_timesheets, trigger_timesheet_nag
import app.models  # noqa: F401

@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def world(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    manager_user = Users(UserID="U-MGR", UserRole="BU Head", UserEmail="manager@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add(manager_user)
    db_session.commit()

    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Dev", email="sam@blitzenx.com",
        joining_date=date(2024, 1, 1), reporting_manager_user_id="U-MGR",
    )
    db_session.add(employee)
    db_session.commit()

    client = Client(tenant_id=tenant.id, company_name="Builders Insurance")
    db_session.add(client)
    db_session.commit()

    demand = Demand(
        tenant_id=tenant.id, client_id=client.id, job_title="Dev", required_skills="[]",
        min_experience_years=3, work_location="REMOTE", headcount=1, positions_filled=1, status="FILLED",
    )
    db_session.add(demand)
    db_session.commit()

    allocation = EmployeeAllocation(
        tenant_id=tenant.id, employee_id=employee.id, demand_id=demand.id, client_id=client.id, status="ACTIVE",
    )
    db_session.add(allocation)
    db_session.commit()

    return {"tenant": tenant, "employee": employee, "manager_user": manager_user, "allocation": allocation}

def test_scan_missing_timesheets_finds_employee_with_no_submission(db_session, world):
    week = date(2026, 8, 3)
    missing = scan_missing_timesheets(db_session, week_starting_date=week)
    assert len(missing) == 1
    assert missing[0].id == world["employee"].id

def test_scan_missing_timesheets_excludes_submitted(db_session, world):
    week = date(2026, 8, 3)
    db_session.add(Timesheet(
        tenant_id=world["tenant"].id, employee_id=world["employee"].id, allocation_id=world["allocation"].id,
        week_starting_date=week, status="SUBMITTED",
    ))
    db_session.commit()

    missing = scan_missing_timesheets(db_session, week_starting_date=week)
    assert missing == []

def test_first_nag_notifies_employee_at_level_1(db_session, world):
    week = date(2026, 8, 3)
    log = trigger_timesheet_nag(db_session, world["employee"], week_starting_date=week, tenant_id=world["tenant"].id)

    assert log is not None
    assert log.escalation_level == 1

def test_nag_escalates_to_manager_after_escalation_days(db_session, world):
    week = date(2026, 8, 3)
    trigger_timesheet_nag(db_session, world["employee"], week_starting_date=week, escalation_days=3, tenant_id=world["tenant"].id)

    later = datetime.utcnow() + timedelta(days=4)
    log = trigger_timesheet_nag(db_session, world["employee"], week_starting_date=week, escalation_days=3, now=later, tenant_id=world["tenant"].id)

    assert log.escalation_level == 2

def test_nag_does_not_escalate_before_escalation_days(db_session, world):
    week = date(2026, 8, 3)
    trigger_timesheet_nag(db_session, world["employee"], week_starting_date=week, escalation_days=3, tenant_id=world["tenant"].id)

    soon = datetime.utcnow() + timedelta(days=1)
    log = trigger_timesheet_nag(db_session, world["employee"], week_starting_date=week, escalation_days=3, now=soon, tenant_id=world["tenant"].id)

    assert log.escalation_level == 1

def test_nag_resolves_once_timesheet_submitted(db_session, world):
    week = date(2026, 8, 3)
    trigger_timesheet_nag(db_session, world["employee"], week_starting_date=week, tenant_id=world["tenant"].id)

    db_session.add(Timesheet(
        tenant_id=world["tenant"].id, employee_id=world["employee"].id, allocation_id=world["allocation"].id,
        week_starting_date=week, status="SUBMITTED",
    ))
    db_session.commit()

    result = trigger_timesheet_nag(db_session, world["employee"], week_starting_date=week, tenant_id=world["tenant"].id)
    assert result is None

    log = db_session.query(TimesheetNagLog).filter(
        TimesheetNagLog.employee_id == world["employee"].id, TimesheetNagLog.week_starting_date == week,
    ).first()
    assert log.resolved is True

def test_nag_idempotent_unique_constraint_per_employee_week(db_session, world):
    week = date(2026, 8, 3)
    trigger_timesheet_nag(db_session, world["employee"], week_starting_date=week, tenant_id=world["tenant"].id)
    trigger_timesheet_nag(db_session, world["employee"], week_starting_date=week, tenant_id=world["tenant"].id)

    count = db_session.query(TimesheetNagLog).filter(
        TimesheetNagLog.employee_id == world["employee"].id, TimesheetNagLog.week_starting_date == week,
    ).count()
    assert count == 1
