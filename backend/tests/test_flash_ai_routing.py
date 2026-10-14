"""Flash answers from real data only. Rules route the common phrasings for free; the AI
router handles the rest but may only pick a known intent -- anything else (no key, bad
output, an invented intent) falls back to the honest "unsupported" reply. Candidate status
includes where the person is in the hiring order and what they are waiting for."""
import json
import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate, CandidateStatus
from app.models.client import Client
from app.models.employee import Employee
from app.models.employee_allocation import EmployeeAllocation
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.models.timesheet import Timesheet
from app.models.user import Jobs, Users
from app.services import flash_service
from app.services import hiring_pipeline_service as hp


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
def user(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="BlitzenX"))
        db.flush()
    role = RoleTemplate(tenant_id=1, name=f"r-{_uid()}", display_name="R", enabled=True)
    db.add(role)
    db.flush()
    person = Users(UserID=f"U-{_uid()}", UserName="Dee", UserEmail=f"dee{_uid()}@blitzenx.com", UserPassword="x",
                   UserRole="Employee", tenant_id=1, role_template_id=role.id)
    db.add(person)
    db.commit()
    return person


def _router(reply):
    return lambda system, prompt, max_tokens, temperature: reply


def test_ai_routes_phrasings_the_rules_miss(db, user, monkeypatch):
    assert flash_service.classify_internal_query("got a spare kafka person?")["intent"] == "unknown"
    monkeypatch.setattr(flash_service, "_ai_llm_call", _router(json.dumps({"intent": "bench_availability", "query": "kafka"})))
    result = flash_service.answer_internal_query(db, "got a spare kafka person?", current_user=user)
    assert result["intent"] == "bench_availability"


@pytest.mark.parametrize("reply", ["not json", json.dumps({"intent": "delete_everything", "query": "x"}), json.dumps([1])])
def test_ai_cannot_invent_an_answer_or_an_intent(db, user, monkeypatch, reply):
    monkeypatch.setattr(flash_service, "_ai_llm_call", _router(reply))
    result = flash_service.answer_internal_query(db, "tell me something interesting", current_user=user)
    assert result == {"intent": "unknown", "reply": flash_service.UNSUPPORTED_QUERY_MESSAGE}


def test_without_a_model_flash_still_answers_what_the_rules_know(db, user, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert flash_service.answer_internal_query(db, "what's on my plate", current_user=user)["intent"] == "my_tasks"
    assert flash_service.answer_internal_query(db, "write me a poem", current_user=user)["intent"] == "unknown"


def test_my_timesheets(db, user):
    reply = flash_service.answer_internal_query(db, "did I submit my timesheets?", current_user=user)
    assert reply["intent"] == "my_timesheets" and "don't have an employee record" in reply["reply"]
    employee = Employee(tenant_id=1, first_name="Dee", last_name="R", email=f"d{_uid()}@x.com", joining_date=date(2026, 1, 5),
                        status="ALLOCATED", wros_user_id=user.UserID)
    client = Client(tenant_id=1, company_name=f"C {_uid()}", payment_terms_days=30)
    db.add_all([employee, client])
    db.flush()
    job = Jobs(tenant_id=1, client_id=client.id, jobTitle="Dev", jobDescription="d", jobSkills="x", jobExperience="5",
               jobLocation="Remote")
    db.add(job)
    db.flush()
    allocation = EmployeeAllocation(tenant_id=1, employee_id=employee.id, client_id=client.id, demand_id=job.jobID,
                                    status="ACTIVE", start_date=date(2026, 1, 5))
    db.add(allocation)
    db.flush()
    db.add(Timesheet(tenant_id=1, employee_id=employee.id, allocation_id=allocation.id, week_starting_date=date(2026, 9, 28),
                     total_hours=40, billable_hours=40, non_billable_hours=0, status="SUBMITTED"))
    db.commit()
    reply = flash_service.answer_internal_query(db, "show my timesheets", current_user=user)["reply"]
    assert "week of 28 Sep: submitted, 40h" in reply


def test_candidate_status_says_what_hiring_is_waiting_for(db, user, monkeypatch):
    monkeypatch.setattr("app.services.thunder_mail.cadence_service.enqueue_once", lambda *a, **k: True)
    candidate = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"z{_uid()}@example.com", candidatePassword="x",
                          candidateFirstName="Zoravar", candidateLastName="Quill", tenant_id=1, thunder_enabled=False)
    db.add(candidate)
    db.flush()
    db.add(CandidateStatus(candidateID=candidate.candidateID, status="Active", piplineStatus="Screening"))
    db.commit()
    hp.evaluate_and_act(db, candidate.candidateID, "test")
    reply = flash_service.answer_internal_query(db, "what's the status of Zoravar Quill?", current_user=user)["reply"]
    assert "Hiring stage: screen -- waiting for recruiter screen pending." in reply
