"""Root fixes under Flash (flash spec section E): a job created on the Create Job screen carries
its structured skills, experience and a recruiter into the queue; the queue handler writes them;
an empty head count is one position and still starts recruiting in the job's tenant; sourcing,
bench answers and job search stay inside the tenant and the caller's business units; logging an
LLM call never commits the caller's work; scheduling hours come from settings; one Graph token
function; queue labels name Flash work as Flash."""
import inspect
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.channel_queue import ChannelQueueItem
from app.models.employee import Employee
from app.models.resource_management import BenchPoolEntry
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.models.user import Jobs, Users
from app.services import flash_service
from app.services.message_handlers.job_creation_flash_handler import JobCreationFlashHandler
from app.services.message_handlers.source_candidates_handler import SourceCandidatesHandler
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient, person, scoped_role, two_bu_world

ENQUEUE = "app.services.message_queue_service.MessageQueueService.enqueue"


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
def queued():
    calls = []

    def enqueue(task_name, task_id=None, data=None, **kw):
        calls.append(SimpleNamespace(task_name=task_name, task_id=task_id, data=data, kw=kw))
        return {"status": "queued", "task_id": task_id, "message_id": task_id}

    with patch(ENQUEUE, side_effect=enqueue):
        yield calls


@pytest.fixture
def tenants(db):
    for tid in (1, 2):
        if db.query(Tenant).filter_by(id=tid).first() is None:
            db.add(Tenant(id=tid, name=f"tenant-{tid}"))
    db.flush()


def _recruiter(db):
    role = full_access_role(db)
    role.specialization = "Recruitment"
    db.flush()
    return person(db, role, "Rae Recruiter")


def _job_body(**extra):
    body = {"job_title": "Rails Developer", "job_description": "Build things", "job_skills": "Ruby on Rails, SQL",
            "structured_skills": [{"name": "Ruby on Rails", "years_of_experience": 5, "is_primary": True},
                                  {"name": "SQL"}],
            "job_experience": "5+ years", "min_experience_years": 6, "job_location": "Remote",
            "company_type": "Full time", "company_name": "", "job_status": "active"}
    body.update(extra)
    return body


# --------------------------------------------------------------------------- E4 + E6: create_job payload

def test_create_job_carries_skills_experience_and_a_round_robin_recruiter(db, tenants, queued):
    recruiter = _recruiter(db)
    creator = person(db, full_access_role(db), "Creator")
    db.commit()
    api = ApiClient(db)
    try:
        response = api.post(creator, "/api/v1/jobs/create_job", json=_job_body())
    finally:
        api.close()
    assert response.status_code == 200, response.text
    payload = next(c.data for c in queued if c.task_name == "job_created_flash")
    assert payload["structured_skills"][0] == {"name": "Ruby on Rails", "years_of_experience": 5,
                                               "last_used_date": None, "is_primary": True}
    assert payload["min_experience_years"] == 6 and payload["tenant_id"] == 1
    from app.services.recruiter_assignment_service import active_recruiters
    assert recruiter.UserID in {r.UserID for r in active_recruiters(db, 1)}
    assert payload["recuriter_id"] in {r.UserID for r in active_recruiters(db, 1)}


def test_create_job_keeps_the_recruiter_it_was_given(db, tenants, queued):
    _recruiter(db)
    chosen = person(db, full_access_role(db), "Chosen")
    db.commit()
    api = ApiClient(db)
    try:
        assert api.post(chosen, "/api/v1/jobs/create_job",
                        json=_job_body(recuriter_id=chosen.UserID)).status_code == 200
    finally:
        api.close()
    assert next(c.data for c in queued if c.task_name == "job_created_flash")["recuriter_id"] == chosen.UserID


# --------------------------------------------------------------------------- E4 + E5 + E7: the handler

def _message(payload):
    return SimpleNamespace(id=f"m-{_uid()}", payload=payload, idempotency_key=None, tenant_id=1)


def _payload(**extra):
    payload = {"job_id": f"JOB-{_uid()}", "job_title": "Rails Developer", "job_location": "Remote",
               "job_description": "d", "job_skills": "Ruby on Rails", "job_experience": "5+ years",
               "structured_skills": [{"name": "Ruby on Rails", "is_primary": True}], "min_experience_years": 6,
               "no_of_positions": None, "tenant_id": 1}
    payload.update(extra)
    return payload


def test_handler_writes_structured_skills_experience_and_one_position(db, tenants):
    payload = _payload()
    message = _message(payload)
    with patch("app.services.ready_for_opportunity_service.scan_new_job_for_matches", return_value=[]):
        result = JobCreationFlashHandler.process(message, db)
    job = db.get(Jobs, payload["job_id"])
    assert job.required_skills_canonical == [{"name": "Ruby on Rails", "is_primary": True}]
    assert job.job_skills_boolean_mode == "AND" and float(job.min_experience_years) == 6.0
    assert job.noOfPositions == 1 and job.jobStatus == "active" and job.tenant_id == 1
    # E7: no job_status in the payload means active on both sides
    JobCreationFlashHandler.validate(message, result, db)


@pytest.mark.parametrize("bad", [{"structured_skills": [{"years_of_experience": 3}]},
                                 {"structured_skills": "Rails"},
                                 {"min_experience_years": "lots"},
                                 {"job_skills_boolean_mode": "XOR"}])
def test_handler_rejects_malformed_skill_and_experience_fields(db, tenants, bad):
    payload = _payload(**bad)
    with pytest.raises(ValueError):
        JobCreationFlashHandler.process(_message(payload), db)
    assert db.get(Jobs, payload["job_id"]) is None


def test_slm_job_analysis_treats_no_head_count_as_one():
    from app.services.slm_service import SLMService

    analysis = SLMService.analyze_job_creation(job_id="J-1", job_title="Dev", job_skills="a, b", no_of_positions=None)
    assert analysis["positions_open"] == 1 and analysis["urgency"] == "MEDIUM"


def test_queue_processor_starts_recruiting_in_the_job_tenant_even_when_slm_fails(db, tenants, queued):
    from app.services.queue_processor_service import QueueProcessorService
    from app.services.slm_service import SLMService

    payload = _payload()
    item = ChannelQueueItem(id=str(uuid.uuid4()), message_id="m", type="job_created_flash", channel_type="FLASH_QUEUE",
                            status="PENDING", payload=payload, retry_count=0, tenant_id=1)
    db.add(item)
    db.commit()
    with patch("app.services.ready_for_opportunity_service.scan_new_job_for_matches", return_value=[]), \
            patch.object(SLMService, "analyze_job_creation", side_effect=RuntimeError("SLM down")):
        QueueProcessorService._process_single_message(db, item)
    runs = {c.task_name: c for c in queued}
    assert {"flash_recruiter", "source_candidates_for_job"} <= set(runs)
    assert runs["flash_recruiter"].kw["tenant_id"] == 1 and runs["source_candidates_for_job"].kw["tenant_id"] == 1
    assert runs["flash_recruiter"].task_id == f"recruit:{payload['job_id']}:created"
    assert runs["flash_recruiter"].data["no_of_positions"] == 1


# --------------------------------------------------------------------------- E8: sourcing is tenant-scoped

def _tagged(db, skill, tenant_id):
    cand = Candidate(candidateID=f"CAN-{_uid()}", candidateEmail=f"{_uid()}@example.com", candidatePassword="x",
                     candidateFirstName="Priya", tenant_id=tenant_id, total_experience_months=80)
    db.add(cand)
    db.flush()
    db.add(CandidateSkillTag(tenant_id=str(tenant_id), candidate_id=cand.candidateID, skill_canonical=skill))
    db.flush()
    return cand


def test_sourcing_ranks_only_the_job_tenant_and_reports_in_it(db, tenants, queued):
    skill = f"Rails{_uid()}"
    job = Jobs(tenant_id=1, jobTitle="Rails Developer", jobDescription="d", jobSkills=skill, jobExperience="5",
               jobLocation="Remote", jobStatus="active", required_skills_canonical=[{"name": skill}])
    db.add(job)
    db.flush()
    mine, theirs = _tagged(db, skill, 1), _tagged(db, skill, 2)
    db.commit()
    result = SourceCandidatesHandler.process(SimpleNamespace(id="s1", payload={"job_id": job.jobID}), db)
    report = next(c for c in queued if c.task_name == "candidate_sourcing_complete")
    reported = [m["candidate_id"] for m in report.data["top_matches"]]
    assert mine.candidateID in reported and theirs.candidateID not in reported
    assert report.kw["tenant_id"] == 1 and result["cascade_status"] == "VIABLE"
    assert report.data["top_matches"][0]["recency_score"] == 100


def test_sourcing_has_one_timeout():
    source = inspect.getsource(SourceCandidatesHandler)
    assert "time_bound(timeout_seconds=TIMEOUT_SECONDS)" in source and SourceCandidatesHandler.TIMEOUT_SECONDS == 30


# --------------------------------------------------------------------------- E10: Flash job search

def test_find_candidates_for_job_uses_the_ranking_rule(db, tenants):
    skill = f"Rails{_uid()}"
    job = Jobs(tenant_id=1, jobTitle="Rails Developer", jobDescription="d", jobSkills=skill, jobExperience="5",
               jobLocation="Remote", jobStatus="active")
    db.add(job)
    db.flush()
    fits = _tagged(db, skill, 1)
    junior = _tagged(db, skill, 1)
    junior.total_experience_months = 48  # the 5-year floor
    db.flush()
    found = [r["candidate_id"] for r in flash_service.find_candidates_for_job(db, job.jobID, tenant_id=1)]
    assert fits.candidateID in found and junior.candidateID not in found
    assert flash_service.find_candidates_for_job(db, job.jobID, tenant_id=2) == []


# --------------------------------------------------------------------------- E11: bench answers

def _bench(db, bu_id, tenant_id=1, title="Kafka Engineer"):
    employee = Employee(tenant_id=tenant_id, first_name="Ben", last_name=_uid(), email=f"{_uid()}@blitzenx.com",
                        joining_date=date(2025, 1, 1), status="BENCH", bu_id=bu_id, current_title=title)
    db.add(employee)
    db.flush()
    db.add(BenchPoolEntry(tenant_id=tenant_id, employee_id=employee.id, available_from=date(2026, 10, 1),
                          skill_tags='["Kafka"]'))
    db.flush()
    return employee


def test_bench_answer_is_scoped_to_the_callers_tenant_and_business_units(db, tenants):
    w = two_bu_world(db)
    own, other, foreign = _bench(db, w.bu_a.id), _bench(db, w.bu_b.id), _bench(db, None, tenant_id=2)
    seen = {r["employee_id"] for r in flash_service.find_available_bench_employees(db, w.partner_a, "kafka", top_n=50)}
    assert own.id in seen and other.id not in seen and foreign.id not in seen
    everyone = {r["employee_id"] for r in flash_service.find_available_bench_employees(db, w.org_user, "", top_n=500)}
    assert {own.id, other.id} <= everyone and foreign.id not in everyone


def test_bench_question_needs_employees_view(db, tenants):
    role = RoleTemplate(tenant_id=1, name=f"r-{_uid()}", display_name="No access", enabled=True)
    db.add(role)
    db.flush()
    nobody = Users(UserID=f"U-{_uid()}", UserName="Nobody", UserEmail=f"{_uid()}@blitzenx.com", UserPassword="x",
                   UserRole="Employee", tenant_id=1, role_template_id=role.id)
    db.add(nobody)
    db.flush()
    reply = flash_service.answer_internal_query(db, "who is on the bench right now", current_user=nobody)
    assert reply == {"intent": "bench_availability", "reply": flash_service.PERMISSION_DENIED_BENCH_MESSAGE}
    allowed = person(db, scoped_role(db), "Allowed")
    assert flash_service.answer_internal_query(db, "who is on the bench right now",
                                               current_user=allowed)["reply"] != \
        flash_service.PERMISSION_DENIED_BENCH_MESSAGE


# --------------------------------------------------------------------------- E13: LLM call logging

def test_call_llm_logs_without_committing_the_callers_session():
    from app.services import prompt_framework_service as pfs

    caller, rows = MagicMock(), []
    reply = pfs.call_llm(caller, "1", None, "flash_intent", "v1", "sys", "user", 10, 0.0,
                         llm_call=lambda *a: "ok", log_writer=rows.append)
    assert reply == "ok" and [r.success for r in rows] == [True]
    rows.clear()
    with pytest.raises(pfs.LLMCallFailedError):
        pfs.call_llm(caller, "1", None, "flash_intent", "v1", "sys", "user", 10, 0.0,
                     llm_call=MagicMock(side_effect=RuntimeError("down")), log_writer=rows.append,
                     sleep_fn=lambda _s: None)
    assert [r.success for r in rows] == [False, False]
    caller.commit.assert_not_called()
    caller.add.assert_not_called()


def test_default_log_writer_uses_its_own_session():
    from app.services import prompt_framework_service as pfs

    own = MagicMock()
    with patch("app.core.database.SessionLocal", return_value=own):
        pfs.call_llm(MagicMock(), "1", None, "flash_intent", "v1", "sys", "user", 10, 0.0, llm_call=lambda *a: "ok")
    own.add.assert_called_once()
    own.commit.assert_called_once()
    own.close.assert_called_once()


# --------------------------------------------------------------------------- E17: scheduling settings

def test_business_hours_working_days_and_buffer_come_from_settings(monkeypatch):
    from datetime import datetime, timezone

    from app.services import calendar_matching_service as cms

    monkeypatch.setattr(settings, "INTERVIEW_WORKDAY_START_HOUR", 10)
    monkeypatch.setattr(settings, "INTERVIEW_WORKDAY_END_HOUR", 16)
    monkeypatch.setattr(settings, "INTERVIEW_WEEKEND_DAYS", (4, 5, 6))
    windows = cms._business_hour_windows_utc(date(2026, 10, 12), date(2026, 10, 18), "UTC")  # Mon..Sun
    assert len(windows) == 4  # Friday is now off too
    assert windows[0] == (datetime(2026, 10, 12, 10, tzinfo=timezone.utc), datetime(2026, 10, 12, 16, tzinfo=timezone.utc))
    monkeypatch.setattr(settings, "INTERVIEW_BUFFER_MINUTES", 30)
    start, end = windows[0]
    busy = [(datetime(2026, 10, 12, 11, tzinfo=timezone.utc), datetime(2026, 10, 12, 12, tzinfo=timezone.utc))]
    assert cms.invert_busy_to_free(busy, start, end)[1][0] == datetime(2026, 10, 12, 12, 30, tzinfo=timezone.utc)
    assert "os.getenv" not in inspect.getsource(cms)


# --------------------------------------------------------------------------- E18: one Graph token function

def test_graph_token_function_is_defined_once_and_honours_force_refresh(monkeypatch):
    from app.core import graph_auth

    assert inspect.getsource(graph_auth).count("def get_graph_token") == 1
    monkeypatch.setattr(graph_auth.GraphServiceAuth, "is_configured", staticmethod(lambda: True))
    seen = []
    monkeypatch.setattr(graph_auth.GraphServiceAuth, "get_access_token",
                        staticmethod(lambda force_refresh=False: seen.append(force_refresh) or "tok"))
    assert graph_auth.get_graph_token(force_refresh=True) == "tok" and seen == [True]
    monkeypatch.setattr(graph_auth.GraphServiceAuth, "is_configured", staticmethod(lambda: False))
    with pytest.raises(Exception, match="not configured"):
        graph_auth.get_graph_token()


def test_validate_token_lives_on_the_service_and_reports_unreachable_graph(monkeypatch):
    import requests

    from app.core import graph_auth

    monkeypatch.setattr(graph_auth.requests, "get", lambda *a, **k: SimpleNamespace(status_code=401))
    assert graph_auth.GraphServiceAuth.validate_token("t") is False

    def unreachable(*a, **k):
        raise requests.exceptions.ConnectionError("no route")

    monkeypatch.setattr(graph_auth.requests, "get", unreachable)
    with pytest.raises(RuntimeError):
        graph_auth.GraphServiceAuth.validate_token("t")


# --------------------------------------------------------------------------- E23: queue labels

@pytest.mark.parametrize("task,label", [("create_candidate", "CANDIDATE_QUEUE"),
                                        ("engage_candidate_with_thunder", "THUNDER_QUEUE"),
                                        ("create_thunder_outreach", "THUNDER_QUEUE"),
                                        ("job_created_flash", "FLASH_QUEUE"),
                                        ("flash_recruiter", "FLASH_QUEUE"),
                                        ("interview_scheduled", "FLASH_QUEUE")])
def test_queue_label(task, label):
    from app.services.message_queue_service import queue_label

    assert queue_label(task) == label
