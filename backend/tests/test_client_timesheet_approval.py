"""Client timesheet approval (CEO 2026-10-23, gap 3): for a client flagged
requires_client_timesheet_approval, an internally approved week goes CLIENT_PENDING; the client's
approver decides from a signed, expiring, single-use link on a public page (approve, or reject with a
reason that sends the week back to the employee through the resubmit task), or an internal approver
uploads the client's VMS-approved timesheet as evidence. Invoicing refuses weeks without it."""
import re
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.core.rate_limiter import reset_public_rate_limits
from app.models.client import ClientContact
from app.models.client_timesheet_approval import ClientTimesheetApproval
from app.models.task import Task
from app.models.timesheet import Timesheet
from app.models.timesheet_review import TimesheetReview
from app.services import client_timesheet_approval_service as client_approvals
from app.services.message_handlers.send_client_timesheet_approval_handler import SendClientTimesheetApprovalHandler
from tests.test_core_certification import _h, _user, db, org  # noqa: F401 -- fixtures
from tests.test_timesheet_approval import (  # noqa: F401 -- fixtures
    LAST_MONDAY, _self_service_role, _submit, api, emails, loop,
)

APPROVER = "approver@client.example"
PUBLIC = "/api/v1/public/client-timesheet-approval"


class FakeMailbox:
    def __init__(self):
        self.drafts, self.sent = {}, []

    def create_draft(self, to, subject, html, ref):
        mid = f"g{len(self.drafts) + 1}"
        self.drafts[mid] = {"to": to, "subject": subject, "html": html}
        return mid, None, None

    def is_draft(self, mid):
        return mid not in self.sent

    def send(self, mid):
        self.sent.append(mid)


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    reset_public_rate_limits()
    yield
    reset_public_rate_limits()


@pytest.fixture
def flagged(db, loop):
    """The loop's client approves its own timesheets; the placement names the client approver."""
    loop.org.staff_aug.requires_client_timesheet_approval = True
    loop.allocation.timesheet_approver_email = APPROVER
    db.commit()
    return loop


def _approve_internally(api, loop):
    assert _submit(api, loop).status_code == 200
    res = api.post(f"/api/v1/timesheet-approvals/{loop.sheet.id}/approve", headers=_h(loop.manager),
                   json={"comment": "ok"})
    assert res.status_code == 200, res.text
    return res.json()


def _request(db, sheet):
    return db.query(ClientTimesheetApproval).filter_by(timesheet_id=sheet.id) \
        .order_by(ClientTimesheetApproval.id.desc()).first()


def _email_link(db, sheet, mailbox=None):
    """Run the queued email's handler; returns (token, mailbox)."""
    mailbox = mailbox or FakeMailbox()
    request = _request(db, sheet)
    result = SendClientTimesheetApprovalHandler.process(
        SimpleNamespace(id="m1", payload={"request_id": request.id}), db, mailbox=mailbox)
    assert result["status"] == "sent"
    html = list(mailbox.drafts.values())[-1]["html"]
    token = re.search(r"token=([A-Za-z0-9_\-]+)", html).group(1)
    return token, mailbox


# ------------------------------------------------------------------------------ the flow

def test_internal_approval_of_a_flagged_client_week_goes_to_the_client(api, db, flagged, emails):
    view = _approve_internally(api, flagged)
    sheet = db.get(Timesheet, flagged.sheet.id)
    assert sheet.status == "APPROVED" and sheet.client_approval_status == "CLIENT_PENDING"
    assert sheet.client_approver_email == APPROVER
    request = _request(db, sheet)
    assert request.decision == "PENDING" and request.approver_email == APPROVER and request.token_hash is None
    queued = [e for e in emails if e["task"] == "send_client_timesheet_approval"]
    assert queued == [{"task": "send_client_timesheet_approval", "id": f"client-ts-approval-{request.id}",
                       "request_id": request.id}]  # the payload never carries the token
    assert view["client_approval"]["status"] == "CLIENT_PENDING" and view["client_approval"]["can_request"]


def test_a_client_without_the_flag_is_never_asked(api, db, loop, emails):
    _approve_internally(api, loop)
    sheet = db.get(Timesheet, loop.sheet.id)
    assert sheet.client_approval_status is None and _request(db, sheet) is None
    assert not [e for e in emails if e["task"] == "send_client_timesheet_approval"]


def test_the_email_carries_a_single_use_link_and_only_its_hash_is_stored(api, db, flagged, emails):
    _approve_internally(api, flagged)
    token, mailbox = _email_link(db, flagged.sheet)
    request = _request(db, flagged.sheet)
    draft = list(mailbox.drafts.values())[0]
    assert draft["to"] == APPROVER and "40 hours" in draft["html"] and mailbox.sent == ["g1"]
    assert request.token_hash != token and len(request.token_hash) == 64 and request.emailed_at is not None
    assert request.expires_at > datetime.utcnow() + timedelta(hours=settings.CLIENT_TIMESHEET_APPROVAL_LINK_TTL_HOURS - 1)
    again = SendClientTimesheetApprovalHandler.process(SimpleNamespace(id="m2", payload={"request_id": request.id}),
                                                       db, mailbox=mailbox)
    assert again["status"] == "already_sent" and len(mailbox.drafts) == 1


def test_public_page_needs_no_login_and_shows_only_the_week(api, db, flagged, emails):
    _approve_internally(api, flagged)
    token, _ = _email_link(db, flagged.sheet)
    res = api.post(f"{PUBLIC}/view", json={"token": token})  # no Authorization header
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_hours"] == 40 and body["week_starting_date"] == LAST_MONDAY.isoformat()
    assert body["client_name"] == flagged.org.staff_aug.company_name and len(body["entries"]) == 5
    assert set(body) == {"employee_name", "client_name", "issuer_name", "expires_at", "week_starting_date",
                         "week_ending_date", "entries", "total_hours", "billable_hours"}
    assert set(body["entries"][0]) == {"entry_date", "hours", "entry_type"}  # no notes, no rates
    assert api.post(f"{PUBLIC}/view", json={"token": "not-a-real-token"}).status_code == 410


def test_client_approves_once_by_link(api, db, flagged, emails):
    _approve_internally(api, flagged)
    token, _ = _email_link(db, flagged.sheet)
    res = api.post(f"{PUBLIC}/approve", json={"token": token})
    assert res.status_code == 200, res.text
    sheet = db.get(Timesheet, flagged.sheet.id)
    assert sheet.client_approval_status == "CLIENT_APPROVED" and sheet.client_approver_email == APPROVER
    assert sheet.client_approved_at is not None
    request = _request(db, sheet)
    assert (request.decision, request.method) == ("APPROVED", "LINK") and request.used_at is not None
    assert api.post(f"{PUBLIC}/approve", json={"token": token}).status_code == 410  # single use
    assert api.post(f"{PUBLIC}/reject", json={"token": token, "reason": "late"}).status_code == 410


def test_an_expired_link_does_nothing(api, db, flagged, emails):
    _approve_internally(api, flagged)
    token, _ = _email_link(db, flagged.sheet)
    _request(db, flagged.sheet).expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    res = api.post(f"{PUBLIC}/approve", json={"token": token})
    assert res.status_code == 410 and "expired" in res.json()["detail"]
    assert db.get(Timesheet, flagged.sheet.id).client_approval_status == "CLIENT_PENDING"


def test_client_rejection_needs_a_reason_and_goes_back_to_the_employee(api, db, flagged, emails):
    _approve_internally(api, flagged)
    token, _ = _email_link(db, flagged.sheet)
    assert api.post(f"{PUBLIC}/reject", json={"token": token, "reason": "   "}).status_code == 422
    assert db.get(Timesheet, flagged.sheet.id).client_approval_status == "CLIENT_PENDING"  # link still usable

    res = api.post(f"{PUBLIC}/reject", json={"token": token, "reason": "Wednesday was a client holiday"})
    assert res.status_code == 200, res.text
    sheet = db.get(Timesheet, flagged.sheet.id)
    assert sheet.status == "REJECTED" and sheet.client_approval_status == "CLIENT_REJECTED"
    assert "Wednesday was a client holiday" in sheet.rejection_reason and sheet.approved_at is None
    review = db.query(TimesheetReview).filter_by(timesheet_id=sheet.id).order_by(TimesheetReview.revision.desc()).first()
    assert review.decision == "REJECTED" and review.client_decision_email == APPROVER
    task = db.get(Task, review.resubmit_task_id)
    assert task.assigned_to_user_id == flagged.login.UserID and task.category == "TIMESHEET_RESUBMIT"
    assert "Wednesday was a client holiday" in task.description
    assert any(e["task"] == "send_staff_email" and e["user_id"] == flagged.login.UserID and "rejected" in e["subject"]
               for e in emails)

    # the employee answers, the approver approves again, and the client gets a new link
    assert _submit(api, flagged, response="Wednesday was worked remotely, agreed with the client").status_code == 200
    res = api.post(f"/api/v1/timesheet-approvals/{sheet.id}/approve", headers=_h(flagged.manager),
                   json={"addressed": True})
    assert res.status_code == 200, res.text
    assert db.get(Timesheet, sheet.id).client_approval_status == "CLIENT_PENDING"
    assert api.post(f"{PUBLIC}/approve", json={"token": token}).status_code == 410  # the old link is dead
    new_token, _ = _email_link(db, flagged.sheet)
    assert api.post(f"{PUBLIC}/approve", json={"token": new_token}).status_code == 200


def test_resend_supersedes_the_open_link(api, db, flagged, emails):
    _approve_internally(api, flagged)
    old, _ = _email_link(db, flagged.sheet)
    res = api.post(f"/api/v1/timesheet-approvals/{flagged.sheet.id}/client-request", headers=_h(flagged.manager))
    assert res.status_code == 200, res.text
    assert api.post(f"{PUBLIC}/view", json={"token": old}).status_code == 410
    new, _ = _email_link(db, flagged.sheet)
    assert api.post(f"{PUBLIC}/view", json={"token": new}).status_code == 200


def test_evidence_upload_marks_the_week_client_approved(api, db, flagged, emails, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    _approve_internally(api, flagged)
    url = f"/api/v1/timesheet-approvals/{flagged.sheet.id}/client-evidence"
    bad = api.post(url, headers=_h(flagged.manager), files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 422
    stranger = _user(db, _self_service_role(db), "Someone Else")
    db.commit()
    assert api.post(url, headers=_h(stranger), files={"file": ("ts.pdf", b"%PDF-1", "application/pdf")}).status_code == 404

    res = api.post(url, headers=_h(flagged.manager), data={"note": "Approved in Fieldglass"},
                   files={"file": ("fieldglass.pdf", b"%PDF-1.4 approved", "application/pdf")})
    assert res.status_code == 200, res.text
    sheet = db.get(Timesheet, flagged.sheet.id)
    assert sheet.client_approval_status == "CLIENT_APPROVED" and sheet.client_approved_at is not None
    request = _request(db, sheet)
    assert (request.method, request.decision, request.recorded_by_user_id) == ("EVIDENCE", "APPROVED",
                                                                                flagged.manager.UserID)
    assert request.evidence_filename == "fieldglass.pdf" and request.reason == "Approved in Fieldglass"
    assert res.json()["client_approval"]["request"]["recorded_by"] == "Mira Manager"
    download = api.get(url, headers=_h(flagged.manager))
    assert download.status_code == 200 and download.content == b"%PDF-1.4 approved"
    again = api.post(url, headers=_h(flagged.manager), files={"file": ("x.pdf", b"%PDF", "application/pdf")})
    assert again.status_code == 422  # already client-approved


def test_no_approver_email_gives_the_internal_approver_a_task(api, db, loop, emails):
    loop.org.staff_aug.requires_client_timesheet_approval = True
    db.commit()
    _approve_internally(api, loop)
    request = _request(db, loop.sheet)
    assert request.approver_email is None and request.task_id
    task = db.get(Task, request.task_id)
    assert task.assigned_to_user_id == loop.manager.UserID and task.link == f"/timesheet-approvals/{loop.sheet.id}"
    assert not [e for e in emails if e["task"] == "send_client_timesheet_approval"]
    res = api.post(f"/api/v1/timesheet-approvals/{loop.sheet.id}/client-request", headers=_h(loop.manager))
    assert res.status_code == 422 and "approver email" in res.json()["detail"]


def test_public_endpoint_is_rate_limited_per_ip(api, monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_ENDPOINT_RATE_LIMIT_PER_MINUTE", 2)
    codes = [api.post(f"{PUBLIC}/view", json={"token": "x"}).status_code for _ in range(3)]
    assert codes == [410, 410, 429]


def test_public_routes_skip_the_login_gate():
    from app.middleware.auth_middleware import AuthenticationMiddleware as gate

    mw = gate(app=lambda scope, receive, send: None)
    for path in (f"{PUBLIC}/view", f"{PUBLIC}/approve", f"{PUBLIC}/reject",
                 "/api/v1/public/thunder-chat/start", "/api/v1/public/thunder-chat/message"):
        assert mw._is_public_route(path), path
    assert not mw._is_public_route("/api/v1/timesheet-approvals")


# ------------------------------------------------------------------------------ the placement's approver

def test_placement_approver_must_be_a_client_timesheet_approver_contact(api, db, loop):
    url = f"/api/v1/allocations/{loop.allocation.id}/client-billing"
    admin = _user(db, loop.org.role, "Admin")
    db.add(ClientContact(tenant_id=1, client_id=loop.org.staff_aug.id, name="Tia", email="Tia@Client.example",
                         role_type="TIMESHEET_APPROVER"))
    db.commit()
    assert api.put(url, headers=_h(admin), json={"timesheet_approver_email": "not-an-email"}).status_code == 422
    wrong = api.put(url, headers=_h(admin), json={"timesheet_approver_email": "someone@else.example"})
    assert wrong.status_code == 422 and "tia@client.example" in wrong.json()["detail"]
    ok = api.put(url, headers=_h(admin), json={"timesheet_approver_email": "tia@client.example"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["timesheet_approver_email"] == "tia@client.example"
    cleared = api.put(url, headers=_h(admin), json={"timesheet_approver_email": ""})
    assert cleared.status_code == 200 and cleared.json()["timesheet_approver_email"] is None


def test_client_flag_and_payment_terms_are_editable_and_validated(api, db, loop):
    admin = _user(db, loop.org.role, "Admin")
    db.commit()
    url = f"/api/v1/clients/{loop.org.staff_aug.id}"
    res = api.patch(url, headers=_h(admin), json={"requires_client_timesheet_approval": True, "payment_terms_days": 45})
    assert res.status_code == 200, res.text
    assert res.json()["requires_client_timesheet_approval"] is True and res.json()["payment_terms_days"] == 45
    assert api.patch(url, headers=_h(admin), json={"payment_terms_days": -5}).status_code == 400
    assert api.patch(url, headers=_h(admin), json={"payment_terms_days": None}).status_code == 400
