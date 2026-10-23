"""Utilization is recorded every week for every billable employee (CEO 2026-10-23): the
utilization_snapshot job replaces the typed-employee-ID form, and the dashboard flags people
below a configurable target (settings.UTILIZATION_TARGET_PCT), not a hardcoded 50%."""
from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.scheduled_jobs import JOBS
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.resource_management import EmployeeUtilizationMetric
from app.models.timesheet import Timesheet
from app.services import resource_management_service as rm
from tests.scope_fixtures import ApiClient, ids, two_bu_world, uid

TODAY = date(2026, 10, 21)  # a Wednesday; last completed week starts Monday 2026-10-12
LAST_WEEK = date(2026, 10, 12)


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def w(db):
    return two_bu_world(db)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _employee(db, bu, *, billable=True, status="ALLOCATED", joined=date(2025, 1, 1)):
    e = Employee(tenant_id=1, first_name="E", last_name=uid(), email=f"{uid()}@u.test", joining_date=joined,
                 status=status, bu_id=bu.id, is_billable=billable)
    db.add(e)
    db.flush()
    return e


def _hours(db, employee, client, job, week, hours, status="APPROVED"):
    allocation = EmployeeAllocation(tenant_id=1, employee_id=employee.id, client_id=client.id, demand_id=job.jobID,
                                    start_date=date(2025, 1, 1), status="ACTIVE")
    db.add(allocation)
    db.flush()
    db.add(Timesheet(tenant_id=1, employee_id=employee.id, allocation_id=allocation.id, week_starting_date=week,
                     total_hours=hours, billable_hours=hours, non_billable_hours=0, status=status))
    db.flush()


def _metrics(db, employee):
    return {m.period_start: float(m.utilization_pct) for m in
            db.query(EmployeeUtilizationMetric).filter(EmployeeUtilizationMetric.employee_id == employee.id)}


def test_the_weekly_job_snapshots_every_billable_working_employee(db, w, monkeypatch):
    monkeypatch.setattr(settings, "UTILIZATION_SNAPSHOT_WEEKS", 2)
    busy = _employee(db, w.bu_a)
    _hours(db, busy, w.client_a, w.job_a, LAST_WEEK, 30)
    _hours(db, busy, w.client_a, w.job_a, LAST_WEEK - timedelta(weeks=1), 12, status="SUBMITTED")  # not approved
    internal = _employee(db, w.bu_a, billable=False)
    not_joined = _employee(db, w.bu_a, status="PRE_JOINING")
    new_joiner = _employee(db, w.bu_b, joined=LAST_WEEK + timedelta(days=2))
    db.commit()

    result = rm.run_utilization_snapshot(db, today=TODAY)
    assert result["snapshots"] >= 3
    assert _metrics(db, busy) == {LAST_WEEK: 75.0, LAST_WEEK - timedelta(weeks=1): 0.0}
    assert _metrics(db, internal) == {} and _metrics(db, not_joined) == {}
    assert _metrics(db, new_joiner) == {LAST_WEEK: 0.0}  # not counted before they joined

    # rerun after a late approval: the week is updated, never duplicated
    db.query(Timesheet).filter(Timesheet.employee_id == busy.id, Timesheet.status == "SUBMITTED").update(
        {"status": "APPROVED"})
    db.commit()
    rm.run_utilization_snapshot(db, today=TODAY)
    assert _metrics(db, busy) == {LAST_WEEK: 75.0, LAST_WEEK - timedelta(weeks=1): 30.0}


def test_the_job_is_registered_and_on_by_default():
    job = JOBS["utilization_snapshot"]
    assert job.target == "app.services.resource_management_service:run_utilization_snapshot"
    assert job.interval == timedelta(days=7) and not job.sends_external
    assert "utilization_snapshot" in settings.SCHEDULED_JOBS_ENABLED.split(",")


def test_summary_flags_below_the_configured_target_and_skips_internal_staff(db, w, api, monkeypatch):
    monkeypatch.setattr(settings, "UTILIZATION_TARGET_PCT", 80)
    seventy, ninety, internal = _employee(db, w.bu_a), _employee(db, w.bu_a), _employee(db, w.bu_a, billable=False)
    for employee, pct in ((seventy, 70), (ninety, 90), (internal, 0)):
        db.add(EmployeeUtilizationMetric(tenant_id=1, employee_id=employee.id, period_start=LAST_WEEK,
                                         utilization_pct=pct, billable_hours=pct * 0.4, bench_hours=40 - pct * 0.4))
    db.commit()
    body = api.get(w.org_user, "/api/v1/employees/utilization-summary").json()
    assert body["utilization_target_pct"] == 80
    flags = {e["employee_id"]: e["is_low_utilization"] for e in body["employees"]}
    assert flags[seventy.id] is True and flags[ninety.id] is False  # 70% was "fine" under the old 50%
    assert internal.id not in flags


def test_recompute_now_covers_only_the_callers_business_units(db, w, api, monkeypatch):
    monkeypatch.setattr(settings, "UTILIZATION_SNAPSHOT_WEEKS", 1)
    mine, theirs = _employee(db, w.bu_a), _employee(db, w.bu_b)
    db.commit()
    res = api.post(w.partner_a, "/api/v1/employees/utilization/recompute")
    assert res.status_code == 200, res.text
    assert res.json()["employees"] >= 1
    assert _metrics(db, mine) and not _metrics(db, theirs)
    summary = ids(api.get(w.partner_a, "/api/v1/employees/utilization-summary").json(), "employee_id")
    assert mine.id in summary and theirs.id not in summary
