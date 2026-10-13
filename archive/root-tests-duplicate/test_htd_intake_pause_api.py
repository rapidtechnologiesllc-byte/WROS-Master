"""
POST /htd-intake/calculate-monthly-metric|check-breach|resume, GET
/htd-intake/status|pause-log -- proves S-359/HRMS-P511 (HTD Intake
Pause Engine: Conversion Rate Breach) end-to-end on real routes.

Throwaway SQLite app, throwaway JWT keys -- never the real database or
real signing keys.
"""
import os
import tempfile
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


def _month(offset_months, day=1):
    today = date.today()
    year = today.year
    month = today.month - offset_months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, day)


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

    from app.api.v1.endpoints.htd_intake_pause import router as htd_router
    from app.core.database import get_db

    app = FastAPI()
    app.include_router(htd_router)
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

    ids = {"tenant_id": tenant.id}
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


def _seed_htd_employee(client, *, htd_start_date, core_certified=False, core_certified_date=None):
    engine = create_engine(client.db_url)
    session = sessionmaker(bind=engine)()
    employee = Employee(
        tenant_id=client.wros_ids["tenant_id"], first_name="HTD", last_name="Trainee",
        email=f"htd{htd_start_date.isoformat()}-{core_certified}@blitzenx.com",
        joining_date=htd_start_date, status="ALLOCATED", htd_track=True,
        htd_start_date=htd_start_date, core_certified=core_certified, core_certified_date=core_certified_date,
    )
    session.add(employee)
    session.commit()
    session.close()
    engine.dispose()


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/htd-intake/status")
    assert resp.status_code in (401, 403)


def test_status_defaults_to_not_paused(client):
    resp = client.get("/htd-intake/status", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["is_paused"] is False


def test_calculate_monthly_metric_insufficient_data_with_no_cohort(client):
    resp = client.post("/htd-intake/calculate-monthly-metric", json={"month": _month(1).isoformat()}, headers=_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["cohort_size"] == 0
    assert body["conversion_rate"] is None


def test_calculate_monthly_metric_computes_rate(client):
    month_start = _month(1)
    # 2 converted (within 400 days), 3 total -> 66.67%
    _seed_htd_employee(client, htd_start_date=month_start, core_certified=True, core_certified_date=month_start + timedelta(days=100))
    _seed_htd_employee(client, htd_start_date=month_start + timedelta(days=1), core_certified=True, core_certified_date=month_start + timedelta(days=200))
    _seed_htd_employee(client, htd_start_date=month_start + timedelta(days=2), core_certified=False)

    resp = client.post("/htd-intake/calculate-monthly-metric", json={"month": month_start.isoformat()}, headers=_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["cohort_size"] == 3
    assert body["converted"] == 2
    assert round(body["conversion_rate"], 2) == 0.67


def test_calculate_monthly_metric_excludes_late_conversion(client):
    month_start = _month(1)
    _seed_htd_employee(client, htd_start_date=month_start, core_certified=True, core_certified_date=month_start + timedelta(days=500))

    resp = client.post("/htd-intake/calculate-monthly-metric", json={"month": month_start.isoformat()}, headers=_auth())
    body = resp.json()
    assert body["converted"] == 0


def test_calculate_monthly_metric_is_idempotent(client):
    month_start = _month(1)
    _seed_htd_employee(client, htd_start_date=month_start, core_certified=True, core_certified_date=month_start + timedelta(days=50))
    client.post("/htd-intake/calculate-monthly-metric", json={"month": month_start.isoformat()}, headers=_auth())
    resp = client.post("/htd-intake/calculate-monthly-metric", json={"month": month_start.isoformat()}, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["cohort_size"] == 1


def test_check_breach_pauses_after_two_consecutive_low_months(client):
    month1 = _month(2)
    month2 = _month(1)
    # Month 1: 1/3 converted (33%)
    _seed_htd_employee(client, htd_start_date=month1, core_certified=True, core_certified_date=month1 + timedelta(days=50))
    _seed_htd_employee(client, htd_start_date=month1 + timedelta(days=1), core_certified=False)
    _seed_htd_employee(client, htd_start_date=month1 + timedelta(days=2), core_certified=False)
    # Month 2: 0/2 converted (0%)
    _seed_htd_employee(client, htd_start_date=month2, core_certified=False)
    _seed_htd_employee(client, htd_start_date=month2 + timedelta(days=1), core_certified=False)

    client.post("/htd-intake/calculate-monthly-metric", json={"month": month1.isoformat()}, headers=_auth())
    client.post("/htd-intake/calculate-monthly-metric", json={"month": month2.isoformat()}, headers=_auth())

    resp = client.post("/htd-intake/check-breach", headers=_auth())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_paused"] is True
    assert "50%" in body["pause_reason"]

    status_resp = client.get("/htd-intake/status", headers=_auth())
    assert status_resp.json()["is_paused"] is True


def test_check_breach_does_not_pause_with_only_one_low_month(client):
    month1 = _month(2)
    month2 = _month(1)
    # Month 1: healthy (2/2 = 100%)
    _seed_htd_employee(client, htd_start_date=month1, core_certified=True, core_certified_date=month1 + timedelta(days=50))
    _seed_htd_employee(client, htd_start_date=month1 + timedelta(days=1), core_certified=True, core_certified_date=month1 + timedelta(days=60))
    # Month 2: breach (0/2 = 0%)
    _seed_htd_employee(client, htd_start_date=month2, core_certified=False)
    _seed_htd_employee(client, htd_start_date=month2 + timedelta(days=1), core_certified=False)

    client.post("/htd-intake/calculate-monthly-metric", json={"month": month1.isoformat()}, headers=_auth())
    client.post("/htd-intake/calculate-monthly-metric", json={"month": month2.isoformat()}, headers=_auth())

    resp = client.post("/htd-intake/check-breach", headers=_auth())
    assert resp.json()["is_paused"] is False


def test_check_breach_is_idempotent_no_duplicate_pause_log(client):
    month1 = _month(2)
    month2 = _month(1)
    _seed_htd_employee(client, htd_start_date=month1, core_certified=False)
    _seed_htd_employee(client, htd_start_date=month2, core_certified=False)
    client.post("/htd-intake/calculate-monthly-metric", json={"month": month1.isoformat()}, headers=_auth())
    client.post("/htd-intake/calculate-monthly-metric", json={"month": month2.isoformat()}, headers=_auth())

    client.post("/htd-intake/check-breach", headers=_auth())
    client.post("/htd-intake/check-breach", headers=_auth())

    log_resp = client.get("/htd-intake/pause-log", headers=_auth())
    paused_entries = [e for e in log_resp.json()["entries"] if e["action"] == "PAUSED"]
    assert len(paused_entries) == 1


def test_resume_requires_200_char_fields(client):
    resp = client.post(
        "/htd-intake/resume",
        json={"audit_findings": "too short", "corrective_actions": "too short"},
        headers=_auth(),
    )
    assert resp.status_code == 422


LONG_TEXT = "A" * 200


def test_resume_succeeds_with_valid_audit(client):
    month1 = _month(2)
    month2 = _month(1)
    _seed_htd_employee(client, htd_start_date=month1, core_certified=False)
    _seed_htd_employee(client, htd_start_date=month2, core_certified=False)
    client.post("/htd-intake/calculate-monthly-metric", json={"month": month1.isoformat()}, headers=_auth())
    client.post("/htd-intake/calculate-monthly-metric", json={"month": month2.isoformat()}, headers=_auth())
    client.post("/htd-intake/check-breach", headers=_auth())

    resp = client.post(
        "/htd-intake/resume",
        json={"audit_findings": LONG_TEXT, "corrective_actions": LONG_TEXT},
        headers=_auth(),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_paused"] is False

    log_resp = client.get("/htd-intake/pause-log", headers=_auth())
    resumed_entries = [e for e in log_resp.json()["entries"] if e["action"] == "RESUMED"]
    assert len(resumed_entries) == 1
    assert resumed_entries[0]["resumed_by"] == "U-ADMIN"
