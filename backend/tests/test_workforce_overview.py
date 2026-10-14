"""Workforce Overview (CEO 2026-10-14): every employee in exactly one of bench / Staff Aug /
Core groups, so the groups add up to headcount; scoped to the caller's business units."""
import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.business_unit import BusinessUnit
from app.models.client import Client
from app.models.demand import Demand
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.employee_escalation import EmployeeEscalation
from app.models.project import Project
from app.models.role_template import Resource, RoleTemplate, RoleTemplatePermission
from app.models.user import Users
from tests.hiring_fixtures import full_access_role


def _uid():
    return uuid.uuid4().hex[:8]


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
def api(db):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True):
        yield TestClient(app)
    app.dependency_overrides.clear()


def _headers(user):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


def _user(db, role):
    user = Users(UserID=f"U-{_uid()}", UserName="Viewer", UserEmail=f"v{_uid()}@blitzenx.com", UserPassword="x",
                 UserRole="user", tenant_id=1, role_template_id=role.id, password_reset_required=False)
    db.add(user)
    db.flush()
    return user


def _employee(db, name, *, buddy="GRADUATED", certified=False, status="BENCH", bu_id=None):
    e = Employee(tenant_id=1, first_name=name, last_name="T", email=f"{name}{_uid()}@blitzenx.com",
                 joining_date=date(2025, 1, 1), status=status, buddy_program_status=buddy, bu_id=bu_id,
                 core_certified=certified, core_certified_date=date(2026, 1, 1) if certified else None)
    db.add(e)
    db.flush()
    return e


def _allocate(db, employee, *, line, end_date=None, via_project=False):
    client = Client(tenant_id=1, company_name=f"C {_uid()}", line_type=None if via_project else line)
    db.add(client)
    db.flush()
    project = None
    if via_project:
        project = Project(tenant_id=1, client_id=client.id, name=f"P {_uid()}", delivery_engine=line)
        db.add(project)
        db.flush()
    job = Demand(tenant_id=1, client_id=client.id, job_title="Role", work_location="REMOTE", status="OPEN")
    db.add(job)
    db.flush()
    db.add(EmployeeAllocation(tenant_id=1, employee_id=employee.id, demand_id=job.id, client_id=client.id,
                              project_id=project.id if project else None, start_date=date.today(),
                              end_date=end_date, status="ACTIVE"))
    db.flush()


def _group_of(body, employee):
    return next(g["key"] for g in body["groups"] for p in g["people"] if p["employee_id"] == employee.id)


def test_every_employee_lands_in_exactly_one_group(db, api):
    admin = _user(db, full_access_role(db))
    in_buddy = _employee(db, "Buddy", buddy="IN_PROGRESS")
    ready = _employee(db, "Ready")
    core_ready = _employee(db, "CoreReady", certified=True)
    staff_aug = _employee(db, "StaffAug", status="ALLOCATED")
    _allocate(db, staff_aug, line="SPECIALITY")
    staff_aug_cert = _employee(db, "StaffAugCert", certified=True, status="ALLOCATED")
    _allocate(db, staff_aug_cert, line="SPECIALITY", end_date=date.today() + timedelta(days=10))
    core = _employee(db, "Core", certified=True, status="ALLOCATED")
    _allocate(db, core, line="CORE", via_project=True)  # the project's engine decides
    both = _employee(db, "Both", certified=True, status="ALLOCATED")
    _allocate(db, both, line="SPECIALITY")
    _allocate(db, both, line="CORE")  # Core wins
    unknown = _employee(db, "Unknown", status="ALLOCATED")
    _allocate(db, unknown, line=None)
    exited = _employee(db, "Exited", status="EXITED")
    db.add(EmployeeEscalation(tenant_id=1, employee_id=ready.id, reason="Late timesheets"))
    db.commit()

    body = api.get("/api/v1/workforce/overview", headers=_headers(admin)).json()
    expected = {in_buddy: "BENCH_IN_BUDDY", ready: "BENCH_READY", core_ready: "BENCH_CORE_READY",
                staff_aug: "STAFF_AUG", staff_aug_cert: "STAFF_AUG_CORE_CERTIFIED", core: "CORE", both: "CORE",
                unknown: "UNCLASSIFIED"}
    for employee, group in expected.items():
        assert _group_of(body, employee) == group, employee.first_name
    every = [p["employee_id"] for g in body["groups"] for p in g["people"]]
    assert len(every) == len(set(every)) == body["headcount"] == sum(g["count"] for g in body["groups"])
    assert exited.id not in every

    person = {p["employee_id"]: p for g in body["groups"] for p in g["people"]}
    assert person[staff_aug_cert.id]["rolling_off"] is True and person[staff_aug.id]["rolling_off"] is False
    assert person[ready.id]["open_escalations"] == 1
    assert body["flags"]["rolling_off"] >= 1 and body["roll_off_window_days"] == 30


def test_scoped_to_the_viewers_business_units_and_permission(db, api):
    full_access_role(db)  # the tenant and every contract resource
    unit = BusinessUnit(tenant_id=1, name=f"bu-{_uid()}", display_name="Other BU")
    db.add(unit)
    db.flush()
    theirs = _employee(db, "OtherBU", bu_id=unit.id)
    role = RoleTemplate(tenant_id=1, name=f"r-{_uid()}", display_name="BU viewer", hierarchy_level=8,
                        org_level_access=False, enabled=True)
    db.add(role)
    db.flush()
    resource = db.query(Resource).filter_by(tenant_id=1, name="employee-in-bench").one()
    db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=resource.id, tenant_id=1,
                                  can_view=True, can_create=False, can_edit=False, can_delete=False))
    viewer = _user(db, role)
    bare = RoleTemplate(tenant_id=1, name=f"n-{_uid()}", display_name="No access", hierarchy_level=3,
                        org_level_access=False, enabled=True)
    db.add(bare)
    db.flush()
    no_permission = _user(db, bare)
    db.commit()

    response = api.get("/api/v1/workforce/overview", headers=_headers(viewer))
    assert response.status_code == 200, response.text
    assert theirs.id not in [p["employee_id"] for g in response.json()["groups"] for p in g["people"]]
    assert api.get("/api/v1/workforce/overview", headers=_headers(no_permission)).status_code == 403
