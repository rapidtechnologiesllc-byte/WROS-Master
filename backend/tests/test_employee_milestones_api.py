"""
POST /employee-milestones, GET /employee-milestones/employee/{id},
POST /employee-milestones/{id}/complete, POST /employee-milestones/
scan-overdue -- proves S-356/HRMS-0517 (Employee Milestone Tracker:
Personal, Project & Org) end-to-end on real routes. Also proves the
auto-write into employee_performance_events (HRMS-0515) on completion
(AC-3, scored 100 on-time / 70 late) and on overdue detection (AC-4).

real signing keys.
"""
import os
from datetime import date, timedelta

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
from app.models.tenant import Tenant
from app.models.user import Users
import app.models  # noqa: F401 -- registers every model on Base.metadata

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
    engine = create_engine(f"sqlite:///{db_path}")

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    from app.api.v1.endpoints.employee_milestones import router as milestones_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(milestones_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    from app.core.security import get_password_hash

    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    db.add(Users(
        UserID="U-ADMIN", UserRole="Admin", UserEmail="admin@blitzenx.com",
        UserPassword=get_password_hash("x"), tenant_id=tenant.id,
    ))
    db.commit()

    employee = Employee(
        tenant_id=tenant.id, first_name="Sam", last_name="Lee", email="sam@blitzenx.com",
        joining_date=date(2025, 1, 1), status="ALLOCATED",
    )
    db.add(employee)
    db.commit()

    ids = {"tenant_id": tenant.id, "employee_id": employee.id}
    db.close()

    test_client = TestClient(app)
    test_client.wros_ids = ids
    test_client.db_url = f"sqlite:///{db_path}"
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)

def _token_for(email, role="Admin"):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})

def _auth():
    return {"Authorization": f"Bearer {_token_for('admin@blitzenx.com')}"}

def test_unauthenticated_request_is_rejected(client):
    resp = client.get(f"/employee-milestones/employee/{client.wros_ids['employee_id']}")
    assert resp.status_code in (401, 403)

def test_create_personal_milestone(client):
    ids = client.wros_ids
    resp = client.post(
        "/employee-milestones",
        json={
            "milestone_type": "PERSONAL", "title": "Onboarding Checklist Complete",
            "target_date": (date.today() + timedelta(days=14)).isoformat(), "employee_id": ids["employee_id"],
        },
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "PENDING"

def test_create_personal_milestone_requires_employee_id(client):
    resp = client.post(
        "/employee-milestones",
        json={"milestone_type": "PERSONAL", "title": "No Employee", "target_date": date.today().isoformat()},
        headers=_auth(),
    )
    assert resp.status_code == 422

def test_list_employee_milestones(client):
    ids = client.wros_ids
    client.post(
        "/employee-milestones",
        json={
            "milestone_type": "ORG", "title": "Q1 OKR", "target_date": (date.today() + timedelta(days=90)).isoformat(),
            "employee_id": ids["employee_id"],
        },
        headers=_auth(),
    )
    resp = client.get(f"/employee-milestones/employee/{ids['employee_id']}", headers=_auth())
    assert resp.status_code == 200
    assert len(resp.json()["milestones"]) == 1

def test_complete_milestone_on_time_writes_score_100(client):
    ids = client.wros_ids
    milestone = client.post(
        "/employee-milestones",
        json={
            "milestone_type": "PERSONAL", "title": "Cert Attempt",
            "target_date": (date.today() + timedelta(days=5)).isoformat(), "employee_id": ids["employee_id"],
        },
        headers=_auth(),
    ).json()

    resp = client.post(f"/employee-milestones/{milestone['id']}/complete", json={}, headers=_auth())
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "COMPLETED"
    assert resp.json()["completed_date"] == date.today().isoformat()

    from app.models.performance_store import EmployeePerformanceEvent
    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    events = session.query(EmployeePerformanceEvent).filter(
        EmployeePerformanceEvent.employee_id == ids["employee_id"],
        EmployeePerformanceEvent.event_type == "MILESTONE_COMPLETED",
    ).all()
    session.close()
    engine.dispose()
    assert len(events) == 1
    import json
    data = json.loads(events[0].event_data)
    assert data["score"] == 100
    assert data["on_time"] is True

def test_complete_milestone_late_writes_score_70(client):
    ids = client.wros_ids
    milestone = client.post(
        "/employee-milestones",
        json={
            "milestone_type": "PERSONAL", "title": "Late Milestone",
            "target_date": (date.today() - timedelta(days=3)).isoformat(), "employee_id": ids["employee_id"],
        },
        headers=_auth(),
    ).json()

    client.post(f"/employee-milestones/{milestone['id']}/complete", json={}, headers=_auth())

    from app.models.performance_store import EmployeePerformanceEvent
    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    events = session.query(EmployeePerformanceEvent).filter(
        EmployeePerformanceEvent.employee_id == ids["employee_id"],
        EmployeePerformanceEvent.event_type == "MILESTONE_COMPLETED",
    ).all()
    session.close()
    engine.dispose()
    import json
    assert json.loads(events[0].event_data)["score"] == 70

def test_complete_already_complete_milestone_is_409(client):
    ids = client.wros_ids
    milestone = client.post(
        "/employee-milestones",
        json={
            "milestone_type": "PERSONAL", "title": "M", "target_date": date.today().isoformat(),
            "employee_id": ids["employee_id"],
        },
        headers=_auth(),
    ).json()
    client.post(f"/employee-milestones/{milestone['id']}/complete", json={}, headers=_auth())
    resp = client.post(f"/employee-milestones/{milestone['id']}/complete", json={}, headers=_auth())
    assert resp.status_code == 409

def test_complete_milestone_404_for_unknown_id(client):
    resp = client.post("/employee-milestones/does-not-exist/complete", json={}, headers=_auth())
    assert resp.status_code == 404

def test_scan_overdue_flips_status_and_writes_negative_event(client):
    ids = client.wros_ids
    client.post(
        "/employee-milestones",
        json={
            "milestone_type": "PERSONAL", "title": "Missed Milestone",
            "target_date": (date.today() - timedelta(days=10)).isoformat(), "employee_id": ids["employee_id"],
        },
        headers=_auth(),
    )

    resp = client.post("/employee-milestones/scan-overdue", headers=_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["overdue"]) == 1
    assert body["overdue"][0]["status"] == "OVERDUE"

    from app.models.performance_store import EmployeePerformanceEvent
    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    events = session.query(EmployeePerformanceEvent).filter(
        EmployeePerformanceEvent.employee_id == ids["employee_id"],
        EmployeePerformanceEvent.event_type == "MILESTONE_OVERDUE",
    ).all()
    session.close()
    engine.dispose()
    assert len(events) == 1

def test_scan_overdue_is_idempotent(client):
    ids = client.wros_ids
    client.post(
        "/employee-milestones",
        json={
            "milestone_type": "PERSONAL", "title": "Missed Milestone",
            "target_date": (date.today() - timedelta(days=10)).isoformat(), "employee_id": ids["employee_id"],
        },
        headers=_auth(),
    )
    first = client.post("/employee-milestones/scan-overdue", headers=_auth())
    second = client.post("/employee-milestones/scan-overdue", headers=_auth())
    assert len(first.json()["overdue"]) == 1
    assert len(second.json()["overdue"]) == 0

def test_scan_overdue_skips_future_milestones(client):
    ids = client.wros_ids
    client.post(
        "/employee-milestones",
        json={
            "milestone_type": "PERSONAL", "title": "Future Milestone",
            "target_date": (date.today() + timedelta(days=10)).isoformat(), "employee_id": ids["employee_id"],
        },
        headers=_auth(),
    )
    resp = client.post("/employee-milestones/scan-overdue", headers=_auth())
    assert resp.json()["overdue"] == []
