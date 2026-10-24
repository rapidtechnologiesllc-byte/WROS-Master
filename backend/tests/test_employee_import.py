"""Bulk employee import with a dry run (CEO 2026-10-22): current employees loaded as complete
records -- login, scope, Buddy attestation, bench or allocation, P&L cost -- able to log time the
day they are imported. One creation path: the Add employee form is a one-row import."""
import io
import json
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.models.audit_log import AuditLog
from app.models.buddy_program import BuddyProgramRecord
from app.models.business_unit import BusinessUnit, BusinessUnitLocationHead
from app.models.core_certification import CoreCertificationRequest
from app.models.cost_rate_config import CostRateConfig
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.employee_import import EmployeeImportBatch
from app.models.location import Location
from app.models.project import Project
from app.models.resource_management import BenchPoolEntry
from app.models.role_template import RoleTemplate
from app.models.timesheet import Timesheet
from app.models.user import Jobs, Users
from app.core.config import settings
from app.services import employee_import_service as importer
from tests.test_core_certification import _h, _uid, _user, db  # noqa: F401 -- db is a fixture
from tests.hiring_fixtures import full_access_role

COLUMNS = ("first_name,last_name,email,business_unit,delivery_center,joining_date,designation,manager_email,"
           "billable,existing_staff,core_certified,monthly_salary,salary_currency,bench_since,"
           "allocation_job_id,allocation_pct,allocation_start_date")
TODAY = date.today()
LAST_MONDAY = TODAY - timedelta(days=TODAY.weekday() + 7)


@pytest.fixture
def mail():
    """Every queue write the import makes (activation emails go through enqueue_once)."""
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True) as once, \
            patch("app.services.message_queue_service.MessageQueueService.enqueue", return_value={}) as enqueue:
        yield type("Mail", (), dict(once=once, enqueue=enqueue))


@pytest.fixture
def world(db):
    role = full_access_role(db)
    from app.core.db_contract import LEADERSHIP_ROLES, ensure_role

    ensure_role(db, "Employee", LEADERSHIP_ROLES["Employee"], 1)  # the self-service role startup seeds
    unit = BusinessUnit(tenant_id=1, name=f"axion-{_uid()}", display_name="Axion", bu_code=_uid()[:6])
    company = Location(tenant_id=1, name=f"BX-IN-{_uid()}", country="India")
    db.add_all([unit, company])
    db.flush()
    from app.models.business_unit import BusinessUnitCompany
    from app.models.client import Client

    db.add(BusinessUnitCompany(tenant_id=1, business_unit_id=unit.id, company_id=company.id))
    head = _user(db, role, "BU Head")
    db.add(BusinessUnitLocationHead(tenant_id=1, business_unit_id=unit.id, company_id=company.id,
                                    head_user_id=head.UserID))
    hr = _user(db, role, "HR Admin")
    manager = _user(db, role, "Manager")
    manager.org_node_id = _seat_chain(db, 8).id  # managers are recorded in the org chart: the manager has a seat
    client = Client(tenant_id=1, company_name=f"Insurer {_uid()}", business_unit_id=unit.id, line_type="SPECIALITY")
    db.add(client)
    db.flush()
    project = Project(tenant_id=1, client_id=client.id, name=f"Policy Center {_uid()}", delivery_engine="SPECIALITY")
    db.add(project)
    db.flush()
    job = Jobs(tenant_id=1, client_id=client.id, project_id=project.id, business_unit_id=unit.id,
               jobTitle="Guidewire Dev", jobDescription="d", jobSkills="x", jobExperience="5", jobLocation="Remote",
               billing_rate_usd_cents=5000)
    db.add(job)
    db.add(CostRateConfig(business_unit_id=unit.id, statutory_pct=10, overhead_pct=10, created_by=hr.UserID))
    db.commit()
    return type("World", (), dict(role=role, unit=unit, company=company, head=head, hr=hr, manager=manager,
                                  client=client, project=project, job=job))


def _seat_chain(db, level: int):
    """A seat at `level` under a valid chain of seats up to the CEO (each one or two levels up)."""
    from app.core.db_contract import _initialize_org_positions, _initialize_org_roles
    from app.models.org_structure import OrgNode
    from app.services.org_structure_service import create_org_node

    _initialize_org_positions(db)  # what startup seeds; a fresh test database has none
    _initialize_org_roles(db)
    node = db.query(OrgNode).filter(OrgNode.tenant_id == 1, OrgNode.hierarchy_level == 17,
                                    OrgNode.active.is_(True)).first() \
        or create_org_node(db, tenant_id=1, name="CEO seat", hierarchy_level=17, specialization="General")
    current = 17
    while current > level:
        current = max(level, current - 2)
        node = create_org_node(db, tenant_id=1, name=f"Seat {current} {_uid()}", hierarchy_level=current,
                               specialization="General", parent_id=node.id)
    return node


def _csv(*rows) -> bytes:
    return ("\n".join([COLUMNS, *rows]) + "\n").encode()


def _row(w, email, *, joining=date(2024, 4, 1), billable="yes", existing="yes", core="no", salary="2000",
         currency="USD", bench_since="", job="", pct="", start="", manager=True):
    return ",".join([
        "Asha", "Rao", email, w.unit.display_name, w.company.name, joining.isoformat(), "Lead Consultant",
        w.manager.UserEmail if manager else "", billable, existing, core, salary, currency, bench_since,
        job, pct, start])


def _counts(model, db):
    return db.query(model).count()


def test_dry_run_writes_nothing_and_sends_nothing(db, world, mail):
    before = (_counts(Employee, db), _counts(Users, db), _counts(BuddyProgramRecord, db))
    preview = importer.dry_run(db, world.hr, _csv(_row(world, f"a{_uid()}@bx.test"),
                                                  _row(world, "not-an-email")))
    assert (_counts(Employee, db), _counts(Users, db), _counts(BuddyProgramRecord, db)) == before
    assert not mail.once.called and not mail.enqueue.called
    assert preview["counts"]["create"] == 1 and preview["counts"]["error"] == 1
    first, second = preview["rows"]
    assert first["action"] == "create" and first["status_after"] == "BENCH" and first["errors"] == []
    assert first["business_unit"] == "Axion" and first["country"] == "IN"
    assert any("not an email" in e for e in second["errors"])
    assert db.get(EmployeeImportBatch, preview["token"]).row_count == 2


def test_apply_creates_a_complete_employee_once(db, world, mail):
    email = f"asha{_uid()}@bx.test"
    content = _csv(_row(world, email))
    preview = importer.dry_run(db, world.hr, content)
    outcome = importer.apply(db, world.hr, preview["token"], content)
    assert outcome["counts"] == {"total": 1, "applied": 1}
    employee = db.query(Employee).filter_by(email=email).one()
    user = db.query(Users).filter_by(UserEmail=email).one()
    assert employee.wros_user_id == user.UserID and user.password_reset_required
    assert db.get(RoleTemplate, user.role_template_id).name == "Employee"
    assert (employee.bu_id, employee.company_id, employee.status) == (world.unit.id, world.company.id, "BENCH")
    assert employee.reporting_manager_user_id == world.manager.UserID
    assert employee.base_salary_usd_cents == 200_000 and employee.is_billable
    bench = db.query(BenchPoolEntry).filter_by(employee_id=employee.id).one()
    assert bench.available_from == employee.joining_date  # bench counted from the real first bench day
    # Buddy: attested by the importer, audited, not a code carve-out
    assert employee.buddy_program_status == "GRADUATED"
    record = db.query(BuddyProgramRecord).filter_by(employee_id=employee.id).one()
    assert record.status == "GRADUATED" and "Existing employee imported" in record.bu_head_decision_notes
    assert db.query(AuditLog).filter_by(entity_id=employee.id, action="buddy_graduated_on_import").count() == 1
    # one activation email, after commit, with a key that never repeats
    assert mail.once.call_count == 1
    assert mail.once.call_args.args[1] == f"account-email-{user.UserID}-ACTIVATE-employee-import"

    again = importer.apply(db, world.hr, preview["token"], content)  # idempotent
    assert again["counts"] == {"total": 1, "unchanged": 1}
    assert db.query(Employee).filter_by(email=email).count() == 1 and mail.once.call_count == 1


def test_a_changed_file_or_someone_elses_token_is_refused(db, world, mail):
    content = _csv(_row(world, f"x{_uid()}@bx.test"))
    preview = importer.dry_run(db, world.hr, content)
    with pytest.raises(importer.ImportTokenError) as changed:
        importer.apply(db, world.hr, preview["token"], _csv(_row(world, f"y{_uid()}@bx.test")))
    assert changed.value.status_code == 409
    with pytest.raises(importer.ImportTokenError) as other:
        importer.apply(db, world.manager, preview["token"], content)
    assert other.value.status_code == 404
    batch = db.get(EmployeeImportBatch, preview["token"])
    batch.expires_at = batch.created_at - timedelta(minutes=1)
    db.commit()
    with pytest.raises(importer.ImportTokenError) as expired:
        importer.apply(db, world.hr, preview["token"], content)
    assert expired.value.status_code == 410


def test_update_by_email_and_link_existing_login(db, world, mail):
    legacy = Employee(tenant_id=1, first_name="Old", last_name="Name", email=f"legacy{_uid()}@bx.test",
                      joining_date=date(2023, 1, 1), status="BENCH", bu_id=world.unit.id)
    login_only = _user(db, world.role, "Recruiter With Login")  # made on Users & Access, no Employee
    db.add(legacy)
    db.commit()
    content = _csv(_row(world, legacy.email, salary="3000"), _row(world, login_only.UserEmail, billable="no"))
    preview = importer.dry_run(db, world.hr, content)
    update, link = preview["rows"]
    assert update["action"] == "update" and any("base_salary_usd_cents" in c for c in update["changes"])
    assert "login: create login + activation email" in update["changes"]
    assert link["action"] == "link-existing-user" and link["status_after"] == "ACTIVE"
    importer.apply(db, world.hr, preview["token"], content)
    db.refresh(legacy)
    assert legacy.base_salary_usd_cents == 300_000 and legacy.wros_user_id and legacy.first_name == "Asha"
    linked = db.query(Employee).filter_by(email=login_only.UserEmail.lower()).one()
    assert linked.wros_user_id == login_only.UserID and linked.status == "ACTIVE" and not linked.is_billable
    assert db.query(BenchPoolEntry).filter_by(employee_id=linked.id).count() == 0  # internal staff: never bench
    assert mail.once.call_count == 1  # only the newly created login is emailed; the linked one already signs in


def test_business_unit_scope_is_enforced(db, mail):
    from tests.scope_fixtures import two_bu_world

    w = two_bu_world(db)
    company = Location(tenant_id=1, name=f"BX-US-{_uid()}", country="US")
    db.add(company)
    db.commit()
    row = (f"Ben,Ko,b{_uid()}@bx.test,{w.bu_b.name},{company.name},2024-01-01,,,yes,yes,no,1000,USD,,,,")
    preview = importer.dry_run(db, w.partner_a, _csv(row))
    assert preview["counts"]["error"] == 1
    assert any("You cannot add employees" in e for e in preview["rows"][0]["errors"])


def test_core_certified_needs_a_leader_of_the_business_unit(db, world, mail):
    content = _csv(_row(world, f"c{_uid()}@bx.test", core="yes"))
    assert any("leader of this business unit" in e
               for e in importer.dry_run(db, world.hr, content)["rows"][0]["errors"])
    preview = importer.dry_run(db, world.head, content)
    importer.apply(db, world.head, preview["token"], content)
    employee = db.query(Employee).filter_by(email=preview["rows"][0]["email"]).one()
    request = db.query(CoreCertificationRequest).filter_by(employee_id=employee.id).one()
    assert employee.core_certified and request.status == "APPROVED" and request.decided_by_user_id == world.head.UserID


def test_future_joiner_is_pre_joining_and_not_bench(db, world, mail):
    content = _csv(_row(world, f"f{_uid()}@bx.test", joining=TODAY + timedelta(days=20)))
    preview = importer.dry_run(db, world.hr, content)
    assert preview["rows"][0]["status_after"] == "PRE_JOINING"
    importer.apply(db, world.hr, preview["token"], content)
    employee = db.query(Employee).filter_by(email=preview["rows"][0]["email"]).one()
    assert employee.status == "PRE_JOINING" and not db.query(BenchPoolEntry).filter_by(employee_id=employee.id).count()


def test_new_hires_cannot_be_allocated_and_allocation_needs_billable(db, world, mail):
    rows = importer.dry_run(db, world.hr, _csv(
        _row(world, f"n{_uid()}@bx.test", existing="no", job=world.job.jobID),
        _row(world, f"m{_uid()}@bx.test", billable="no", job=world.job.jobID)))["rows"]
    assert any("existing_staff=yes" in e for e in rows[0]["errors"])
    assert any("non-billable employee is not allocated" in e for e in rows[1]["errors"])


def test_imported_and_allocated_employee_logs_time_that_reaches_invoice_and_pnl(db, world, mail):
    """existing_staff -> Buddy graduated -> allocation passes every deployment gate -> My Timesheet
    -> submit -> approve -> invoice and the revenue-chain P&L."""
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app
    from app.services import invoice_service
    from app.services.revenue_chain_service import pnl

    email = f"alloc{_uid()}@bx.test"
    start = LAST_MONDAY - timedelta(weeks=2)
    content = _csv(_row(world, email, job=world.job.jobID, pct="100", start=start.isoformat()))
    preview = importer.dry_run(db, world.hr, content)
    assert preview["rows"][0]["status_after"] == "ALLOCATED", preview["rows"][0]["errors"]
    importer.apply(db, world.hr, preview["token"], content)
    employee = db.query(Employee).filter_by(email=email).one()
    allocation = db.query(EmployeeAllocation).filter_by(employee_id=employee.id).one()
    assert employee.status == "ALLOCATED" and allocation.project_id == world.project.id
    assert db.query(BenchPoolEntry).filter_by(employee_id=employee.id).count() == 0
    login = db.get(Users, employee.wros_user_id)

    app.dependency_overrides[get_db] = lambda: db
    try:
        api = TestClient(app)
        mine = api.get("/api/v1/my/allocations", headers=_h(login)).json()["allocations"]
        assert [a["id"] for a in mine] == [allocation.id]
        sheet = api.get("/api/v1/my/timesheet/current", headers=_h(login),
                        params={"allocation_id": allocation.id, "week_starting": LAST_MONDAY.isoformat()}).json()
        entries = [{"entry_date": (LAST_MONDAY + timedelta(days=i)).isoformat(), "hours": 8} for i in range(5)]
        assert api.put(f"/api/v1/my/timesheet/{sheet['id']}/entries", headers=_h(login),
                       json={"entries": entries}).status_code == 200
        assert api.post(f"/api/v1/my/timesheet/{sheet['id']}/submit", headers=_h(login)).status_code == 200
        approved = api.post(f"/api/v1/timesheets/{sheet['id']}/approve", headers=_h(world.manager))
        assert approved.status_code == 200, approved.text
    finally:
        app.dependency_overrides.clear()
    assert db.get(Timesheet, sheet["id"]).status == "APPROVED"

    report = pnl(db, start=LAST_MONDAY, end=LAST_MONDAY + timedelta(days=6), tenant_id=1)
    unit_row = next(r for r in report["by_business_unit"] if r["key"] == world.unit.id)
    assert unit_row["revenue_usd_cents"] == 40 * 5000  # 40 approved hours x $50
    assert unit_row["delivery_cost_usd_cents"] > 0
    invoice = invoice_service.generate_invoice(db, world.project, period_start=LAST_MONDAY,
                                               period_end=LAST_MONDAY + timedelta(days=6))
    assert invoice.total_usd_cents == 40 * 5000


def test_bench_employee_costs_bench_in_the_pnl(db, world, mail):
    from app.services.revenue_chain_service import pnl

    email = f"bench{_uid()}@bx.test"
    content = _csv(_row(world, email, salary="3000"))
    importer.apply(db, world.hr, importer.dry_run(db, world.hr, content)["token"], content)
    report = pnl(db, start=LAST_MONDAY, end=LAST_MONDAY + timedelta(days=6), tenant_id=1)
    unit_row = next(r for r in report["by_business_unit"] if r["key"] == world.unit.id)
    assert unit_row["bench_cost_usd_cents"] > 0 and unit_row["cost_data_complete"]


def test_inr_salary_is_converted_with_the_configured_rate(db, world, mail):
    from app.core.config import settings

    content = _csv(_row(world, f"inr{_uid()}@bx.test", salary="170000", currency="INR"))
    importer.apply(db, world.hr, importer.dry_run(db, world.hr, content)["token"], content)
    employee = db.query(Employee).filter(Employee.email.like("inr%")).order_by(Employee.created_at.desc()).first()
    assert employee.base_salary_usd_cents == round(170000 * 100 / settings.FX_INR_PER_USD)


def test_unknown_columns_fail_the_whole_file(db, world, mail):
    with pytest.raises(importer.ImportFileError, match="Unknown columns: salary_band"):
        importer.dry_run(db, world.hr, b"first_name,last_name,email,salary_band\n")


# --------------------------------------------------------------------------- the HTTP surface

@pytest.fixture
def api(db, mail):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_http_dry_run_then_apply_and_template(api, db, world):
    template = api.get("/api/v1/employees/import/template", headers=_h(world.hr)).json()
    assert template["csv"].startswith("first_name,last_name,email")
    assert {c["name"] for c in template["columns"]} >= {"billable", "existing_staff", "monthly_salary"}
    content = _csv(_row(world, f"h{_uid()}@bx.test"))
    preview = api.post("/api/v1/employees/import/dry-run", headers=_h(world.hr),
                       files={"file": ("staff.csv", io.BytesIO(content), "text/csv")})
    assert preview.status_code == 200, preview.text
    applied = api.post("/api/v1/employees/import/apply", headers=_h(world.hr), data={"token": preview.json()["token"]},
                       files={"file": ("staff.csv", io.BytesIO(content), "text/csv")})
    assert applied.status_code == 200 and applied.json()["counts"]["applied"] == 1
    changed = api.post("/api/v1/employees/import/apply", headers=_h(world.hr), data={"token": preview.json()["token"]},
                       files={"file": ("staff.csv", io.BytesIO(content + b"\n" + _row(world, "z@bx.test").encode()),
                                       "text/csv")})
    assert changed.status_code == 409


def test_add_employee_form_is_a_one_row_import(api, db, world, mail):
    body = {"first_name": "Form", "last_name": "Hire", "email": f"form{_uid()}@bx.test",
            "joining_date": "2024-02-01", "business_unit_id": world.unit.id, "company_id": world.company.id,
            "base_salary_usd_cents": 250_000, "billable": True, "reporting_manager_id": world.manager.UserID,
            "current_title": "Lead Consultant"}
    created = api.post("/api/v1/employees", headers=_h(world.hr), json=body)
    assert created.status_code == 200, created.text
    item = created.json()
    assert item["has_login"] and item["status"] == "BENCH" and item["buddy_program_status"] == "GRADUATED"
    assert item["reporting_manager_user_id"] == world.manager.UserID and mail.once.call_count == 1
    assert api.post("/api/v1/employees", headers=_h(world.hr), json=body).status_code == 409


def test_employee_list_reads_legacy_skills_and_reports_allocations(api, db, world):
    legacy = Employee(tenant_id=1, first_name="Legacy", last_name="Skills", email=f"s{_uid()}@bx.test",
                      joining_date=date(2023, 1, 1), status="BENCH", bu_id=world.unit.id,
                      current_skills="Java, Guidewire; PolicyCenter")
    db.add(legacy)
    db.commit()
    res = api.get("/api/v1/employees", headers=_h(world.hr))
    assert res.status_code == 200, res.text
    row = next(e for e in res.json()["employees"] if e["id"] == legacy.id)
    assert row["current_skills"] == ["Java", "Guidewire", "PolicyCenter"]
    assert row["active_allocations"] == [] and row["allocated_pct"] == 0
    json.dumps(row)  # serialisable as the screen receives it


# --------------------------------------------------------------------------- manager = org chart seat

def _row_for(w, email, manager_email, designation="Lead Consultant"):
    return ",".join(["Ravi", "Iyer", email, w.unit.display_name, w.company.name, "2024-04-01", designation,
                     manager_email, "yes", "yes", "no", "2000", "USD", "", "", "", ""])


def test_import_seats_the_employee_under_the_managers_seat(db, world, mail):
    from app.models.org_structure import OrgNode

    email = f"seat{_uid()}@bx.test"
    content = _csv(_row(world, email))
    importer.apply(db, world.hr, importer.dry_run(db, world.hr, content)["token"], content)
    user = db.query(Users).filter_by(UserEmail=email).one()
    seat = db.get(OrgNode, user.org_node_id)
    assert seat.parent_id == world.manager.org_node_id and seat.hierarchy_level == 6
    employee = db.query(Employee).filter_by(email=email).one()
    assert employee.org_node_id == seat.id and employee.reporting_manager_user_id == world.manager.UserID


def test_a_manager_without_a_seat_or_a_non_role_designation_is_refused_in_the_dry_run(db, world, mail):
    unseated = _user(db, world.role, "Unseated")
    db.commit()
    preview = importer.dry_run(db, world.hr, _csv(_row_for(world, f"u{_uid()}@bx.test", unseated.UserEmail),
                                                  _row_for(world, f"d{_uid()}@bx.test", world.manager.UserEmail,
                                                           designation="Ninja"),
                                                  _row_for(world, f"g{_uid()}@bx.test", world.manager.UserEmail,
                                                           designation="Associate")))
    no_seat, no_role, too_far = preview["rows"]
    assert any("has no seat in the org chart" in e for e in no_seat["errors"])
    assert any("is not an org role" in e for e in no_role["errors"])
    assert any("can't report to a level 8 manager" in e for e in too_far["errors"])  # Associate is level 2


def test_a_manager_listed_later_in_the_same_file_is_seated_first(db, world, mail):
    boss, report = f"boss{_uid()}@bx.test", f"rep{_uid()}@bx.test"
    content = _csv(_row_for(world, report, boss), _row_for(world, boss, world.manager.UserEmail, designation="Associate Manager"))
    preview = importer.dry_run(db, world.hr, content)
    assert preview["counts"]["error"] == 0, preview["rows"]
    outcome = importer.apply(db, world.hr, preview["token"], content)
    assert outcome["counts"]["applied"] == 2 and [r["row"] for r in outcome["rows"]] == [2, 3]
    boss_user = db.query(Users).filter_by(UserEmail=boss).one()
    report_user = db.query(Users).filter_by(UserEmail=report).one()
    from app.models.org_structure import OrgNode

    assert db.get(OrgNode, report_user.org_node_id).parent_id == boss_user.org_node_id
    assert db.get(OrgNode, boss_user.org_node_id).parent_id == world.manager.org_node_id


def test_changing_the_manager_on_reimport_moves_the_seat(db, world, mail):
    from app.models.org_structure import OrgNode

    email = f"move{_uid()}@bx.test"
    content = _csv(_row(world, email))
    importer.apply(db, world.hr, importer.dry_run(db, world.hr, content)["token"], content)
    other = _user(db, world.role, "Other Manager")
    other.org_node_id = _seat_chain(db, 7).id
    db.commit()
    content = _csv(_row_for(world, email, other.UserEmail))
    preview = importer.dry_run(db, world.hr, content)
    assert preview["rows"][0]["action"] == "update"
    assert any(c.startswith("manager:") for c in preview["rows"][0]["changes"])
    importer.apply(db, world.hr, preview["token"], content)
    user = db.query(Users).filter_by(UserEmail=email).one()
    assert db.get(OrgNode, user.org_node_id).parent_id == other.org_node_id
    assert db.query(Employee).filter_by(email=email).one().reporting_manager_user_id == other.UserID


def test_timesheet_approver_is_read_from_the_org_chart(db, world, mail):
    from app.services.timesheet_approval_service import resolve_approver

    email = f"chart{_uid()}@bx.test"
    content = _csv(_row(world, email))
    importer.apply(db, world.hr, importer.dry_run(db, world.hr, content)["token"], content)
    employee = db.query(Employee).filter_by(email=email).one()
    assert resolve_approver(db, employee).UserID == world.manager.UserID
    # a stale copy on the employee row does not win over the chart
    employee.reporting_manager_user_id = world.hr.UserID
    db.flush()
    assert resolve_approver(db, employee).UserID == world.manager.UserID
    # the manager leaves the seat: the next person seated above approves
    from app.models.org_structure import OrgNode

    above = db.get(OrgNode, db.get(OrgNode, world.manager.org_node_id).parent_id)
    world.head.org_node_id = above.id
    world.manager.org_node_id = None
    db.flush()
    assert resolve_approver(db, employee).UserID == world.head.UserID


def test_add_employee_form_lists_org_roles_and_seated_managers(api, db, world):
    template = api.get("/api/v1/employees/import/template", headers=_h(world.hr)).json()
    assert {"name": "Lead Consultant", "level": 6} in template["org_roles"]
    assert any(m["user_id"] == world.manager.UserID and m["level"] == 8 for m in template["managers"])
    assert all(m["user_id"] != world.hr.UserID for m in template["managers"])  # not seated


# ---- pay as agreed (CEO 2026-10-24) ------------------------------------------------------------

def test_add_employee_takes_annual_pay_in_the_countrys_currency(api, db, world, mail):
    body = {"first_name": "Annual", "last_name": "Pay", "email": f"pay{_uid()}@bx.test",
            "joining_date": "2024-02-01", "business_unit_id": world.unit.id, "company_id": world.company.id,
            "pay_amount_cents": 102_000_000, "pay_basis": "ANNUAL", "billable": True,
            "reporting_manager_id": world.manager.UserID, "current_title": "Lead Consultant"}
    created = api.post("/api/v1/employees", headers=_h(world.hr), json=body)
    assert created.status_code == 200, created.text
    row = db.query(Employee).filter_by(email=body["email"]).one()
    # the company is in India, so INR; the P&L cost is the monthly USD equivalent
    assert (row.pay_amount_cents, row.pay_currency, row.pay_basis) == (102_000_000, "INR", "ANNUAL")
    assert row.base_salary_usd_cents == round(102_000_000 / 12 / settings.FX_INR_PER_USD)


def test_add_employee_with_hourly_usd_pay(api, db, world, mail):
    body = {"first_name": "Hourly", "last_name": "Pay", "email": f"hr{_uid()}@bx.test",
            "joining_date": "2024-02-01", "business_unit_id": world.unit.id, "company_id": world.company.id,
            "pay_amount_cents": 4_500, "pay_basis": "HOURLY", "pay_currency": "USD", "billable": True,
            "reporting_manager_id": world.manager.UserID, "current_title": "Lead Consultant"}
    assert api.post("/api/v1/employees", headers=_h(world.hr), json=body).status_code == 200
    row = db.query(Employee).filter_by(email=body["email"]).one()
    assert row.base_salary_usd_cents == round(4_500 * settings.STANDARD_MONTHLY_HOURS)


def test_add_employee_without_pay_is_refused(api, db, world, mail):
    body = {"first_name": "No", "last_name": "Pay", "email": f"np{_uid()}@bx.test", "joining_date": "2024-02-01",
            "business_unit_id": world.unit.id, "company_id": world.company.id, "billable": True,
            "reporting_manager_id": world.manager.UserID, "current_title": "Lead Consultant"}
    response = api.post("/api/v1/employees", headers=_h(world.hr), json=body)
    assert response.status_code in (400, 422)
    assert "pay is required" in response.text


def test_older_clients_monthly_usd_salary_is_recorded_as_monthly_usd_pay(api, db, world, mail):
    body = {"first_name": "Old", "last_name": "Client", "email": f"old{_uid()}@bx.test",
            "joining_date": "2024-02-01", "business_unit_id": world.unit.id, "company_id": world.company.id,
            "base_salary_usd_cents": 250_000, "billable": True, "reporting_manager_id": world.manager.UserID,
            "current_title": "Lead Consultant"}
    assert api.post("/api/v1/employees", headers=_h(world.hr), json=body).status_code == 200
    row = db.query(Employee).filter_by(email=body["email"]).one()
    assert (row.pay_amount_cents, row.pay_currency, row.pay_basis, row.base_salary_usd_cents) == \
        (250_000, "USD", "MONTHLY", 250_000)


def test_profile_pay_edit_recomputes_the_cost(api, db, world, mail):
    body = {"first_name": "Edit", "last_name": "Pay", "email": f"ed{_uid()}@bx.test", "joining_date": "2024-02-01",
            "business_unit_id": world.unit.id, "company_id": world.company.id, "base_salary_usd_cents": 250_000,
            "billable": True, "reporting_manager_id": world.manager.UserID, "current_title": "Lead Consultant"}
    employee_id = api.post("/api/v1/employees", headers=_h(world.hr), json=body).json()["id"]
    changed = api.patch(f"/api/v1/employees/{employee_id}", headers=_h(world.hr),
                        json={"pay_amount_cents": 12_000_000, "pay_basis": "ANNUAL", "pay_currency": "USD"})
    assert changed.status_code == 200, changed.text
    row = db.get(Employee, employee_id)
    db.refresh(row)
    assert row.base_salary_usd_cents == 1_000_000
    assert api.patch(f"/api/v1/employees/{employee_id}", headers=_h(world.hr),
                     json={"pay_basis": "WEEKLY"}).status_code == 400


def test_import_row_with_annual_pay_columns(db, world, mail):
    header = COLUMNS + ",pay,pay_basis"
    email = f"imp{_uid()}@bx.test"
    row = _row(world, email, salary="", currency="INR") + ",1200000,ANNUAL"
    content = ("\n".join([header, row]) + "\n").encode()
    importer.apply(db, world.hr, importer.dry_run(db, world.hr, content)["token"], content)
    employee = db.query(Employee).filter_by(email=email).one()
    assert (employee.pay_amount_cents, employee.pay_currency, employee.pay_basis) == (120_000_000, "INR", "ANNUAL")
    assert employee.base_salary_usd_cents == round(120_000_000 / 12 / settings.FX_INR_PER_USD)


def test_existing_salaries_become_monthly_usd_pay(db, world):
    from app.core.db_contract import _pay_from_monthly_usd

    legacy = Employee(tenant_id=1, first_name="Was", last_name="Monthly", email=f"lg{_uid()}@bx.test",
                      joining_date=date(2023, 1, 1), status="BENCH", bu_id=world.unit.id, base_salary_usd_cents=300_000)
    db.add(legacy)
    db.flush()
    assert _pay_from_monthly_usd(db) >= 1
    assert (legacy.pay_amount_cents, legacy.pay_currency, legacy.pay_basis, legacy.base_salary_usd_cents) == \
        (300_000, "USD", "MONTHLY", 300_000)
