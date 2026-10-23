"""Billable vs non-billable (CEO 2026-10-22): internal staff are never bench -- not in the bench
pool, Workforce bench groups, Flash bench answers or bench cost -- their cost is P&L overhead;
time on a non-billable allocation is NON_BILLABLE and never invoiced; reclassifying moves cost
between bench and overhead without changing the org total."""
from datetime import date

import pytest

from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.project import Project
from app.models.resource_management import BenchPoolEntry
from app.models.timesheet import TimesheetEntry
from app.models.user import Jobs
from app.services import bench_service, invoice_service, timesheet_service
from app.services.employee_allocation_service import allocate_employee_to_project, end_allocation
from app.services.revenue_chain_service import CostBook, pnl
from tests.test_core_certification import _h, _uid, db  # noqa: F401 -- fixtures
from tests.test_employee_import import api, mail, world  # noqa: F401 -- fixtures

MONTH_START, MONTH_END = date(2026, 9, 1), date(2026, 9, 30)


def _person(db, world, *, billable=True, status="BENCH", salary=300_000):
    e = Employee(tenant_id=1, first_name="Int", last_name=_uid(), email=f"{_uid()}@bx.test", joining_date=date(2025, 1, 1),
                 status=status, bu_id=world.unit.id, company_id=world.company.id, is_billable=billable,
                 base_salary_usd_cents=salary, buddy_program_status="GRADUATED")
    db.add(e)
    db.flush()
    return e


def _unit(report, world):
    return next(r for r in report["by_business_unit"] if r["key"] == world.unit.id)


def test_internal_staff_cost_is_overhead_and_the_org_total_does_not_move(db, world):
    worker = _person(db, world)
    db.commit()
    before = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    bench_service.set_billable(db, worker, False, changed_by="test")
    db.commit()
    after = pnl(db, start=MONTH_START, end=MONTH_END, tenant_id=1)
    assert after["total_cost_usd_cents"] == before["total_cost_usd_cents"]
    payroll = CostBook(db).period(worker, MONTH_START, MONTH_END)
    assert _unit(before, world)["bench_cost_usd_cents"] - _unit(after, world)["bench_cost_usd_cents"] == payroll
    assert _unit(after, world)["overhead_cost_usd_cents"] - _unit(before, world)["overhead_cost_usd_cents"] == payroll
    unit = _unit(after, world)  # every payroll cent of the BU is delivery, bench or overhead
    staff = db.query(Employee).filter(Employee.bu_id == world.unit.id, Employee.status != "PRE_JOINING").all()
    loaded = sum(CostBook(db).period(e, MONTH_START, MONTH_END) for e in staff)
    assert unit["cost_data_complete"]
    assert unit["delivery_cost_usd_cents"] + unit["bench_cost_usd_cents"] + unit["overhead_cost_usd_cents"] == loaded
    assert worker.status == "ACTIVE" and worker.billing_classification == "NON_BILLABLE"
    assert db.query(BenchPoolEntry).filter_by(employee_id=worker.id).count() == 0


def test_internal_staff_are_their_own_workforce_group_and_never_in_flash_bench(api, db, world):
    from app.services.flash_service import find_available_bench_employees

    internal = _person(db, world, billable=False, status="ACTIVE")
    db.commit()
    groups = api.get("/api/v1/workforce/overview?group=NON_BILLABLE", headers=_h(world.hr)).json()
    assert internal.id in [p["employee_id"] for p in groups["selection"]["people"]]
    bench_ids = [p["employee_id"] for g in ("BENCH_IN_BUDDY", "BENCH_READY", "BENCH_CORE_READY")
                 for p in api.get(f"/api/v1/workforce/overview?group={g}", headers=_h(world.hr)).json()["selection"]["people"]]
    assert internal.id not in bench_ids
    assert internal.id not in [r["employee_id"] for r in find_available_bench_employees(db, world.hr, "")]


def test_billable_toggle_endpoint_moves_people_on_and_off_the_bench(api, db, world):
    worker = _person(db, world, status="ACTIVE", billable=False)
    db.commit()
    res = api.put(f"/api/v1/employees/{worker.id}/billable", headers=_h(world.hr), json={"billable": True})
    assert res.status_code == 200 and res.json()["status"] == "BENCH" and res.json()["is_on_bench"]
    res = api.put(f"/api/v1/employees/{worker.id}/billable", headers=_h(world.hr), json={"billable": False})
    assert res.json()["status"] == "ACTIVE" and not res.json()["is_on_bench"]


def test_time_on_an_internal_project_is_non_billable_and_never_invoiced(db, world):
    internal = Project(tenant_id=1, client_id=world.client.id, name=f"Internal tools {_uid()}", is_billable=False)
    db.add(internal)
    db.flush()
    job = Jobs(tenant_id=1, client_id=world.client.id, project_id=internal.id, jobTitle="Tools", jobDescription="d",
               jobSkills="x", jobExperience="1", jobLocation="Remote", billing_rate_usd_cents=5000)
    db.add(job)
    worker = _person(db, world)
    db.flush()
    allocation = allocate_employee_to_project(db, tenant_id=1, employee=worker, demand=job, start_date=MONTH_START)
    assert allocation.billable is False and worker.billing_classification == "ALLOCATED"
    sheet = timesheet_service.create_weekly_draft(db, allocation, date(2026, 9, 7), tenant_id=1)
    db.flush()
    timesheet_service.upsert_entries(db, sheet, [{"entry_date": date(2026, 9, 7), "hours": 8, "entry_type": "BILLABLE"}])
    sheet.status = "APPROVED"
    db.commit()
    assert db.query(TimesheetEntry).filter_by(timesheet_id=sheet.id).one().entry_type == "NON_BILLABLE"
    assert float(sheet.billable_hours) == 0
    with pytest.raises(Exception):
        invoice_service.generate_invoice(db, internal, period_start=MONTH_START, period_end=MONTH_END)


def test_an_internal_employee_leaving_an_allocation_is_not_benched(db, world):
    worker = _person(db, world)
    allocation = allocate_employee_to_project(db, tenant_id=1, employee=worker, demand=world.job, start_date=MONTH_START)
    worker.is_billable = False
    end_allocation(db, allocation, worker)
    db.commit()
    assert worker.status == "ACTIVE" and db.query(BenchPoolEntry).filter_by(employee_id=worker.id).count() == 0


def test_reconcile_bench_pool_heals_both_directions_from_history(db, world):
    missing = _person(db, world)  # BENCH with no pool row (written before the rule)
    ended = EmployeeAllocation(tenant_id=1, employee_id=missing.id, demand_id=world.job.jobID, client_id=world.client.id,
                               start_date=date(2025, 3, 1), end_date=date(2026, 6, 30), status="ENDED")
    stale = _person(db, world, status="ALLOCATED")
    db.add_all([ended, EmployeeAllocation(tenant_id=1, employee_id=stale.id, demand_id=world.job.jobID,
                                          client_id=world.client.id, start_date=date(2026, 1, 1), status="ACTIVE"),
                BenchPoolEntry(tenant_id=1, employee_id=stale.id, available_from=date(2026, 1, 1))])
    db.commit()
    bench_service.reconcile_bench_pool(db)
    entry = db.query(BenchPoolEntry).filter_by(employee_id=missing.id).one()
    assert entry.available_from == date(2026, 7, 1)  # the day after their last allocation ended
    assert db.query(BenchPoolEntry).filter_by(employee_id=stale.id).count() == 0
    again = bench_service.reconcile_bench_pool(db)
    assert again["added"] == 0 and again["removed"] == 0
    assert db.get(Employee, missing.id).billing_classification == "BENCH"

