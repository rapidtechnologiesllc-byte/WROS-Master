"""Staff-aug revenue protection (CEO 2026-10-23, gaps 1 and 4).

Allocation edit/extend with history, every placement rule re-run on the edited values, bill-rate
changes that never reprice a past week; the renewal pipeline (status, owner, daily alert tasks);
and the rate card / margin floor at placement with BU Head / Partner approval by role level.
"""
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.models.business_unit import BusinessUnitLocationHead
from app.models.client import Client
from app.models.cost_rate_config import CostRateConfig
from app.models.employee import Employee
from app.models.employee_allocation import AllocationChange, AllocationRenewalAlert, EmployeeAllocation
from app.models.employee_escalation import EmployeeEscalation
from app.models.location import Location
from app.models.margin_policy import MarginPolicy
from app.models.project import Project
from app.models.task import Task
from app.models.timesheet import Timesheet, TimesheetEntry
from app.services import allocation_renewal_service as renewals
from app.services import employee_allocation_service as allocations
from app.services import margin_guard_service as margin_guard
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient

# $100.00/h loaded: 173.33 h x 10000 cents, with no statutory or overhead load
SALARY_CENTS = round(settings.STANDARD_MONTHLY_HOURS * 10000)
START = date.today() - timedelta(days=date.today().weekday() + 21)  # a Monday three weeks ago


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _person(db, level, name, org_level=False):
    role = full_access_role(db)
    role.hierarchy_level, role.org_level_access = level, org_level
    db.flush()
    return factories.user(db, role_template_id=role.id, UserName=name)


@pytest.fixture
def world(db):
    admin = _person(db, 5, "Allocator", org_level=True)
    company = Location(tenant_id=1, name=f"co-{factories.uid()}")
    db.add(company)
    db.flush()
    head = _person(db, settings.BU_LEADER_MIN_LEVEL, "BU Head")
    partner = _person(db, settings.PARTNER_MIN_LEVEL, "Partner")
    junior = _person(db, settings.BU_LEADER_MIN_LEVEL - 1, "Manager", org_level=True)
    unit = factories.business_unit(db, partner_user_id=partner.UserID)
    db.add(BusinessUnitLocationHead(tenant_id=1, business_unit_id=unit.id, company_id=company.id,
                                    head_user_id=head.UserID))
    client = Client(tenant_id=1, company_name=f"Insurer {factories.uid()}", business_unit_id=unit.id,
                    contracting_company_id=company.id, line_type="SPECIALITY", payment_terms_days=30)
    db.add(client)
    db.flush()
    project = Project(tenant_id=1, client_id=client.id, name="PolicyCenter", delivery_engine="SPECIALITY")
    db.add(project)
    db.flush()
    job = factories.job(db, client_id=client.id, business_unit_id=unit.id, project_id=project.id,
                        jobTitle="Guidewire Developer", billing_rate_usd_cents=13000)
    employee = factories.employee(db, first_name="Asha", last_name="Rao", status="BENCH", bu_id=unit.id,
                                  company_id=company.id, buddy_program_status="GRADUATED",
                                  base_salary_usd_cents=SALARY_CENTS)
    db.add(CostRateConfig(tenant_id=1, statutory_pct=0, overhead_pct=0, effective_date=date(2020, 1, 1)))
    db.commit()
    return SimpleNamespace(admin=admin, head=head, partner=partner, junior=junior, unit=unit, company=company,
                           client=client, project=project, job=job, employee=employee)


def _floor(db, minimum=20, hard=10, **kw):
    row = MarginPolicy(tenant_id=1, delivery_engine="SPECIALITY", min_margin_pct=minimum, hard_floor_pct=hard, **kw)
    db.add(row)
    db.commit()
    return row


def _allocate(api, w, **overrides):
    body = {"employee_id": w.employee.id, "demand_id": w.job.jobID, "project_id": w.project.id,
            "start_date": START.isoformat(), "end_date": (date.today() + timedelta(days=120)).isoformat(),
            "utilization_pct": 100}
    body.update(overrides)
    return api.post(w.admin, "/api/v1/allocations", json=body)


def _sheet(db, allocation, monday, status="APPROVED", hours=40):
    sheet = Timesheet(tenant_id=1, employee_id=allocation.employee_id, allocation_id=allocation.id,
                      week_starting_date=monday, status=status, total_hours=hours, billable_hours=hours)
    db.add(sheet)
    db.flush()
    for offset in range(5):
        db.add(TimesheetEntry(timesheet_id=sheet.id, entry_date=monday + timedelta(days=offset), hours=hours / 5,
                              entry_type="BILLABLE"))
    db.commit()
    return sheet


# --------------------------------------------------------------------------- margin floor at placement

def test_no_floor_configured_allows_the_placement_and_flags_it(api, world):
    response = _allocate(api, world)
    assert response.status_code == 200, response.text
    item = response.json()
    assert item["status"] == "ACTIVE"
    assert item["margin"]["margin_check"] == "NO_FLOOR_CONFIGURED"
    assert "NO_MARGIN_FLOOR_CONFIGURED" in item["margin"]["flags"]
    assert item["margin"]["margin_pct"] == pytest.approx(23.08, abs=0.01)  # (130 - 100) / 130


def test_placement_at_or_above_the_floor_is_active(api, world, db):
    _floor(db)
    item = _allocate(api, world).json()
    assert (item["status"], item["margin_check"]) == ("ACTIVE", "OK")
    db.expire_all()
    assert db.get(Employee, world.employee.id).status == "ALLOCATED"


def test_below_minimum_waits_for_the_bu_head_and_blocks_timesheets(api, world, db):
    from app.services.timesheet_service import AllocationNotActive, create_weekly_draft

    _floor(db)
    item = _allocate(api, world, billing_rate_usd_cents=11500).json()  # 13% < 20%
    assert item["status"] == "PENDING_MARGIN_APPROVAL" and item["margin_check"] == "BELOW_MIN"
    change = item["pending_change"]
    assert change["approval_level"] == "BU_HEAD" and change["approver_user_id"] == world.head.UserID
    task = db.get(Task, change["task_id"])
    assert task.assigned_to_user_id == world.head.UserID
    assert task.link == f"/employees?tab=allocations&allocation={item['id']}"
    db.expire_all()
    assert db.get(Employee, world.employee.id).status == "BENCH"  # not placed until approved
    allocation = db.get(EmployeeAllocation, item["id"])
    with pytest.raises(AllocationNotActive):
        create_weekly_draft(db, allocation, START)

    # the requester cannot approve their own placement, nor can someone below BU Head level
    assert api.post(world.admin, f"/api/v1/allocations/changes/{change['id']}/approve",
                    json={"reason": "Strategic account"}).status_code == 403
    assert api.post(world.junior, f"/api/v1/allocations/changes/{change['id']}/approve",
                    json={"reason": "Strategic account"}).status_code == 403
    assert api.post(world.head, f"/api/v1/allocations/changes/{change['id']}/approve",
                    json={"reason": "ok"}).status_code == 422  # a reason is a sentence
    approved = api.post(world.head, f"/api/v1/allocations/changes/{change['id']}/approve",
                        json={"reason": "Strategic account, rate rises at renewal"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "ACTIVE" and approved.json()["pending_change"] is None
    db.expire_all()
    assert db.get(Employee, world.employee.id).status == "ALLOCATED"
    assert db.get(Task, change["task_id"]).status == "COMPLETED"
    assert create_weekly_draft(db, db.get(EmployeeAllocation, item["id"]), START) is not None


def test_below_the_hard_floor_needs_a_partner(api, world, db):
    _floor(db)
    item = _allocate(api, world, billing_rate_usd_cents=10500).json()  # 4.8% < 10%
    change = item["pending_change"]
    assert change["approval_level"] == "PARTNER" and change["approver_user_id"] == world.partner.UserID
    assert api.post(world.head, f"/api/v1/allocations/changes/{change['id']}/approve",
                    json={"reason": "BU Head tries"}).status_code == 403
    assert api.post(world.partner, f"/api/v1/allocations/changes/{change['id']}/approve",
                    json={"reason": "Partner accepts the land deal"}).status_code == 200


def test_rejection_keeps_the_employee_on_the_bench(api, world, db):
    _floor(db)
    item = _allocate(api, world, billing_rate_usd_cents=11500).json()
    rejected = api.post(world.head, f"/api/v1/allocations/changes/{item['pending_change']['id']}/reject",
                        json={"reason": "Rate is too low for this skill"})
    assert rejected.status_code == 200 and rejected.json()["status"] == "MARGIN_REJECTED"
    db.expire_all()
    assert db.get(Employee, world.employee.id).status == "BENCH"
    # a rejected placement never holds the employee: they can be placed again
    assert _allocate(api, world, billing_rate_usd_cents=13000).json()["status"] == "ACTIVE"


def test_unknown_cost_under_a_floor_fails_closed(api, world, db):
    _floor(db)
    world.employee.base_salary_usd_cents = None
    db.commit()
    item = _allocate(api, world).json()
    assert item["status"] == "PENDING_MARGIN_APPROVAL" and item["margin_check"] == "NO_COST_DATA"


def test_most_specific_floor_wins(db, world):
    _floor(db, minimum=20, hard=10)
    _floor(db, minimum=35, hard=25, role="Architect")
    assert float(margin_guard.policy_for(db, 1, "SPECIALITY", None, "architect").min_margin_pct) == 35
    assert float(margin_guard.policy_for(db, 1, "SPECIALITY", None, "Developer").min_margin_pct) == 20
    assert margin_guard.policy_for(db, 1, "CORE", None, "Developer") is None


def test_pending_placement_holds_the_employee_and_cannot_be_invoiced(api, world, db):
    from app.services.invoice_service import AllocationNotBillable, generate_invoice

    _floor(db)
    item = _allocate(api, world, billing_rate_usd_cents=11500).json()
    assert _allocate(api, world, billing_rate_usd_cents=13000).status_code == 409  # no double booking
    allocation = db.get(EmployeeAllocation, item["id"])
    _sheet(db, allocation, START)  # however it got there, it is never billed
    with pytest.raises(AllocationNotBillable):
        generate_invoice(db, world.project, period_start=START, period_end=START + timedelta(days=6))


def test_existing_active_allocations_are_not_blocked_retroactively(db, world):
    from app.services.invoice_service import generate_invoice
    from app.services.timesheet_service import create_weekly_draft

    legacy = EmployeeAllocation(tenant_id=1, employee_id=world.employee.id, demand_id=world.job.jobID,
                                client_id=world.client.id, project_id=world.project.id, start_date=START,
                                billing_rate_usd_cents=10100, status="ACTIVE")
    db.add(legacy)
    db.commit()
    _floor(db)  # the floor arrives after the placement
    assert create_weekly_draft(db, legacy, START + timedelta(days=7)) is not None
    _sheet(db, legacy, START)
    invoice = generate_invoice(db, world.project, period_start=START, period_end=START + timedelta(days=6))
    assert invoice.total_usd_cents == 40 * 10100


def test_margin_preview_is_live_for_the_form(api, world, db):
    _floor(db)
    body = {"employee_id": world.employee.id, "demand_id": world.job.jobID, "billing_rate_usd_cents": 11500}
    preview = api.post(world.admin, "/api/v1/allocations/margin-preview", json=body)
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["margin_check"] == "BELOW_MIN" and data["approval_level"] == "BU_HEAD"
    assert data["loaded_hourly_cost_usd_cents"] == 10000 and data["min_margin_pct"] == 20


# --------------------------------------------------------------------------- edit / extend

def test_extend_writes_history_and_restarts_the_renewal(api, world, db):
    item = _allocate(api, world).json()
    db.query(EmployeeAllocation).filter_by(id=item["id"]).update({"renewal_status": "IN_DISCUSSION"})
    db.commit()
    new_end = (date.today() + timedelta(days=300)).isoformat()
    assert api.patch(world.admin, f"/api/v1/allocations/{item['id']}",
                     json={"end_date": new_end, "reason": ""}).status_code == 422
    response = api.patch(world.admin, f"/api/v1/allocations/{item['id']}",
                         json={"end_date": new_end, "reason": "Client extended the SOW by six months"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["change"]["status"] == "APPLIED"
    assert data["change"]["old_values"]["end_date"] == item["end_date"]
    assert data["change"]["new_values"]["end_date"] == new_end
    assert data["allocation"]["end_date"] == new_end and data["allocation"]["renewal_status"] == "NOT_STARTED"
    history = api.get(world.admin, f"/api/v1/allocations/{item['id']}/history").json()["changes"]
    assert [c["change_type"] for c in history] == ["EDIT", "CREATE"]
    assert history[0]["changed_by_user_id"] == world.admin.UserID
    assert history[0]["reason"] == "Client extended the SOW by six months"


def test_rate_change_never_reprices_a_billed_week(api, world, db):
    from app.services.invoice_service import generate_invoice

    item = _allocate(api, world).json()
    allocation = db.get(EmployeeAllocation, item["id"])
    _sheet(db, allocation, START)
    _sheet(db, allocation, START + timedelta(days=7), status="DRAFT")
    url = f"/api/v1/allocations/{item['id']}"
    into_billed = api.patch(world.admin, url, json={"billing_rate_usd_cents": 14000, "reason": "Rate uplift agreed",
                                                     "effective_from": START.isoformat()})
    assert into_billed.status_code == 422 and "already submitted" in into_billed.json()["detail"]
    assert api.patch(world.admin, url, json={"billing_rate_usd_cents": 14000, "reason": "Rate uplift agreed",
                                             "effective_from": (START + timedelta(days=8)).isoformat()}
                     ).status_code == 422  # not a Monday
    week2 = START + timedelta(days=7)
    ok = api.patch(world.admin, url, json={"billing_rate_usd_cents": 14000, "reason": "Rate uplift agreed",
                                           "effective_from": week2.isoformat()})
    assert ok.status_code == 200, ok.text
    db.expire_all()
    rates = allocations.RateHistory(db, [item["id"]])
    allocation = db.get(EmployeeAllocation, item["id"])
    assert rates.rate(allocation, START) == 13000 and rates.rate(allocation, week2) == 14000
    db.query(Timesheet).filter_by(allocation_id=item["id"], week_starting_date=week2).update({"status": "APPROVED"})
    db.commit()
    invoice = generate_invoice(db, world.project, period_start=START, period_end=week2 + timedelta(days=6))
    assert invoice.total_usd_cents == 40 * 13000 + 40 * 14000


def test_edit_below_the_floor_waits_and_keeps_the_current_terms(api, world, db):
    _floor(db)
    item = _allocate(api, world).json()
    url = f"/api/v1/allocations/{item['id']}"
    held = api.patch(world.admin, url, json={"billing_rate_usd_cents": 11500, "reason": "Client asked for a discount"})
    assert held.status_code == 200, held.text
    assert held.json()["change"]["status"] == "PENDING_APPROVAL"
    assert held.json()["allocation"]["billing_rate_usd_cents"] == 13000  # unchanged until approved
    assert api.patch(world.admin, url, json={"utilization_pct": 50, "reason": "Part time from next month"}
                     ).status_code == 409  # one pending change at a time
    change_id = held.json()["change"]["id"]
    assert api.post(world.head, f"/api/v1/allocations/changes/{change_id}/approve",
                    json={"reason": "Keeps the account"}).json()["billing_rate_usd_cents"] == 11500


def test_edit_reruns_the_deployment_rules_except_for_a_reduction(api, world, db):
    item = _allocate(api, world).json()
    db.add(EmployeeEscalation(tenant_id=1, employee_id=world.employee.id, reason="Client complaint", status="OPEN"))
    db.commit()
    url = f"/api/v1/allocations/{item['id']}"
    extend = api.patch(world.admin, url, json={"end_date": (date.today() + timedelta(days=400)).isoformat(),
                                               "reason": "Client wants to extend"})
    assert extend.status_code == 409 and "escalation" in extend.json()["detail"]
    shorten = api.patch(world.admin, url, json={"end_date": (date.today() + timedelta(days=10)).isoformat(),
                                                "reason": "Rolling off early after the complaint"})
    assert shorten.status_code == 200, shorten.text


def test_edit_cannot_end_before_submitted_time(api, world, db):
    item = _allocate(api, world).json()
    _sheet(db, db.get(EmployeeAllocation, item["id"]), START)
    response = api.patch(world.admin, f"/api/v1/allocations/{item['id']}",
                         json={"end_date": START.isoformat(), "reason": "Ended on day one"})
    assert response.status_code == 422 and "never rewritten" in response.json()["detail"]


def test_edit_rechecks_capacity(api, world, db):
    item = _allocate(api, world, utilization_pct=50).json()
    other_job = factories.job(db, client_id=world.client.id, business_unit_id=world.unit.id,
                              project_id=world.project.id, billing_rate_usd_cents=13000)
    db.commit()
    assert _allocate(api, world, demand_id=other_job.jobID, utilization_pct=50, allow_concurrent=True
                     ).status_code == 200
    response = api.patch(world.admin, f"/api/v1/allocations/{item['id']}",
                         json={"utilization_pct": 80, "reason": "More hours at the client"})
    assert response.status_code == 409 and "exceed 100%" in response.json()["detail"]


# --------------------------------------------------------------------------- renewals

def _active(db, w, ends_in, **kw):
    allocation = EmployeeAllocation(tenant_id=1, employee_id=w.employee.id, demand_id=w.job.jobID,
                                    client_id=w.client.id, project_id=w.project.id, start_date=START,
                                    end_date=date.today() + timedelta(days=ends_in), billing_rate_usd_cents=13000,
                                    status="ACTIVE", **kw)
    db.add(allocation)
    db.commit()
    return allocation


def test_alerts_go_to_the_account_manager_once_per_threshold(db, world):
    manager = _person(db, 9, "Account Manager")
    world.client.account_manager_user_id = manager.UserID
    allocation = _active(db, world, 25)
    first = renewals.run_renewal_alerts(db)
    assert first["alerted"] == 1
    tasks = db.query(Task).filter(Task.link == renewals.renewal_link(allocation.id)).all()
    assert len(tasks) == 1 and tasks[0].assigned_to_user_id == manager.UserID
    marks = {r.threshold_days for r in db.query(AllocationRenewalAlert).filter_by(allocation_id=allocation.id)}
    assert marks == {60, 30}  # 60 was passed too: one task, never a second one for it
    assert renewals.run_renewal_alerts(db)["alerted"] == 0
    assert renewals.run_renewal_alerts(db, today=date.today() + timedelta(days=10))["alerted"] == 1  # 15 days
    assert db.query(Task).filter(Task.link == renewals.renewal_link(allocation.id)).count() == 2


def test_owner_falls_back_to_the_bu_head_and_settled_renewals_are_skipped(db, world):
    allocation = _active(db, world, 59)
    assert renewals.effective_owner(db, allocation) == (world.head.UserID, "BU_HEAD")
    settled = _active(db, world, 29, renewal_status="ROLLING_OFF")
    assert renewals.run_renewal_alerts(db)["alerted"] == 1
    assert db.query(Task).filter(Task.link == renewals.renewal_link(settled.id)).count() == 0
    task = db.query(Task).filter(Task.link == renewals.renewal_link(allocation.id)).one()
    assert task.assigned_to_user_id == world.head.UserID


def test_a_new_term_gets_its_own_alerts(api, world, db):
    allocation = _active(db, world, 20)
    renewals.run_renewal_alerts(db)
    allocations.edit_allocation(db, allocation, changes={"end_date": date.today() + timedelta(days=40)},
                                reason="Short extension", changed_by=world.admin.UserID)
    db.commit()
    assert renewals.run_renewal_alerts(db)["alerted"] == 1  # the 60-day alert of the new term


def test_renewals_list_and_update(api, world, db):
    inside = _active(db, world, 45)
    _active(db, world, 200)
    listing = api.get(world.admin, "/api/v1/allocations/renewals?days=90")
    assert listing.status_code == 200, listing.text
    rows = listing.json()["renewals"]
    assert [r["allocation_id"] for r in rows] == [inside.id]
    assert rows[0]["days_left"] == 45 and rows[0]["renewal_owner_source"] == "BU_HEAD"
    assert listing.json()["alert_days"] == [60, 30, 15]
    updated = api.put(world.admin, f"/api/v1/allocations/{inside.id}/renewal",
                      json={"renewal_status": "ROLLING_OFF", "owner_user_id": world.partner.UserID,
                            "note": "Client budget cut"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["renewal_status"] == "ROLLING_OFF"
    assert updated.json()["renewal_owner_source"] == "SET"
    change = db.query(AllocationChange).filter_by(allocation_id=inside.id, change_type="RENEWAL").one()
    assert change.old_values["renewal_status"] == "NOT_STARTED" and change.reason == "Client budget cut"
    assert api.put(world.admin, f"/api/v1/allocations/{inside.id}/renewal",
                   json={"renewal_status": "MAYBE"}).status_code == 422


def test_alert_thresholds_config_fails_fast(monkeypatch):
    monkeypatch.setattr(settings, "RENEWAL_ALERT_DAYS", "60,soon")
    with pytest.raises(ValueError):
        renewals.alert_thresholds()
    monkeypatch.setattr(settings, "RENEWAL_ALERT_DAYS", "15,60,30")
    assert renewals.alert_thresholds() == [60, 30, 15]


def test_renewal_job_is_registered_and_enabled_by_default():
    from app.core.scheduled_jobs import JOBS

    job = JOBS["renewal_alerts"]
    assert job.target == "app.services.allocation_renewal_service:run_renewal_alerts" and not job.sends_external
    assert "renewal_alerts" in settings.SCHEDULED_JOBS_ENABLED


# --------------------------------------------------------------------------- rate card admin

def test_rate_card_crud(api, world, db):
    created = api.post(world.admin, "/api/v1/margin-policies",
                       json={"delivery_engine": "SPECIALITY", "min_margin_pct": 22, "hard_floor_pct": 12})
    assert created.status_code == 200, created.text
    assert api.post(world.admin, "/api/v1/margin-policies",
                    json={"delivery_engine": "SPECIALITY", "min_margin_pct": 25, "hard_floor_pct": 12}
                    ).status_code == 409
    assert api.post(world.admin, "/api/v1/margin-policies",
                    json={"delivery_engine": "CORE", "min_margin_pct": 10, "hard_floor_pct": 20}
                    ).status_code == 422
    row_id = created.json()["id"]
    assert api.put(world.admin, f"/api/v1/margin-policies/{row_id}",
                   json={"delivery_engine": "SPECIALITY", "min_margin_pct": 30, "hard_floor_pct": 15}
                   ).json()["min_margin_pct"] == 30
    listing = api.get(world.admin, "/api/v1/margin-policies").json()
    assert [p["id"] for p in listing["policies"]] == [row_id]
    assert {e["code"] for e in listing["engines"]} == {"SPECIALITY", "CORE"}
    assert api.delete(world.admin, f"/api/v1/margin-policies/{row_id}").status_code == 200
    assert db.query(MarginPolicy).count() == 0


def test_nothing_is_seeded():
    """The floors are Finance's numbers: no seed or startup code writes a rate-card row."""
    import pathlib

    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    sources = list((app_dir / "seeds").rglob("*.py")) + [app_dir / "core" / "db_contract.py"]
    assert not [p for p in sources if "MarginPolicy" in p.read_text(encoding="utf-8")]


def test_end_withdraws_a_pending_change(api, world, db):
    _floor(db)
    item = _allocate(api, world).json()
    held = api.patch(world.admin, f"/api/v1/allocations/{item['id']}",
                     json={"billing_rate_usd_cents": 11500, "reason": "Discount requested"}).json()
    assert api.post(world.admin, f"/api/v1/allocations/{item['id']}/end", json={}).status_code == 200
    db.expire_all()
    change = db.get(AllocationChange, held["change"]["id"])
    assert change.status == "REJECTED" and db.get(Task, change.task_id).status == "CANCELLED"
