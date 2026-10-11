"""After an accepted offer the system runs onboarding by itself: documents requested and the
candidate emailed a portal link; uploads arrive through the portal; HR verifies; consent
starts BGV; a BGV pass plus the joining date makes the candidate a BENCH employee with a
login -- never allocated to a client at that point. Nothing reaches a client before."""
import uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models.background_verification import BackgroundVerification
from app.models.business_unit import BusinessUnit
from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.interview_verdict import InterviewRoundVerdict
from app.models.offer_letter import OfferLetter
from app.models.pipeline_email import PipelineEmail
from app.models.preboarding_document import PreboardingDocument
from app.models.role_template import Module, Resource, RoleTemplate
from app.models.tenant import Tenant
from app.models.user import InterviewPanel, Users
from app.services import hiring_pipeline_service as hp
from app.services.message_handlers.send_pipeline_email_handler import SendPipelineEmailHandler
from app.services.submission_service import check_hiring_pipeline_rule
from tests.hiring_fixtures import full_access_role


def _uid():
    return uuid.uuid4().hex[:8]


class FakeMailbox:
    def __init__(self):
        self.drafts, self.sent = {}, []

    def create_draft(self, to, subject, html, ref):
        mid = f"g-{_uid()}"
        self.drafts[mid] = {"to": to, "subject": subject, "html": html}
        return mid, None, None

    def is_draft(self, mid):
        return mid not in self.sent

    def send(self, mid):
        self.sent.append(mid)


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
def queued():
    calls = []

    def enqueue_once(task_name, task_id, data, tenant_id, delay_seconds=0):
        if any(c[1] == task_id for c in calls):
            return False
        calls.append((task_name, task_id, data))
        return True

    with patch("app.services.thunder_mail.cadence_service.enqueue_once", side_effect=enqueue_once):
        yield calls


@pytest.fixture
def client(db, queued):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db

    async def stored(file, document_type, user, db_):
        return SimpleNamespace(sharepoint_url=f"https://files.example/{file.filename}")

    with patch("app.api.v1.endpoints.documents._upload_document_helper", side_effect=stored):
        yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def world(db):
    from app.core.db_contract import LEADERSHIP_ROLES, ensure_role

    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="BlitzenX"))
        db.flush()
    role = full_access_role(db)
    db.add(role)
    module = db.query(Module).filter_by(name="Personal", tenant_id=1).first() or \
        Module(name="Personal", display_name="Personal", tenant_id=1)
    db.add(module)
    db.flush()
    for name in LEADERSHIP_ROLES["Employee"]["permissions"]["vce"]:
        if db.query(Resource).filter_by(name=name).first() is None:
            db.add(Resource(module_id=module.id, name=name, display_name=name, tenant_id=1))
    db.flush()
    ensure_role(db, "Employee", LEADERSHIP_ROLES["Employee"])
    hr = Users(UserID=f"HR-{_uid()}", UserName="HR", UserEmail=f"hr{_uid()}@blitzenx.com", UserPassword="x",
               UserRole="admin", tenant_id=1, role_template_id=role.id, password_reset_required=False)
    unit = BusinessUnit(name=f"bu-{_uid()}", display_name="BU")
    db.add_all([hr, unit])
    db.flush()
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"ria{_uid()}@example.com", candidatePassword="x",
                          candidateFirstName="Ria", candidateLastName="Das", tenant_id=1, thunder_enabled=True,
                          associated_bu_id=unit.id, candidateMobile="+919800000000", total_experience_months=72)
    db.add(candidate)
    db.flush()
    db.add(CandidateStatus(candidateID=candidate.candidateID, status="Active", piplineStatus="Hired",
                           thunder_assigned_at=datetime.utcnow()))
    for level in ("L1", "L2"):
        panel = InterviewPanel(candidate_id=candidate.candidateID, round_name=level)
        db.add(panel)
        db.flush()
        db.add(InterviewRoundVerdict(panel_id=panel.id, candidate_id=candidate.candidateID, level=level,
                                     verdict="PASS", source="MANUAL"))
    offer = OfferLetter(candidate_id=candidate.candidateID, position="Data Engineer", salary="1800000",
                        joining_date=date.today() + timedelta(days=10), offer_expire_date=date.today() + timedelta(days=5),
                        offer_status="Accepted", responded_at=datetime.utcnow(), created_by=hr.UserID)
    db.add(offer)
    db.commit()
    return SimpleNamespace(hr=hr, candidate=candidate, offer=offer, unit=unit)


def _staff(user):
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": user.role_template_id})}


def _cand(candidate):
    return {"Authorization": "Bearer " + create_access_token({"sub": candidate.candidateID, "type": "candidate",
                                                              "tenant_id": 1})}


def _run_actions(db, queued):
    """Plays the queue: every stage action and pipeline email queued so far."""
    for task_name, task_id, data in list(queued):
        if task_name == hp.STAGE_ACTION_TASK and (task_id, "done") not in queued:
            hp.run_stage_action(db, data["pipeline_id"], data["stage"])
            queued.append((task_id, "done", None))


def test_onboarding_runs_itself_from_acceptance_to_the_bench(client, db, world, queued):
    w = world
    pipeline = hp.evaluate_and_act(db, w.candidate.candidateID, "offer")
    assert pipeline.stage == "ONBOARDING"
    _run_actions(db, queued)

    # documents requested (India: PAN too), BGV record created, onboarding email queued once
    docs = db.query(PreboardingDocument).filter_by(candidate_id=w.candidate.candidateID).all()
    assert {d.document_type for d in docs} >= {"ID_PROOF", "PAN_CARD", "BACKGROUND_CHECK_CONSENT"}
    bgv = db.query(BackgroundVerification).filter_by(candidate_id=w.candidate.candidateID).one()
    assert bgv.status == "NOT_STARTED"
    email = db.query(PipelineEmail).filter_by(candidate_id=w.candidate.candidateID).one()
    assert [q for q in queued if q[0] == "send_pipeline_email"] == [
        ("send_pipeline_email", email.id, {"email_id": email.id, "candidate_id": w.candidate.candidateID})]
    mailbox = FakeMailbox()
    with patch("app.services.message_handlers.send_pipeline_email_handler.GraphMailbox", side_effect=AssertionError):
        SendPipelineEmailHandler.process(SimpleNamespace(id=email.id, payload={"email_id": email.id}), db, mailbox=mailbox)
    sent = list(mailbox.drafts.values())[0]
    assert sent["to"] == w.candidate.candidateEmail and "/candidate/" in sent["html"] and "PAN" in sent["html"]
    SendPipelineEmailHandler.process(SimpleNamespace(id=email.id, payload={"email_id": email.id}), db, mailbox=mailbox)
    assert len(mailbox.sent) == 1  # a retry never sends twice

    # the candidate sees and uploads every document on the portal; consent starts BGV
    listed = client.get("/api/v1/portal/onboarding", headers=_cand(w.candidate)).json()
    assert len(listed["documents"]) == len(docs)
    for doc in docs:
        up = client.post(f"/api/v1/portal/onboarding/documents/{doc.id}", headers=_cand(w.candidate),
                         files={"file": (f"{doc.document_type}.pdf", b"%PDF-1.4", "application/pdf")})
        assert up.status_code == 200 and up.json()["status"] == "RECEIVED", up.text
    db.expire_all()
    assert db.get(BackgroundVerification, bgv.id).status == "IN_PROGRESS"

    # HR verifies; the pipeline moves to BGV
    for doc in docs:
        reviewed = client.post(f"/api/v1/hiring-pipeline/preboarding-documents/{doc.id}/review",
                               headers=_staff(w.hr), json={"decision": "verified"})
        assert reviewed.status_code == 200, reviewed.text
    assert hp.evaluate_and_act(db, w.candidate.candidateID, "docs").stage == "BGV"

    # BGV passes; joining date still ahead -> waits on the BGV stage, no employee yet
    verdict = client.post(f"/api/v1/bgv/{bgv.id}/verdict", headers=_staff(w.hr), json={"verdict": "passed"})
    assert verdict.status_code == 200, verdict.text
    pipeline = hp.evaluate_and_act(db, w.candidate.candidateID, "bgv")
    assert pipeline.stage == "BGV" and pipeline.blockers[0].startswith("BGV cleared; joins the bench on the joining date")
    assert not [q for q in queued if q[0] == hp.BENCH_TASK]

    # joining date arrives: the sweep converts them -- BENCH employee, Employee login, no client allocation
    w.offer.joining_date = date.today()
    pipeline.last_evaluated_at = datetime.utcnow() - timedelta(hours=2)
    db.commit()
    hp.run_pipeline_sweep(db)
    bench = [q for q in queued if q[0] == hp.BENCH_TASK]
    assert len(bench) == 1
    outcome = hp.convert_to_bench(db, bench[0][2]["pipeline_id"])
    assert outcome.startswith("employee"), outcome
    employee = db.query(Employee).filter_by(candidate_id=w.candidate.candidateID).one()
    user = db.query(Users).filter_by(UserID=employee.wros_user_id).one()
    assert employee.status == "BENCH" and employee.bu_id == w.unit.id
    assert db.query(RoleTemplate).filter_by(id=user.role_template_id).one().name == "Employee"
    assert db.query(EmployeeAllocation).filter_by(employee_id=employee.id).count() == 0
    assert any(q[0] == "send_account_email" and q[2]["user_id"] == user.UserID for q in queued)
    assert hp.evaluate_and_act(db, w.candidate.candidateID, "check").stage == "BENCH"
    assert check_hiring_pipeline_rule(db, w.candidate.candidateID) == {"allowed": True}
    # converting twice does nothing
    assert hp.convert_to_bench(db, pipeline.id).startswith("skipped")


def test_nothing_reaches_a_client_before_the_bench(db, world, queued):
    rule = check_hiring_pipeline_rule(db, world.candidate.candidateID)
    assert rule["allowed"] is False and rule["error"] == "PIPELINE_INCOMPLETE" and rule["stage"] == "ONBOARDING"


def test_bgv_failure_rejects_and_webhook_needs_the_secret(client, db, world, queued, monkeypatch):
    w = world
    hp.evaluate_and_act(db, w.candidate.candidateID, "offer")
    _run_actions(db, queued)
    bgv = db.query(BackgroundVerification).filter_by(candidate_id=w.candidate.candidateID).one()
    # no consent yet: a verdict is refused
    assert client.post(f"/api/v1/bgv/{bgv.id}/verdict", headers=_staff(w.hr), json={"verdict": "PASSED"}).status_code == 409
    consent = db.query(PreboardingDocument).filter_by(candidate_id=w.candidate.candidateID,
                                                      document_type="BACKGROUND_CHECK_CONSENT").one()
    client.post(f"/api/v1/portal/onboarding/documents/{consent.id}", headers=_cand(w.candidate),
                files={"file": ("consent.pdf", b"%PDF", "application/pdf")})
    started = client.post(f"/api/v1/bgv/{bgv.id}/start", headers=_staff(w.hr),
                          json={"vendor_name": "AuthBridge", "vendor_reference": f"AB-{_uid()}"})
    assert started.status_code == 200 and started.json()["status"] == "IN_PROGRESS"
    ref = started.json()["vendor_reference"]
    monkeypatch.setenv("WEBHOOK_SHARED_SECRET", "s3cret-value")
    body = {"vendor_reference": ref, "status": "FAILED"}
    assert client.post("/api/v1/bgv/webhook/authbridge", json=body, headers={"X-Webhook-Secret": "nope"}).status_code == 401
    ok = client.post("/api/v1/bgv/webhook/authbridge", json=body, headers={"X-Webhook-Secret": "s3cret-value"})
    assert ok.status_code == 200 and ok.json()["status"] == "FAILED"
    pipeline = hp.evaluate_and_act(db, w.candidate.candidateID, "bgv")
    assert pipeline.stage == "REJECTED" and pipeline.blockers == ["background verification failed"]


def test_waiving_bgv_needs_a_reason_and_hr_cannot_verify_an_unuploaded_document(client, db, world, queued):
    w = world
    hp.evaluate_and_act(db, w.candidate.candidateID, "offer")
    _run_actions(db, queued)
    bgv = db.query(BackgroundVerification).filter_by(candidate_id=w.candidate.candidateID).one()
    assert client.post(f"/api/v1/bgv/{bgv.id}/waive", headers=_staff(w.hr), json={"reason": " "}).status_code == 409
    waived = client.post(f"/api/v1/bgv/{bgv.id}/waive", headers=_staff(w.hr), json={"reason": "Rehire, cleared 2025"})
    assert waived.status_code == 200 and waived.json()["status"] == "WAIVED"
    doc = db.query(PreboardingDocument).filter_by(candidate_id=w.candidate.candidateID).first()
    early = client.post(f"/api/v1/hiring-pipeline/preboarding-documents/{doc.id}/review", headers=_staff(w.hr),
                        json={"decision": "VERIFIED"})
    assert early.status_code == 400
    # another candidate can't upload into this candidate's document
    other = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"o{_uid()}@example.com", candidatePassword="x",
                      candidateFirstName="O", candidateLastName="X", tenant_id=1, total_experience_months=72)
    db.add(other)
    db.commit()
    stolen = client.post(f"/api/v1/portal/onboarding/documents/{doc.id}", headers=_cand(other),
                         files={"file": ("x.pdf", b"%PDF", "application/pdf")})
    assert stolen.status_code == 404
