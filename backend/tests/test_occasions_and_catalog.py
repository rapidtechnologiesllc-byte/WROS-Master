"""CEO 2026-11-03: occasion emails sent by themselves, from the recruiter or common mailbox for candidates and HR or the
reporting manager for employees; all templates in one place with dynamic fields."""
import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateStatus
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.services import mail_sender, occasion_email_service as occasions
from tests.scope_fixtures import ApiClient, two_bu_world

TODAY = date(2026, 11, 5)


class FakeMailbox:
    def __init__(self, mailbox):
        self.mailbox, self.sent = mailbox, []

    def create_draft(self, to, subject, html, ref):
        self.sent.append({"to": to, "subject": subject, "html": html, "from": self.mailbox})
        return "d", None, f"<{ref}>"

    def send(self, draft_id):
        pass


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
    return two_bu_world(db)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@pytest.fixture
def box(monkeypatch):
    sent = []

    def fake_sender(session, key, responsible, *, fallback=None, tenant_id=None):
        who = next((session.get(occasions.Users, r) for r in responsible if r), None)
        mailbox = FakeMailbox(who.UserEmail if who is not None else "helpdesk@blitzenx.com")
        mailbox.sent = sent
        return mailbox

    monkeypatch.setattr(mail_sender, "sender_for", fake_sender)
    monkeypatch.setattr(mail_sender, "record_sent", lambda *a, **k: None)
    return sent


def _employee(db, w, **fields):
    defaults = dict(tenant_id=1, first_name="Asha", last_name="Rao", email=f"{uuid.uuid4().hex[:8]}@example.com", employee_number=f"T-{uuid.uuid4().hex[:6]}",
                    joining_date=date(2024, 1, 15), bu_id=w.bu_a.id, status="ACTIVE", reporting_manager_user_id=w.partner_a.UserID)
    row = Employee(**{**defaults, **fields})
    db.add(row)
    db.commit()
    return row


def _candidate(db, **fields):
    row = Candidate(tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidatePassword="h", candidateFirstName="Ria", candidateLastName="Das",
                    candidateEmail=f"r{uuid.uuid4().hex[:8]}@example.com", **fields)
    db.add(row)
    db.commit()
    return row


def _to(box, person):
    return [m for m in box if m["to"] == person]


def test_each_employee_occasion_goes_once_from_their_manager(db, w, box):
    employee = _employee(db, w, date_of_birth=date(1990, 11, 5), joining_date=date(2023, 11, 5), marriage_date=date(2015, 11, 5))
    assert occasions.run_occasion_emails_job(db, today=TODAY)["failed"] == 0
    mine = _to(box, employee.email)
    assert {m["subject"] for m in mine} == {"Happy birthday, Asha", "Happy 3-year work anniversary, Asha", "Happy anniversary, Asha"}
    assert all(m["from"] == w.partner_a.UserEmail for m in mine)
    occasions.run_occasion_emails_job(db, today=TODAY)
    assert len(_to(box, employee.email)) == 3, "never a second wish"


def test_a_date_we_do_not_have_or_another_day_sends_nothing(db, w, box):
    employee = _employee(db, w, date_of_birth=date(1990, 3, 1), joining_date=TODAY)
    occasions.run_occasion_emails_job(db, today=TODAY)
    assert _to(box, employee.email) == [], "joining today is not an anniversary"


def test_project_milestone_every_six_months(db, w, box):
    employee = _employee(db, w)
    db.add(EmployeeAllocation(tenant_id=1, employee_id=employee.id, status="ACTIVE", role="Guidewire Lead", start_date=date(2026, 5, 5),
                              client_id=w.client_a.id, demand_id=w.job_a.jobID, utilization_pct=100))
    db.commit()
    occasions.run_occasion_emails_job(db, today=TODAY)
    assert [m["subject"] for m in _to(box, employee.email)] == ["6 months on Guidewire Lead, thank you"]


def test_a_candidates_birthday_comes_from_the_recruiter_else_the_common_mailbox(db, w, box):
    with_recruiter = _candidate(db, candidateDateOfBirth=date(1991, 11, 5), assigned_recruiter_id=w.org_user.UserID)
    without = _candidate(db, candidateDateOfBirth=date(1992, 11, 5))
    occasions.run_occasion_emails_job(db, today=TODAY)
    assert _to(box, with_recruiter.candidateEmail)[0]["from"] == w.org_user.UserEmail
    assert _to(box, without.candidateEmail)[0]["from"] == "helpdesk@blitzenx.com"


def test_archived_merged_and_no_date_candidates_are_left_alone(db, w, box):
    archived = _candidate(db, candidateDateOfBirth=date(1991, 11, 5))
    db.add(CandidateStatus(candidateID=archived.candidateID, status="Inactive"))
    kept = _candidate(db)
    merged = _candidate(db, candidateDateOfBirth=date(1991, 11, 5), merged_into_id=kept.candidateID)
    db.commit()
    occasions.run_occasion_emails_job(db, today=TODAY)
    assert not _to(box, archived.candidateEmail) and not _to(box, merged.candidateEmail) and not _to(box, kept.candidateEmail)


def test_29_february_is_celebrated_on_the_28th_in_other_years():
    assert occasions._is_today(date(2000, 2, 29), date(2026, 2, 28)) is True
    assert occasions._is_today(date(2000, 2, 29), date(2028, 2, 28)) is False
    assert occasions._is_today(date(2000, 2, 29), date(2028, 2, 29)) is True


def test_appreciation_is_in_the_managers_words(api, db, w, box):
    employee = _employee(db, w)
    short = api.post(w.org_user, f"/api/v1/employees/{employee.id}/appreciate", json={"note": "thanks"})
    assert short.status_code == 400, short.text
    done = api.post(w.org_user, f"/api/v1/employees/{employee.id}/appreciate", json={"note": "You saved the go-live this weekend."})
    assert done.status_code == 200, done.text
    assert "saved the go-live" in _to(box, employee.email)[0]["html"]
    assert _to(box, employee.email)[0]["from"] == w.org_user.UserEmail


def test_the_catalog_lists_every_store_with_fields_and_edits_keep_versions(api, db, w):
    listed = api.get(w.org_user, "/api/v1/template-catalog")
    assert listed.status_code == 200, listed.text
    templates = listed.json()["templates"]
    groups = {t["group"] for t in templates}
    assert {"Occasions", "Candidate notices"} <= groups
    birthday = next(t for t in templates if t["key"] == occasions.EMPLOYEE_BIRTHDAY)
    assert "first_name" in birthday["fields"] and birthday["syntax"] == "{{field}}"
    saved = api.put(w.org_user, f"/api/v1/template-catalog/message/{birthday['id']}",
                    json={"subject": "Many happy returns, {{first_name}}", "body": "Hi {{first_name}}"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["version"] == birthday["version"] + 1
    again = api.get(w.org_user, "/api/v1/template-catalog").json()["templates"]
    assert [t["subject"] for t in again if t["key"] == occasions.EMPLOYEE_BIRTHDAY] == ["Many happy returns, {{first_name}}"]
    no_subject = api.put(w.org_user, f"/api/v1/template-catalog/message/{saved.json()['id']}", json={"body": "x"})
    assert no_subject.status_code == 400


def test_an_edit_reaches_the_next_email(db, w, box):
    from app.models.message_template import MessageTemplate
    from app.services.candidate_status_notifications import seed_templates
    from app.services.message_template_service import activate_template, create_template_version

    seed_templates(db, 1)
    db.flush()
    current = db.query(MessageTemplate).filter_by(tenant_id="1", template_key=occasions.EMPLOYEE_BIRTHDAY, is_active=True).one()
    version = create_template_version(db, tenant_id="1", template_key=current.template_key, template_name=current.template_name,
                                      channel="EMAIL", subject="Cheers {{first_name}}", body="Hi")
    db.flush()
    activate_template(db, version.id, activated_by="test")
    db.commit()
    employee = _employee(db, w, date_of_birth=date(1990, 11, 5))
    occasions.run_occasion_emails_job(db, today=TODAY)
    assert _to(box, employee.email)[0]["subject"] == "Cheers Asha"
