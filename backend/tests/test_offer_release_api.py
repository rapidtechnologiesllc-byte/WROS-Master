"""
import logging
POST /offer-letter/release/{offer_id} -- S-054/HRMS-0454.

Real HTTP-level proof: BR-01 (readiness re-checked at release, HTTP 409
with blockers if not ready) and AC-8 (Recruiter gets 403 -- the new,
narrower offer.readiness_check permission, not the broader offer.manage
which a real pre-existing RBAC inconsistency still grants Recruiter).

Throwaway SQLite app, throwaway JWT keys, real RBAC seed.
"""
import os
import tempfile
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.core.security as security
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.tenant import Tenant
from app.models.user import Users
import app.models  # noqa: F401 -- registers every model on Base.metadata

@pytest.fixture(autouse=True)
def _fake_whatsapp_number(monkeypatch):
    import app.services.whatsapp_routing_service as wr_svc
    monkeypatch.setattr(wr_svc, "DEFAULT_WHATSAPP_NUMBER", "+15550009999")

@pytest.fixture()
def throwaway_jwt_keys(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption()).decode()
    public_pem = key.public_key().public_bytes(encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()
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

    from app.api.v1.endpoints.offer_letters import router as offer_letters_router
    from app.core.database import get_db
    from app.services.rbac_service_template import RBACService
    from app.models.rbac_template import Role

    app = FastAPI()
    app.include_router(offer_letters_router)
    app.dependency_overrides[get_db] = override_get_db

    db = TestSessionLocal()
    RBACService.seed_roles_and_permissions(db)
    tenant = Tenant(name="BlitzenX")
    db.add(tenant)
    db.commit()

    super_role = db.query(Role).filter_by(name="Super User").first()
    hr_role = db.query(Role).filter_by(name="HR Manager").first()
    rec_role = db.query(Role).filter_by(name="Recruiter").first()

    db.add_all([
        Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword=get_password_hash("x"), tenant_id=tenant.id, role_id=super_role.id if super_role else None),
        Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword=get_password_hash("x"), tenant_id=tenant.id, role_id=hr_role.id if hr_role else None),
        Users(UserID="U-REC", UserRole="Recruiter", UserEmail="rec@blitzenx.com", UserPassword=get_password_hash("x"), tenant_id=tenant.id, role_id=rec_role.id if rec_role else None),
    ])
    db.commit()

    from app.models.candidate import Candidate
    from app.models.candidate_ai import CandidateConversation
    from app.models.consent import ConsentRecord
    from app.models.offer_letter import OfferLetter

    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", tenant_id=tenant.id, total_experience_months=72, employment_type="W2_FULLTIME")
    db.add(candidate)
    db.commit()
    db.add(CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp"))
    db.add(ConsentRecord(subject_type="candidate", subject_id="C-1", consent_type="whatsapp_outreach", consent_given=True, captured_by="candidate_self_service"))

    not_ready_offer = OfferLetter(candidate_id="C-1", position="Sr. Dev", salary="24 LPA", joining_date=date(2026, 9, 1), offer_expire_date=date(2026, 8, 20), offer_status="AwaitingApproval", approval_status="Approved")
    db.add(not_ready_offer)
    db.commit()
    not_ready_offer_id = not_ready_offer.id

    db.close()

    test_client = TestClient(app)
    test_client.not_ready_offer_id = not_ready_offer_id
    try:
        yield test_client
    finally:
        engine.dispose()
        os.remove(db_path)

def _token_for(email, role):
    return security.create_access_token(data={"sub": email, "type": role, "name": email})

def test_recruiter_gets_403(client):
    resp = client.post(
        f"/offer-letter/release/{client.not_ready_offer_id}",
        headers={"Authorization": f"Bearer {_token_for('rec@blitzenx.com', 'Recruiter')}"},
    )
    assert resp.status_code == 403

def test_not_ready_candidate_gets_409_with_blockers(client):
    """C-1 has no L1/L2 interviews at all -- BR-01's re-check must
    block release even though approval_status='Approved'."""
    resp = client.post(
        f"/offer-letter/release/{client.not_ready_offer_id}",
        headers={"Authorization": f"Bearer {_token_for('hr@blitzenx.com', 'HR Manager')}"},
    )
    assert resp.status_code == 409
    body = resp.json()["detail"]
    assert body["blockers"]  # non-empty
    assert any("L1" in b for b in body["blockers"])

def test_ready_candidate_release_succeeds_and_notifies(client):
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        from app.models.demand import Demand
        from app.models.client import Client
        from app.models.employee import Employee
        from app.models.interview_pipeline import DemandInterviewPanel, SubmissionInterview
        from app.services.interview_service import assign_panel_member, create_interview
        from app.services.submission_service import create_submission

        client_row = Client(tenant_id=1, company_name="Acme Insurance")
        db.add(client_row)
        db.commit()
        demand = Demand(tenant_id=1, client_id=client_row.id, job_title="Sr. Dev", required_skills="[]", min_experience_years=5.0, work_location="REMOTE", status="OPEN")
        db.add(demand)
        db.commit()

        candidate = db.query(Candidate).filter(Candidate.candidateID == "C-1").first()
        employee = Employee(tenant_id=1, candidate_id="C-1", first_name="Priya", last_name="S", email="c1@example.com", joining_date=date(2026, 1, 1), status="BENCH")
        db.add(employee)
        db.commit()
        submission = create_submission(db, tenant_id=1, demand=demand, candidate=candidate, submitted_by_user_id="U-HR")
        db.commit()

        interviewer_employee = Employee(tenant_id=1, first_name="Tom", last_name="Kumar", email="tom@blitzenx.com", joining_date=date(2025, 1, 1), status="ACTIVE", wros_user_id="U-INT-1")
        db.add(interviewer_employee)
        db.commit()
        interviewer_user = Users(UserID="U-INT-1", UserRole="Employee", UserEmail="tom@blitzenx.com", UserPassword=get_password_hash("x"), tenant_id=1, timezone="America/Chicago")
        db.add(interviewer_user)
        db.commit()
        panel = assign_panel_member(db, tenant_id=1, demand_id=demand.id, employee=interviewer_employee, interview_level="L1")
        db.commit()

        l1 = create_interview(db, tenant_id=1, submission=submission, level="L1", panel=panel, scheduled_at=datetime.utcnow() - timedelta(days=1))
        db.commit()
        l1.outcome = "PASS"
        db.add(l1)
        db.commit()
        l2 = create_interview(db, tenant_id=1, submission=submission, level="L2", panel=panel, scheduled_at=datetime.utcnow() - timedelta(days=1))
        db.commit()
        l2.outcome = "PASS"
        db.add(l2)
        db.commit()

        offer = OfferLetter(candidate_id="C-1", job_id=None, position="Sr. Dev", salary="24 LPA", joining_date=date(2026, 9, 1), offer_expire_date=date(2026, 8, 20), offer_status="AwaitingApproval", approval_status="Approved")
        db.add(offer)
        db.commit()
        offer_id = offer.id
    finally:
        db.close()

    with patch("app.services.offer_release_notification_service.EmailService.send_email", return_value={"status": "success"}):
        resp = client.post(
            f"/offer-letter/release/{offer_id}",
            headers={"Authorization": f"Bearer {_token_for('hr@blitzenx.com', 'HR Manager')}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["offer_status"] == "Released"
