"""
2026-08-06 Client Management redesign, API-level proof: website/
hiring_manager/timesheet_approver are required by the real POST /clients
schema (not just optional service-layer params -- see client_service.
create_client()'s own docstring for why validation lives at this layer),
and GET /clients/business-units/{id}/assignments resolves BU Head + HR
Manager for Job-creation auto-assignment.

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
from app.models.rbac import BusinessUnit, Role
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.rbac_service import RBACService
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


def test_create_client_requires_website(client):
    resp = client.post(
        "/clients", headers=_troy_auth(),
        json={
            "company_name": "Builders Insurance", "line_type": "CORE",
            "hiring_manager": {"name": "Jane", "email": "jane@builders.com"},
            "timesheet_approver": {"name": "Sam", "email": "sam@builders.com"},
        },
    )
    assert resp.status_code == 422


def test_create_client_requires_hiring_manager_and_timesheet_approver(client):
    resp = client.post(
        "/clients", headers=_troy_auth(),
        json={"company_name": "Builders Insurance", "line_type": "CORE", "website": "builders.com"},
    )
    assert resp.status_code == 422


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


def test_business_unit_assignments_resolves_bu_head_and_hr(client):
    ids = client.wros_ids
    resp = client.get(f"/clients/business-units/{ids['axion_id']}/assignments", headers=_troy_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["bu_head"]["user_id"] == "U-HEMANT"
    assert body["hr_manager"]["user_id"] == "U-HR"
