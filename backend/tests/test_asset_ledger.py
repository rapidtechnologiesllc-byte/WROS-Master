"""Asset ledger (CEO 2026-11-10): one record per device, owned by the IT Admin function. Every item names
its owner (one of our companies, a client, a lessor, the employee) and is always in one place; every
courier movement carries a tracking number; a project's kit is checked when someone is placed and asked
back when the placement ends; notice or exit asks everything back and full and final settlement waits for
IT Admin's sign-off (same rule in every country); overdue returns climb from the holder to their manager
to their BU head; a bench employee keeps their company laptop.

Calls go through the real API as signed-in users and the permission matrix, on the test's own
rolled-back transaction."""
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.models.asset import Asset, AssetClearance, AssetIssue, AssetReturn, AssetShipment
from app.models.business_unit import BusinessUnitLocationHead
from app.models.client import Client
from app.models.employee_allocation import EmployeeAllocation
from app.models.location import Location
from app.models.org_structure import Department
from app.models.project import Project
from app.models.task import Task
from app.services import asset_service
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _employee_role(db):
    """What every login has: My Tasks (view), nothing else."""
    from app.models.role_template import Resource, RoleTemplatePermission

    role = factories.role(db)
    resource = db.query(Resource).filter_by(tenant_id=1, name="my-tasks").one()
    db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=resource.id, tenant_id=1, can_view=True))
    db.flush()
    return role


@pytest.fixture
def world(db):
    role = full_access_role(db)
    function = db.query(Department).filter(Department.tenant_id == 1, Department.name == settings.ASSET_OWNER_FUNCTION).first()
    if function is None:
        function = Department(id=str(uuid.uuid4()), tenant_id=1, name=settings.ASSET_OWNER_FUNCTION, active=True)
        db.add(function)
        db.flush()
    it_admin = factories.user(db, role_template_id=role.id, UserRole="admin", UserName="Ira IT", department_id=function.id)
    company = Location(tenant_id=1, name=f"BlitzenX India {factories.uid()}", country="India")
    unit = factories.business_unit(db)
    db.add(company)
    db.flush()
    client = Client(tenant_id=1, company_name=f"Carrier {factories.uid()}", business_unit_id=unit.id, payment_terms_days=30)
    db.add(client)
    db.flush()
    job = factories.job(db, client_id=client.id, business_unit_id=unit.id, jobTitle="Guidewire Developer")
    project = Project(tenant_id=1, client_id=client.id, name="BillingCenter upgrade", delivery_engine="SPECIALITY")
    db.add(project)
    db.flush()
    manager_login = factories.user(db, role_template_id=role.id, UserName="Mo Manager")
    head_login = factories.user(db, role_template_id=role.id, UserName="Hana Head")
    db.add(BusinessUnitLocationHead(tenant_id=1, business_unit_id=unit.id, company_id=company.id,
                                    head_user_id=head_login.UserID))
    login = factories.user(db, role_template_id=_employee_role(db).id, UserName="Akshay")  # an ordinary employee
    employee = factories.employee(db, first_name="Akshay", last_name="P", status="BENCH", bu_id=unit.id,
                                  company_id=company.id, buddy_program_status="GRADUATED", wros_user_id=login.UserID,
                                  reporting_manager_user_id=manager_login.UserID)
    db.commit()
    return SimpleNamespace(it_admin=it_admin, function=function, company=company, unit=unit, client=client, job=job,
                           project=project, employee=employee, login=login, manager=manager_login, head=head_login)


def _laptop(api, world, **overrides):
    body = {"category": "LAPTOP", "owner_type": "COMPANY", "owner_company_id": world.company.id, "make": "Dell",
            "model": "Latitude 7440", "serial_number": f"SN-{factories.uid()}"}
    body.update(overrides)
    response = api.post(world.it_admin, "/api/v1/assets", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _client_token(api, world):
    return _laptop(api, world, category="SECURITY_TOKEN", owner_type="CLIENT", owner_company_id=None,
                   owner_client_id=world.client.id, make="RSA", model="SecurID")


def _hand_over(api, world, asset, **extra):
    response = api.post(world.it_admin, f"/api/v1/assets/{asset['id']}/issue-to-employee",
                        json={"employee_id": world.employee.id, "method": "HAND", **extra})
    assert response.status_code == 200, response.text
    return response.json()


def _open_tasks(db, category, employee=None):
    query = db.query(Task).filter(Task.category == category, Task.status.in_(("NEW", "IN_PROGRESS", "ON_HOLD")))
    if employee is not None:
        query = query.filter(Task.link == asset_service.employee_path(employee.id))
    return query.all()


def _place(api, world, **overrides):
    body = {"employee_id": world.employee.id, "demand_id": world.job.jobID, "project_id": world.project.id,
            "utilization_pct": 100.0, "role": "Developer", "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=90)).isoformat()}
    body.update(overrides)
    response = api.post(world.it_admin, "/api/v1/allocations", json=body)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- the ledger

def test_every_item_names_its_owner_and_a_serial_is_on_the_ledger_once(api, world):
    no_company = api.post(world.it_admin, "/api/v1/assets", json={"category": "LAPTOP", "owner_type": "COMPANY"})
    assert no_company.status_code == 400 and "which of our companies" in no_company.json()["detail"]
    no_client = api.post(world.it_admin, "/api/v1/assets", json={"category": "LAPTOP", "owner_type": "CLIENT"})
    assert no_client.status_code == 400 and "client" in no_client.json()["detail"]
    laptop = _laptop(api, world, serial_number="SN-ONE-123")
    assert laptop["status"] == "IN_STOCK" and laptop["owner_label"] == world.company.name
    assert laptop["asset_tag"].startswith("AST-") and laptop["events"][0]["event_type"] == "REGISTERED"
    again = api.post(world.it_admin, "/api/v1/assets", json={"category": "LAPTOP", "owner_type": "COMPANY",
                                                            "owner_company_id": world.company.id,
                                                            "serial_number": "sn-one-123"})
    assert again.status_code == 400 and laptop["asset_tag"] in again.json()["detail"]
    token = _client_token(api, world)
    assert token["owner_label"] == f"Client: {world.client.company_name}"


def test_the_ledger_is_for_its_users_only(api, world, db):
    _laptop(api, world)
    assert api.get(world.login, "/api/v1/assets").status_code == 403
    assert api.post(world.login, "/api/v1/assets", json={"category": "LAPTOP", "owner_type": "LEASED",
                                                         "owner_name": "Lease Co"}).status_code == 403
    listing = api.get(world.it_admin, "/api/v1/assets", params={"search": "latitude"}).json()
    assert listing["summary"]["total"] >= 1 and listing["assets"]


# --------------------------------------------------------------------------- shipping and receipt

def test_a_courier_shipment_needs_the_tracking_number_and_the_holder_confirms_it(api, world, db):
    laptop = _laptop(api, world)
    path = f"/api/v1/assets/{laptop['id']}/issue-to-employee"
    missing = api.post(world.it_admin, path, json={"employee_id": world.employee.id, "method": "COURIER",
                                                   "carrier": "Blue Dart"})
    assert missing.status_code == 400 and "tracking number" in missing.json()["detail"]
    shipped = api.post(world.it_admin, path, json={"employee_id": world.employee.id, "method": "COURIER",
                                                   "carrier": "Blue Dart", "tracking_number": "BD123456"})
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["status"] == "IN_TRANSIT" and shipped.json()["shipment"]["tracking_number"] == "BD123456"

    stranger = factories.user(db, role_template_id=_employee_role(db).id)
    db.commit()
    assert api.post(stranger, f"/api/v1/assets/{laptop['id']}/confirm-receipt", json={}).status_code == 404
    received = api.post(world.login, f"/api/v1/assets/{laptop['id']}/confirm-receipt", json={})
    assert received.status_code == 200, received.text
    assert received.json()["status"] == "ASSIGNED" and received.json()["holder_employee_id"] == world.employee.id
    mine = api.get(world.login, f"/api/v1/assets/employee/{world.employee.id}").json()
    assert [a["id"] for a in mine["held"]] == [laptop["id"]] and mine["is_self"]


def test_a_courier_nobody_confirms_is_chased_once(api, world, db):
    laptop = _laptop(api, world)
    api.post(world.it_admin, f"/api/v1/assets/{laptop['id']}/issue-to-employee",
             json={"employee_id": world.employee.id, "method": "COURIER", "carrier": "DHL", "tracking_number": "DHL9",
                   "shipped_on": (date.today() - timedelta(days=settings.ASSET_TRANSIT_MAX_DAYS + 2)).isoformat()})
    for _ in range(2):
        asset_service.run_asset_sweep(db)
    chases = db.query(Task).filter(Task.category == "ASSET_TRANSIT", Task.link == asset_service.asset_path(laptop["id"])).all()
    assert len(chases) == 1 and chases[0].assigned_to_user_id == world.it_admin.UserID
    alerts = api.get(world.it_admin, "/api/v1/assets/alerts").json()["alerts"]
    assert any(a["kind"] == "IN_TRANSIT_TOO_LONG" and a["asset_id"] == laptop["id"] for a in alerts)
    api.post(world.it_admin, f"/api/v1/assets/{laptop['id']}/confirm-receipt", json={})
    db.expire_all()
    assert db.get(Task, chases[0].id).status == "COMPLETED"


# --------------------------------------------------------------------------- project kit

def test_a_placement_on_a_project_that_needs_kit_opens_one_task_for_it_admin(api, world, db):
    kit = api.put(world.it_admin, f"/api/v1/assets/project/{world.project.id}/requirements",
                  json={"items": [{"category": "LAPTOP", "provided_by": "COMPANY"},
                                  {"category": "SECURITY_TOKEN", "provided_by": "CLIENT", "note": "VPN token"}]})
    assert kit.status_code == 200, kit.text
    _place(api, world)
    tasks = _open_tasks(db, "ASSET_KIT", world.employee)
    assert len(tasks) == 1 and tasks[0].assigned_to_user_id == world.it_admin.UserID
    assert tasks[0].department_id == world.function.id
    assert "laptop" in tasks[0].description and "security token" in tasks[0].description
    gaps = api.get(world.it_admin, f"/api/v1/assets/employee/{world.employee.id}").json()["kit_gaps"]
    assert {g["category"] for g in gaps} == {"LAPTOP", "SECURITY_TOKEN"}

    _hand_over(api, world, _laptop(api, world))
    _hand_over(api, world, _client_token(api, world), project_id=world.project.id)
    db.expire_all()
    assert not _open_tasks(db, "ASSET_KIT", world.employee)  # closes by itself once they hold it all


def test_a_client_device_must_belong_to_the_projects_client(api, world, db):
    other = Client(tenant_id=1, company_name=f"Other {factories.uid()}", business_unit_id=world.unit.id)
    db.add(other)
    db.commit()
    token = _laptop(api, world, category="SECURITY_TOKEN", owner_type="CLIENT", owner_company_id=None,
                    owner_client_id=other.id)
    response = api.post(world.it_admin, f"/api/v1/assets/{token['id']}/issue-to-employee",
                        json={"employee_id": world.employee.id, "method": "HAND", "project_id": world.project.id})
    assert response.status_code == 400 and "different client" in response.json()["detail"]


def test_project_end_asks_back_the_clients_device_and_the_bench_keeps_the_laptop(api, world, db):
    allocation = _place(api, world)
    laptop = _hand_over(api, world, _laptop(api, world))
    token = _hand_over(api, world, _client_token(api, world), project_id=world.project.id)
    ended = api.post(world.it_admin, f"/api/v1/allocations/{allocation['id']}/end",
                     json={"end_date": date.today().isoformat()})
    assert ended.status_code == 200, ended.text
    db.expire_all()
    returns = db.query(AssetReturn).filter(AssetReturn.employee_id == world.employee.id, AssetReturn.status == "OPEN").all()
    assert [r.asset_id for r in returns] == [token["id"]] and returns[0].reason == "PROJECT_END"
    assert db.get(Asset, laptop["id"]).status == "ASSIGNED"  # stays with them on the bench
    task = _open_tasks(db, "ASSET_RETURN", world.employee)
    assert len(task) == 1 and token["asset_tag"] in task[0].description


def test_the_sweep_asks_kit_back_before_a_placement_ends(api, world, db):
    _place(api, world, end_date=(date.today() + timedelta(days=settings.ASSET_RETURN_LEAD_DAYS - 1)).isoformat())
    token = _hand_over(api, world, _client_token(api, world), project_id=world.project.id)
    first = asset_service.run_asset_sweep(db)
    second = asset_service.run_asset_sweep(db)
    assert first["returns_requested"] >= 1 and second["failed"] == 0
    rows = db.query(AssetReturn).filter(AssetReturn.asset_id == token["id"]).all()
    assert len(rows) == 1 and rows[0].status == "OPEN"


# --------------------------------------------------------------------------- leaving

def test_notice_asks_everything_back_and_settlement_waits_for_it_admin(api, world, db):
    laptop = _hand_over(api, world, _laptop(api, world))
    personal = api.post(world.it_admin, "/api/v1/assets", json={"category": "PHONE", "owner_type": "PERSONAL",
                                                                "employee_id": world.employee.id}).json()
    last_day = (date.today() + timedelta(days=30)).isoformat()
    notice = api.post(world.it_admin, f"/api/v1/employees/{world.employee.id}/employment",
                      json={"action": "START_NOTICE", "effective_date": last_day, "reason": "Resigned"})
    assert notice.status_code == 200, notice.text
    db.expire_all()
    clearance = db.query(AssetClearance).filter(AssetClearance.employee_id == world.employee.id).one()
    assert clearance.status == "PENDING" and clearance.due_date.isoformat() == last_day
    assert _open_tasks(db, "ASSET_CLEARANCE", world.employee)[0].assigned_to_user_id == world.it_admin.UserID
    asked = {r.asset_id for r in db.query(AssetReturn).filter(AssetReturn.employee_id == world.employee.id)}
    assert asked == {laptop["id"]}  # never their own phone

    view = api.get(world.it_admin, f"/api/v1/assets/employee/{world.employee.id}").json()
    assert "Assets not returned" in view["settlement_hold"]
    refused = api.post(world.it_admin, f"/api/v1/assets/employee/{world.employee.id}/clearance/sign-off", json={})
    assert refused.status_code == 400 and laptop["asset_tag"] in refused.json()["detail"]

    sent = api.post(world.login, f"/api/v1/assets/{laptop['id']}/return-shipment",
                    json={"carrier": "Delhivery", "tracking_number": "DLV-77"})
    assert sent.status_code == 200 and sent.json()["status"] == "IN_TRANSIT"
    back = api.post(world.it_admin, f"/api/v1/assets/{laptop['id']}/receive-return", json={"condition": "GOOD"})
    assert back.status_code == 200 and back.json()["status"] == "IN_STOCK" and back.json()["holder_employee_id"] is None
    signed = api.post(world.it_admin, f"/api/v1/assets/employee/{world.employee.id}/clearance/sign-off", json={})
    assert signed.status_code == 200, signed.text
    assert signed.json()["settlement_hold"] is None and signed.json()["clearance"]["status"] == "CLEARED"
    db.expire_all()
    assert db.get(Asset, personal["id"]).status == "RETURNED_TO_OWNER"  # off the ledger with them
    assert not _open_tasks(db, "ASSET_CLEARANCE", world.employee) and not _open_tasks(db, "ASSET_RETURN", world.employee)


def test_an_exit_without_notice_also_holds_settlement(api, world, db):
    _hand_over(api, world, _laptop(api, world))
    response = api.post(world.it_admin, f"/api/v1/employees/{world.employee.id}/employment",
                        json={"action": "RECORD_EXIT", "effective_date": date.today().isoformat(), "reason": "Terminated"})
    assert response.status_code == 200, response.text
    db.expire_all()
    assert asset_service.settlement_hold(db, world.employee).startswith("Assets not returned")
    alerts = api.get(world.it_admin, "/api/v1/assets/alerts").json()["alerts"]
    assert {"HOLDER_LEFT", "CLEARANCE_PENDING"} <= {a["kind"] for a in alerts if a["employee_id"] == world.employee.id}


def test_a_lost_item_needs_a_note_on_the_clearance(api, world, db):
    laptop = _hand_over(api, world, _laptop(api, world))
    api.post(world.it_admin, f"/api/v1/employees/{world.employee.id}/employment",
             json={"action": "START_NOTICE", "effective_date": (date.today() + timedelta(days=5)).isoformat(),
                   "reason": "Resigned"})
    assert api.post(world.it_admin, f"/api/v1/assets/{laptop['id']}/lost", json={"note": "Stolen, FIR 4411"}).status_code == 200
    plain = api.post(world.it_admin, f"/api/v1/assets/employee/{world.employee.id}/clearance/sign-off", json={})
    assert plain.status_code == 400 and "Lost while with them" in plain.json()["detail"]
    noted = api.post(world.it_admin, f"/api/v1/assets/employee/{world.employee.id}/clearance/sign-off",
                     json={"note": "Recovered from final settlement"})
    assert noted.status_code == 200 and noted.json()["lost"]


def test_nothing_new_is_issued_to_someone_leaving(api, world, db):
    api.post(world.it_admin, f"/api/v1/employees/{world.employee.id}/employment",
             json={"action": "START_NOTICE", "effective_date": (date.today() + timedelta(days=5)).isoformat(),
                   "reason": "Resigned"})
    laptop = _laptop(api, world)
    response = api.post(world.it_admin, f"/api/v1/assets/{laptop['id']}/issue-to-employee",
                        json={"employee_id": world.employee.id, "method": "HAND"})
    assert response.status_code == 400 and "leaving" in response.json()["detail"]


# --------------------------------------------------------------------------- escalation

def test_an_overdue_return_climbs_holder_then_manager_then_bu_head_once_each(api, world, db):
    laptop = _hand_over(api, world, _laptop(api, world))
    first, second, third = asset_service.escalation_days()
    api.post(world.it_admin, f"/api/v1/assets/{laptop['id']}/request-return",
             json={"due_date": (date.today() - timedelta(days=third)).isoformat(), "reason": "RECALL"})
    result = asset_service.run_asset_sweep(db)
    assert result["escalated"] == 1
    row = db.query(AssetReturn).filter(AssetReturn.asset_id == laptop["id"]).one()
    assert row.escalation_level == 3
    escalations = _open_tasks(db, "ASSET_ESCALATION", world.employee)
    assert {t.assigned_to_user_id for t in escalations} == {world.manager.UserID, world.head.UserID}
    assert asset_service.run_asset_sweep(db)["escalated"] == 0  # each level once
    assert len(_open_tasks(db, "ASSET_ESCALATION", world.employee)) == 2

    api.post(world.it_admin, f"/api/v1/assets/{laptop['id']}/receive-return", json={"condition": "GOOD"})
    db.expire_all()
    assert not _open_tasks(db, "ASSET_ESCALATION", world.employee)  # closed with the return


# --------------------------------------------------------------------------- defects

def test_a_defect_is_tied_to_the_item_and_closes_with_its_fix(api, world, db):
    laptop = _hand_over(api, world, _laptop(api, world))
    reported = api.post(world.login, f"/api/v1/assets/{laptop['id']}/issues",
                        json={"description": "Keyboard keys stuck", "severity": "HIGH"})
    assert reported.status_code == 200, reported.text
    issue = db.query(AssetIssue).filter(AssetIssue.asset_id == laptop["id"]).one()
    task = db.get(Task, issue.task_id)
    assert task.category == "ASSET_ISSUE" and task.priority == "HIGH" and task.assigned_to_user_id == world.it_admin.UserID
    path = f"/api/v1/assets/issues/{issue.id}"
    assert api.post(world.it_admin, path, json={"action": "START_REPAIR"}).status_code == 400
    assert api.post(world.it_admin, path, json={"action": "START_REPAIR", "repair_vendor": "Dell care"}).status_code == 200
    fixed = api.post(world.it_admin, path, json={"action": "FIXED", "resolution": "Keyboard replaced",
                                                 "fix_cost_cents": 450000})
    assert fixed.status_code == 200 and fixed.json()["open_issues"] == 0
    db.expire_all()
    assert db.get(Task, issue.task_id).status == "COMPLETED"
    kinds = [e["event_type"] for e in fixed.json()["events"]]
    assert {"DEFECT_REPORTED", "REPAIR_STARTED", "DEFECT_CLOSED"} <= set(kinds)


def test_an_item_back_damaged_opens_a_defect_and_a_retired_one_cannot_go_out(api, world, db):
    laptop = _hand_over(api, world, _laptop(api, world))
    back = api.post(world.it_admin, f"/api/v1/assets/{laptop['id']}/receive-return",
                    json={"condition": "DAMAGED", "note": "Cracked screen"})
    assert back.status_code == 200 and back.json()["open_issues"] == 1
    issue = db.query(AssetIssue).filter(AssetIssue.asset_id == laptop["id"]).one()
    retired = api.post(world.it_admin, f"/api/v1/assets/issues/{issue.id}",
                       json={"action": "RETIRE", "resolution": "Not worth repairing; disk wiped"})
    assert retired.status_code == 200 and retired.json()["status"] == "RETIRED"
    again = api.post(world.it_admin, f"/api/v1/assets/{laptop['id']}/issue-to-employee",
                     json={"employee_id": world.employee.id, "method": "HAND"})
    assert again.status_code == 400 and "not in stock" in again.json()["detail"]


def test_a_clients_device_goes_back_to_the_client_with_tracking(api, world, db):
    token = _client_token(api, world)
    laptop_for_company = _laptop(api, world)
    refused = api.post(world.it_admin, f"/api/v1/assets/{laptop_for_company['id']}/return-to-owner",
                       json={"method": "HAND"})
    assert refused.status_code == 400
    sent = api.post(world.it_admin, f"/api/v1/assets/{token['id']}/return-to-owner",
                    json={"method": "COURIER", "carrier": "FedEx", "tracking_number": "FX-1"})
    assert sent.status_code == 200 and sent.json()["status"] == "RETURNED_TO_OWNER"
    assert api.post(world.it_admin, f"/api/v1/assets/{token['id']}/owner-received", json={}).status_code == 200
    shipment = db.query(AssetShipment).filter(AssetShipment.asset_id == token["id"]).one()
    assert shipment.direction == "TO_OWNER" and shipment.status == "DELIVERED"


def test_without_anyone_in_it_admin_the_tasks_still_have_an_owner(api, world, db, monkeypatch):
    monkeypatch.setattr(settings, "ASSET_OWNER_FUNCTION", f"Nobody Here {uuid.uuid4().hex[:6]}")
    monkeypatch.setattr("app.services.vendor_invoice_intake.vendor_payer", lambda db, tenant_id: world.head.UserID)
    assert asset_service.it_admin_owner(db, 1) == world.head.UserID


def test_the_asset_owner_function_is_seeded_once(db):
    from app.core.db_contract import _initialize_asset_function

    factories.tenant(db)
    _initialize_asset_function(db)
    _initialize_asset_function(db)
    rows = db.query(Department).filter(Department.tenant_id == 1, Department.name == settings.ASSET_OWNER_FUNCTION).all()
    assert len(rows) == 1


def test_the_ledger_is_on_the_admin_menu(db):
    from app.contracts.api_contract import MODULES_AND_RESOURCES
    from app.seeds.init_resources import RESOURCE_ROUTES

    assert "assets" in MODULES_AND_RESOURCES["Admin & Settings"]
    assert RESOURCE_ROUTES["assets"] == "/admin/assets"


def test_allocation_rows_exist_for_the_placement_used_in_tests(api, world, db):
    created = _place(api, world)
    assert db.get(EmployeeAllocation, created["id"]).project_id == world.project.id
