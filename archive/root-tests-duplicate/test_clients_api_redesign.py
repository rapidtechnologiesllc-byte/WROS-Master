"""
2026-08-06 Client Management redesign, API-level proof: hiring_manager/
timesheet_approver were originally required at creation but that was
flagged 2026-08-07 as a real UX blocker (Avinash, live testing against
a real JobDiva client record: contacts belong on their own tab, not
gating company creation) -- they're now optional at creation and
captured via POST /clients/{client_id}/contacts instead, matching
client_service.STATUSES_REQUIRING_CONTACT's existing enforcement point
(a client still can't go status=ACTIVE without at least one contact).

2026-08-07 further: website is also now optional (prospect clients
created on-the-fly, e.g., from MyExpensesScreen, may not have a
website yet -- can be added later via PATCH /clients/{id}).

Also covers GET /clients/business-units/{id}/assignments (BU Head + HR
Manager resolution for Job-creation auto-assignment).

Throwaway SQLite, throwaway JWT keys -- never the real database.
"""
import os
import tempfile
from datetime import date

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
from app.models.base import Base
from app.models.employee import Employee
from app.models.rbac_template import BusinessUnit, Role
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.rbac_service_template import RBACService
import app.models  # noqa: F401


@pytest.fixture()
def throwaway_jwt_keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setattr(security, "PRIVATE_KEY", private_pem)
    monkeypatch.setattr(security, "PUBLIC_KEY", public_pem)


@pytest.fixture()
def client(throwaway_jwt_keys):
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.api.v1.endpoints.clients import router as clients_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(clients_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    RBACService.seed_roles_and_permissions(db)

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    axion = BusinessUnit(name="Axion")
    db.add(axion)
    db.commit()

    partner_role = db.query(Role).filter(Role.name == "Partner").first()
    db.add(Users(
        UserID="U-TROY", UserRole="Partner", UserEmail="troy@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id, role_id=partner_role.id, business_unit_id=axion.id,
    ))
    db.commit()

    hemant_employee = Employee(
        tenant_id=tenant.id, first_name="Hemant", last_name="BuHead",
        email="hemant@blitzenx.com", joining_date=date(2024, 1, 1),
    )
    hr_employee = Employee(
        tenant_id=tenant.id, first_name="HR", last_name="Person",
        email="hr@blitzenx.com", joining_date=date(2024, 1, 1),
    )
    db.add_all([hemant_employee, hr_employee])
    db.commit()
    axion.bu_head_employee_id = hemant_employee.id
    axion.hr_manager_employee_id = hr_employee.id
    db.add(axion)
    db.add(Users(
        UserID="U-HEMANT", UserRole="BU Head", UserEmail="hemant@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id, business_unit_id=axion.id,
    ))
    db.add(Users(
        UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com",
        UserPassword="h", tenant_id=tenant.id, business_unit_id=axion.id,
    ))
    db.commit()

    ids = {"axion_id": axion.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)


def _troy_auth():
    token = security.create_access_token(data={"sub": "troy@blitzenx.com", "type": "internal", "name": "troy@blitzenx.com"})
    return {"Authorization": f"Bearer {token}"}


def test_create_client_without_website_succeeds(client):
    # 2026-08-07: website is now optional (prospect clients created on-the-fly)
    resp = client.post(
        "/clients", headers=_troy_auth(),
        json={
            "company_name": "Builders Insurance", "line_type": "CORE",
        },
    )
    assert resp.status_code == 201, resp.text


def test_create_client_without_contacts_succeeds(client):
    resp = client.post(
        "/clients", headers=_troy_auth(),
        json={"company_name": "Builders Insurance", "line_type": "CORE", "website": "builders.com"},
    )
    assert resp.status_code == 201, resp.text


def test_create_client_with_all_required_fields_succeeds(client):
    resp = client.post(
        "/clients", headers=_troy_auth(),
        json={
            "company_name": "Builders Insurance", "line_type": "CORE", "website": "builders.com",
            "hiring_manager": {"name": "Jane", "email": "jane@builders.com"},
            "timesheet_approver": {"name": "Sam", "email": "sam@builders.com"},
        },
    )
    assert resp.status_code == 201, resp.text


def test_add_contact_to_client_created_without_contacts(client):
    create_resp = client.post(
        "/clients", headers=_troy_auth(),
        json={"company_name": "Builders Insurance", "line_type": "CORE", "website": "builders.com"},
    )
    client_id = create_resp.json()["id"]

    list_resp = client.get(f"/clients/{client_id}/contacts", headers=_troy_auth())
    assert list_resp.status_code == 200, list_resp.text
    assert list_resp.json()["contacts"] == []

    add_resp = client.post(
        f"/clients/{client_id}/contacts", headers=_troy_auth(),
        json={"name": "Jane", "email": "jane@builders.com", "role_type": "HIRING_MANAGER"},
    )
    assert add_resp.status_code == 201, add_resp.text
    assert add_resp.json()["role_type"] == "HIRING_MANAGER"

    list_resp = client.get(f"/clients/{client_id}/contacts", headers=_troy_auth())
    assert len(list_resp.json()["contacts"]) == 1


def test_add_contact_duplicate_email_rejected(client):
    create_resp = client.post(
        "/clients", headers=_troy_auth(),
        json={"company_name": "Builders Insurance", "line_type": "CORE", "website": "builders.com"},
    )
    client_id = create_resp.json()["id"]
    client.post(
        f"/clients/{client_id}/contacts", headers=_troy_auth(),
        json={"name": "Jane", "email": "jane@builders.com", "role_type": "HIRING_MANAGER"},
    )
    dup_resp = client.post(
        f"/clients/{client_id}/contacts", headers=_troy_auth(),
        json={"name": "Jane Two", "email": "jane@builders.com", "role_type": "TIMESHEET_APPROVER"},
    )
    assert dup_resp.status_code == 409


def test_add_contact_invalid_role_type_rejected(client):
    create_resp = client.post(
        "/clients", headers=_troy_auth(),
        json={"company_name": "Builders Insurance", "line_type": "CORE", "website": "builders.com"},
    )
    client_id = create_resp.json()["id"]
    resp = client.post(
        f"/clients/{client_id}/contacts", headers=_troy_auth(),
        json={"name": "Jane", "email": "jane@builders.com", "role_type": "NOT_A_REAL_ROLE"},
    )
    assert resp.status_code == 400


def test_business_unit_assignments_resolves_bu_head_and_hr(client):
    ids = client.wros_ids
    resp = client.get(f"/clients/business-units/{ids['axion_id']}/assignments", headers=_troy_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["bu_head"]["user_id"] == "U-HEMANT"
    assert body["hr_manager"]["user_id"] == "U-HR"
