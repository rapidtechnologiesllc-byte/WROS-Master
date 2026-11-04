"""CEO 2026-11-03: "how we notify sub vendor of new roles that they can submit candidates", and a Manage Sub-vendors
page. New client roles are emailed without the client's name; a reply with a resume becomes a submission to review."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.client import Client
from app.models.sub_vendor import SubVendorAccount, SubVendorRequest
from app.models.sub_vendor_submission import SubVendorSubmission
from app.models.user import Jobs
from app.services import sub_vendor_roles_service as roles
from tests.scope_fixtures import ApiClient, two_bu_world


class FakeMailbox:
    mailbox = "recruiter@blitzenx.com"

    def __init__(self):
        self.sent, self.replies = [], []

    def create_draft(self, to, subject, html, ref):
        self.sent.append({"to": to, "subject": subject, "html": html})
        return f"draft-{len(self.sent)}", None, f"<{ref}>"

    def create_reply_draft(self, message_id, html):
        self.replies.append(html)
        return "reply", None, None

    def send(self, message_id):
        pass

    def get_attachment(self, message_id, attachment_id):
        return {"contentBytes": "cmVzdW1l"}


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
def w(db):
    world = two_bu_world(db)
    tenant = world.org_user.tenant_id
    world.client = Client(id=str(uuid.uuid4()), tenant_id=tenant, company_name=f"Acme {uuid.uuid4().hex[:6]}")
    db.add(world.client)
    db.flush()
    world.job = Jobs(jobTitle=f"Guidewire Developer {uuid.uuid4().hex[:4]}", jobDescription=f"Work for {world.client.company_name} on billing.",
                     jobSkills="Guidewire", jobExperience="5+", jobLocation="Remote", jobStatus="active", tenant_id=tenant,
                     client_id=world.client.id, salaryRange="$150k", recuriterID=world.org_user.UserID)
    world.vendor = SubVendorAccount(tenant_id=tenant, company_name=f"Vendor {uuid.uuid4().hex[:6]}", status="APPROVED",
                                    contact_email=f"jobs@v{uuid.uuid4().hex[:6]}.com")
    db.add_all([world.job, world.vendor])
    db.commit()
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _resume(name="Jane_Doe_Resume.docx", text="Jane Doe\njane.doe@example.com\n+1 415 555 0100\nGuidewire"):
    return SimpleNamespace(attachment_id=f"att-{uuid.uuid4().hex[:6]}", name=name, size=10, content=b"x", text=text)


def test_a_new_client_role_goes_out_once_without_client_or_money(db, w):
    box = FakeMailbox()
    assert roles.run_new_roles_job(db, mailbox=box)["sent"] >= 1
    email = next(m for m in box.sent if m["to"] == w.vendor.contact_email)
    assert w.job.jobTitle in email["subject"] and "[Role " in email["subject"]
    assert w.client.company_name not in email["html"] and "our client" in email["html"]
    assert "$150k" not in email["html"]
    before = len(box.sent)
    assert roles.run_new_roles_job(db, mailbox=box)["sent"] == 0
    assert len(box.sent) == before


def test_old_jobs_internal_jobs_and_opted_out_vendors_get_nothing(db, w):
    w.job.jobCreatedAt = datetime.utcnow() - timedelta(days=30)
    db.commit()
    box = FakeMailbox()
    roles.run_new_roles_job(db, mailbox=box)
    assert not [m for m in box.sent if w.job.jobTitle in m["subject"]]
    w.job.jobCreatedAt = datetime.utcnow()
    w.vendor.receives_new_roles = False
    db.commit()
    roles.run_new_roles_job(db, mailbox=box)
    assert not [m for m in box.sent if m["to"] == w.vendor.contact_email]


def _role(db, w):
    request = SubVendorRequest(tenant_id=w.job.tenant_id, demand_id=w.job.jobID, sub_vendor_id=w.vendor.id,
                               notified_at=datetime.utcnow())
    db.add(request)
    db.commit()
    return request


def test_a_reply_with_a_resume_becomes_a_submission_for_that_role_once(db, w):
    request = _role(db, w)
    message = {"id": "m1", "subject": f"Re: New role [Role {request.id[:8]}]"}
    resume = _resume()
    assert roles.receive_submission(db, w.vendor, message, [resume], "box@x.com") is True
    assert roles.receive_submission(db, w.vendor, message, [resume], "box@x.com") is True
    rows = db.query(SubVendorSubmission).filter(SubVendorSubmission.request_id == request.id).all()
    assert len(rows) == 1
    assert rows[0].candidate_email == "jane.doe@example.com" and rows[0].status == "PENDING_REVIEW"


def test_no_open_role_is_not_a_submission(db, w):
    assert roles.receive_submission(db, w.vendor, {"id": "m2", "subject": "Hello"}, [_resume()], "box@x.com") is False


def test_accept_creates_the_candidate_with_the_vendor_as_source_and_reject_needs_a_reason(db, w, monkeypatch):
    from app.services import candidate_resume_intake

    monkeypatch.setattr(candidate_resume_intake, "store_resume_document", lambda *a, **k: None)
    request = _role(db, w)
    good = SubVendorSubmission(request_id=request.id, sub_vendor_id=w.vendor.id, candidate_name="Jane Doe",
                               candidate_email=f"jane{uuid.uuid4().hex[:6]}@example.com")
    bad = SubVendorSubmission(request_id=request.id, sub_vendor_id=w.vendor.id, candidate_name="Sam Lee",
                              candidate_email="", graph_message_id="m3", source_mailbox="box@x.com")
    db.add_all([good, bad])
    db.commit()
    candidate_id = roles.accept_submission(db, w.org_user, good)
    candidate = db.get(Candidate, candidate_id)
    assert w.vendor.company_name in candidate.candidateSource
    assert good.status == "ACCEPTED" and good.created_candidate_id == candidate_id
    with pytest.raises(roles.SubVendorSubmissionError):
        roles.accept_submission(db, w.org_user, bad)  # no email
    with pytest.raises(roles.SubVendorSubmissionError):
        roles.reject_submission(db, w.org_user, bad, "no")
    box = FakeMailbox()
    roles.reject_submission(db, w.org_user, bad, "Not enough BillingCenter experience.", mailbox=box)
    assert bad.status == "REJECTED" and "BillingCenter" in box.replies[0]


def test_the_page_shows_balance_and_edits_terms(api, db, w):
    listed = api.get(w.org_user, "/api/v1/vendor-invoices/sub-vendors").json()
    row = next(v for v in listed if v["id"] == w.vendor.id)
    assert row["payment_terms_days"] == 30 and row["open_balance_usd_cents"] == 0 and row["receives_new_roles"] is True
    updated = api.patch(w.org_user, f"/api/v1/vendor-invoices/sub-vendors/{w.vendor.id}",
                        json={"payment_terms_days": 45, "w9_status": "RECEIVED", "receives_new_roles": False})
    assert updated.status_code == 200, updated.text
    assert updated.json()["payment_terms_days"] == 45 and updated.json()["w9_status"] == "RECEIVED"
    _role(db, w)
    assert api.get(w.org_user, "/api/v1/vendor-invoices/roles").status_code == 200
    assert api.get(w.org_user, "/api/v1/vendor-invoices/submissions").status_code == 200
