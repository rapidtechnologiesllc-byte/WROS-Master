"""The recruiter agent's search per job: criteria written from the job, candidates captured by skills, title or
resume, one personal email per new match, and the job workspace that shows and saves all of it."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import CandidateJobApplication
from app.models.candidate_resume_parsed import CandidateResumeParsed
from app.models.client_update import RoleOutreach
from app.models.hiring_pipeline import HiringPipeline
from app.models.job_search import JobSearchCriteria, JobSearchMatch
from app.services import job_search_service as job_search
from app.services import job_workspace_service as workspace
from app.services.boolean_search_service import BooleanQueryError
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.test_core_certification import _h, _user

TENANT = 7441
NOW = datetime(2026, 11, 9, 12, 0)
ENQUEUE = "app.services.thunder_mail.cadence_service.enqueue_once"


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def outreach_on(request):
    """Outreach is off until the CEO turns it on; these tests switch it on, except the one that checks the default."""
    if request.node.name == "test_by_default_matches_are_captured_and_nobody_is_written_to":
        yield
        return
    with patch.object(settings, "JOB_AUTO_OUTREACH", True):
        yield


def test_by_default_matches_are_captured_and_nobody_is_written_to(db):
    job = _job(db)
    _person(db, "Default", skills="Guidewire, PolicyCenter")
    job_search.ensure_criteria(db, job)
    with patch(ENQUEUE) as enqueue:
        job_search.capture_for_job(db, job, NOW)
        assert job_search.reach_out(db, job, NOW) == 0
    enqueue.assert_not_called()


@pytest.fixture
def api(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    with patch("app.services.message_queue_service.MessageQueueService.enqueue", return_value="queued"):
        yield TestClient(app)
    app.dependency_overrides.clear()


def _job(db, tenant_id=TENANT, **fields):
    values = dict(jobTitle="PolicyCenter Developer", jobSkills="Guidewire, PolicyCenter", jobStatus="active",
                  jobCreatedAt=NOW - timedelta(days=2), required_skills_canonical=[{"name": "Guidewire"}, {"name": "PolicyCenter"}])
    values.update(fields)
    return factories.job(db, tenant_id, **values)


def _person(db, first, *, skills="", resume=None, months=96, tenant_id=TENANT, **fields):
    fields.setdefault("thunder_enabled", True)
    candidate = factories.candidate(db, tenant_id, candidateFirstName=first, candidateLastName="Test", candidateSkills=skills,
                                    total_experience_months=months, **fields)
    if resume is not None:
        db.add(CandidateResumeParsed(tenant_id=str(tenant_id), candidate_id=candidate.candidateID, raw_text=resume))
        db.flush()
    return candidate


def _matched(db, job):
    return {m.candidate_id: m for m in db.query(JobSearchMatch).filter(JobSearchMatch.job_id == job.jobID).all()}


# ------------------------------------------------------------------------------ criteria

def test_criteria_are_written_from_the_jobs_skills_with_every_name_a_skill_goes_by(db):
    job = _job(db)
    criteria = job_search.ensure_criteria(db, job)
    assert criteria.boolean_query.startswith('("Guidewire" OR "GW" OR "GW PolicyCenter"')
    assert criteria.boolean_query.endswith('AND "PolicyCenter"')
    assert criteria.generated_query == criteria.boolean_query and criteria.edited_by is None
    assert job_search.ensure_criteria(db, job) is criteria  # written once


def test_or_mode_optional_skills_and_a_job_with_only_a_title(db):
    either = _job(db, jobSkills="Python, AWS", job_skills_boolean_mode="OR",
                  required_skills_canonical=[{"name": "Python"}, {"name": "AWS"}])
    assert job_search.generate_query(either) == '("Python" OR "Python3" OR "Python 3") OR ("AWS" OR "Amazon Web Services")'
    optional = _job(db, jobSkills="Gosu, Jira", required_skills_canonical=[{"name": "Gosu"}, {"name": "Jira", "mandatory": False}])
    assert job_search.generate_query(optional) == '"Gosu"'
    titled = _job(db, jobTitle="Senior Billing Analyst", jobSkills="", required_skills_canonical=[])
    assert job_search.generate_query(titled) == '"Billing Analyst"'
    with pytest.raises(job_search.JobSearchError, match="no skills"):
        job_search.generate_query(_job(db, jobTitle="Senior", jobSkills="", required_skills_canonical=[]))


def test_a_recruiters_edit_wins_until_they_go_back_to_the_systems_version(db):
    job = _job(db)
    user = factories.user(db, TENANT)
    criteria = job_search.save_criteria(db, job, user, 'guidewire and ("policy center" or policycenter) not tester')
    assert criteria.boolean_query == 'guidewire AND ("policy center" OR policycenter) AND NOT tester'
    assert criteria.edited_by == user.UserID and criteria.generated_query != criteria.boolean_query
    with pytest.raises(BooleanQueryError, match="bracket is not closed"):
        job_search.save_criteria(db, job, user, "(guidewire")
    assert job_search.reset_criteria(db, job).edited_by is None
    assert criteria.boolean_query == criteria.generated_query


# ------------------------------------------------------------------------------ capture

def test_capture_finds_by_skills_or_resume_once_and_applies_every_hiring_rule(db):
    job = _job(db, min_experience_years=7)
    by_skill = _person(db, "Skill", skills="Guidewire, PolicyCenter")
    by_resume = _person(db, "Resume", skills="Java", resume="Eight years configuring GW PolicyCenter for carriers.")
    _person(db, "NoMatch", skills="Guidewire, ClaimCenter")
    _person(db, "TooJunior", skills="Guidewire, PolicyCenter", months=36)          # the 5-year floor
    _person(db, "BelowJobMinimum", skills="Guidewire, PolicyCenter", months=72)    # the job's own 7 years
    _person(db, "Contractor", skills="Guidewire, PolicyCenter", employment_type="C2C", country="US")
    _person(db, "Elsewhere", skills="Guidewire, PolicyCenter", tenant_id=TENANT + 1)

    captured = job_search.capture_for_job(db, job, NOW)
    assert {m.candidate_id for m in captured} == {by_skill.candidateID, by_resume.candidateID}
    rows = _matched(db, job)
    # the criteria name every form of the skill, so the match says which one the resume used
    assert rows[by_resume.candidateID].found == {"GW": ["resume"], "GW PolicyCenter": ["resume"], "PolicyCenter": ["resume"]}
    assert "GW PolicyCenter for carriers" in rows[by_resume.candidateID].snippet
    assert rows[by_skill.candidateID].score > rows[by_resume.candidateID].score
    assert job_search.capture_for_job(db, job, NOW) == []  # nobody twice
    late = _person(db, "Late", skills="Guidewire, PolicyCenter")
    assert [m.candidate_id for m in job_search.capture_for_job(db, job, NOW)] == [late.candidateID]


# ------------------------------------------------------------------------------ outreach

def test_each_new_match_gets_one_personal_email_that_never_names_the_client(db):
    job = _job(db)
    good = _person(db, "Priya", skills="Guidewire, PolicyCenter", timezone="UTC")
    stopped = _person(db, "Sam", skills="Guidewire, PolicyCenter", thunder_enabled=False)
    job_search.capture_for_job(db, job, NOW)
    db.commit()
    with patch(ENQUEUE, return_value=True) as enqueue:
        assert job_search.reach_out(db, job, NOW) == 1
        assert job_search.reach_out(db, job, NOW) == 0  # nobody is written to twice
    assert enqueue.call_count == 1
    rows = _matched(db, job)
    assert (rows[good.candidateID].status, rows[good.candidateID].contacted_at) == ("CONTACTED", NOW)
    assert rows[stopped.candidateID].status == "SKIPPED" and "not contactable" in rows[stopped.candidateID].note
    email = db.query(RoleOutreach).filter_by(job_id=job.jobID, candidate_id=good.candidateID).one()
    assert "PolicyCenter Developer" in email.body_html and settings.JOB_OUTREACH_CLIENT_DESCRIPTION in email.body_html
    assert email.composed_by == "rules"


def test_outreach_respects_the_per_run_cap_the_switch_and_a_thunder_pause(db):
    job = _job(db)
    for index in range(3):
        _person(db, f"P{index}", skills="Guidewire, PolicyCenter", timezone="UTC")
    job_search.capture_for_job(db, job, NOW)
    db.commit()
    with patch(ENQUEUE, return_value=True):
        with patch.object(settings, "JOB_AUTO_OUTREACH", False):
            assert job_search.reach_out(db, job, NOW) == 0
        with patch("app.services.thunder_pause_service.is_thunder_paused", return_value=True):
            assert job_search.reach_out(db, job, NOW) == 0
        with patch.object(settings, "JOB_OUTREACH_PER_RUN", 2):
            assert job_search.reach_out(db, job, NOW) == 2
            assert job_search.reach_out(db, job, NOW) == 1
    assert {m.status for m in _matched(db, job).values()} == {"CONTACTED"}


def test_the_hourly_job_covers_open_jobs_only_and_the_guard_holds_back_old_jobs(db):
    recent = _job(db)
    old = _job(db, jobTitle="Old Role", jobCreatedAt=NOW - timedelta(days=40))
    closed = _job(db, jobTitle="Closed Role", jobStatus="closed")
    _person(db, "Priya", skills="Guidewire, PolicyCenter", timezone="UTC")

    job_search.backlog_guard(db, NOW)
    assert _matched(db, recent) == {}
    held = list(_matched(db, old).values())
    assert [m.status for m in held] == ["SKIPPED"] and "before automatic outreach" in held[0].note

    with patch(ENQUEUE, return_value=True):
        result = job_search.run_capture_job(db, NOW)
    assert result["failed"] == 0 and result["emails_queued"] >= 1
    assert [m.status for m in _matched(db, recent).values()] == ["CONTACTED"]
    assert [m.status for m in _matched(db, old).values()] == ["SKIPPED"]   # never written to about the old job
    assert _matched(db, closed) == {}


# ------------------------------------------------------------------------------ the workspace

def test_candidates_on_a_job_are_counted_in_the_stage_they_are_really_in(db):
    job = _job(db)
    leader = factories.user(db, TENANT, role_template_id=factories.role(db, TENANT, org_level_access=True).id)
    found = _person(db, "Found", skills="Guidewire, PolicyCenter")
    applied = _person(db, "Applied")
    screening, interviewing, rejected = _person(db, "Screening"), _person(db, "Interviewing"), _person(db, "Rejected")
    elsewhere = _person(db, "Elsewhere", job_id=None)
    job_search.capture_for_job(db, job, NOW)
    db.add(CandidateJobApplication(candidate_id=applied.candidateID, job_id=job.jobID))
    other_job = _job(db, jobTitle="Other")
    db.add_all([
        HiringPipeline(tenant_id=TENANT, candidate_id=screening.candidateID, job_id=job.jobID, stage="SCREEN"),
        HiringPipeline(tenant_id=TENANT, candidate_id=interviewing.candidateID, job_id=job.jobID, stage="L1"),
        HiringPipeline(tenant_id=TENANT, candidate_id=rejected.candidateID, job_id=job.jobID, stage="REJECTED", closed_at=NOW),
        HiringPipeline(tenant_id=TENANT, candidate_id=elsewhere.candidateID, job_id=other_job.jobID, stage="L2"),
        # found by this job's search while interviewing for another job: still only Sourced here
        HiringPipeline(tenant_id=TENANT, candidate_id=found.candidateID, job_id=other_job.jobID, stage="L2"),
    ])
    db.flush()

    view = workspace.job_candidates(db, leader, job)
    assert view["total"] == 5 and sum(view["counts"].values()) == view["total"]
    assert {k: v for k, v in view["counts"].items() if v} == {
        "Sourced": 2, "Recruiter Screening": 1, "L1 Interview": 1, "Closed": 1}
    by_name = {row["name"].split()[0]: row for row in view["candidates"]}
    assert (by_name["Found"]["stage"], by_name["Found"]["how"]) == ("Sourced", "Found by search")
    assert by_name["Found"]["search_match"]["found"]["PolicyCenter"] == ["skills"]
    assert (by_name["Applied"]["stage"], by_name["Applied"]["how"]) == ("Sourced", "Applied")
    assert by_name["Interviewing"]["how"] == "On the hiring pipeline"
    assert "Elsewhere" not in by_name
    assert [row["stage"] for row in view["candidates"]] == sorted(
        (row["stage"] for row in view["candidates"]), key=list(workspace.STAGES).index)


def test_saving_the_workspace_keeps_every_field_and_skills_drive_matching_and_criteria(db, api):
    user = _user(db, full_access_role(db), "Recruiter")
    hm = _user(db, full_access_role(db), "Hiring Manager")
    job = _job(db, tenant_id=1, jobSkills="Guidewire", required_skills_canonical=[{"name": "Guidewire", "years": 5}])
    job_search.ensure_criteria(db, job)
    db.commit()
    url = f"/api/v1/jobs/{job.jobID}/workspace"

    saved = api.put(url, headers=_h(user), json={
        "job_title": "Senior PolicyCenter Developer", "employment_type": "CONTRACT", "urgency": "HIGH",
        "work_location": "HYBRID", "job_location": "Dallas, TX", "no_of_positions": 3, "min_experience_years": 6,
        "salary_range": "USD Annual 150000", "job_skills": "Guidewire, Gosu", "hiring_manager_id": hm.UserID,
        "start_date": "2026-12-01", "end_date": "2027-06-30", "job_description": "Configure PolicyCenter."})
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["job_title"], body["employment_type"], body["urgency"], body["work_location"], body["job_location"]) == (
        "Senior PolicyCenter Developer", "CONTRACT", "HIGH", "HYBRID", "Dallas, TX")
    assert (body["no_of_positions"], body["min_experience_years"], body["salary_range"]) == (3, 6.0, "USD Annual 150000")
    assert (body["hiring_manager_name"], body["start_date"], body["end_date"]) == ("Hiring Manager", "2026-12-01", "2027-06-30")
    assert api.get(url, headers=_h(user)).json() == body  # what was saved is what is read back

    db.refresh(job)
    assert job.required_skills_canonical == [{"name": "Guidewire", "years": 5}, {"name": "Gosu"}]
    criteria = db.get(JobSearchCriteria, job.jobID)
    db.refresh(criteria)
    assert criteria.boolean_query.endswith('AND "Gosu"')  # the system's criteria follow the job

    one = api.put(url, headers=_h(user), json={"urgency": ""})
    assert one.status_code == 200 and one.json()["urgency"] is None and one.json()["job_title"] == body["job_title"]


@pytest.mark.parametrize("fields, message", [
    ({"job_title": "  "}, "needs a title"),
    ({"no_of_positions": 0}, "at least one position"),
    ({"start_date": "2026-12-01", "end_date": "2026-11-01"}, "end date is before"),
    ({"employment_type": "C2C"}, "Position type must be one of"),
    ({"urgency": "ASAP"}, "Priority must be one of"),
    ({"work_location": "ONSITE", "job_location": ""}, "needs its location"),
    ({"job_skills": " , "}, "at least one skill"),
    ({"job_skills_boolean_mode": "XOR"}, "AND (all of them) or OR"),
    ({}, "Nothing to save"),
])
def test_a_save_that_would_leave_the_job_wrong_is_refused_with_the_reason(db, api, fields, message):
    user = _user(db, full_access_role(db), "Recruiter")
    job = _job(db, tenant_id=1)
    db.commit()
    answer = api.put(f"/api/v1/jobs/{job.jobID}/workspace", headers=_h(user), json=fields)
    assert answer.status_code == 400 and message in answer.json()["detail"], answer.text
    db.refresh(job)
    assert job.jobTitle == "PolicyCenter Developer"


def test_criteria_routes_run_now_and_permissions(db, api):
    user = _user(db, full_access_role(db), "Recruiter")
    outsider = _user(db, factories.role(db, 1), "Outsider")
    job = _job(db, tenant_id=1, jobSkills="Zylotech", required_skills_canonical=[{"name": "Zylotech"}])
    found = _person(db, "Priya", skills="Zylotech", tenant_id=1, timezone="UTC")
    db.commit()
    base = f"/api/v1/jobs/{job.jobID}"

    first = api.get(f"{base}/search-criteria", headers=_h(user))
    assert first.status_code == 200 and first.json()["query"] == '"Zylotech"' and not first.json()["edited"]
    edited = api.put(f"{base}/search-criteria", headers=_h(user), json={"query": "zylotech OR zylo"})
    assert edited.status_code == 200 and edited.json()["edited"] and edited.json()["edited_by_name"] == "Recruiter"
    assert api.put(f"{base}/search-criteria", headers=_h(user), json={"query": "zylotech AND"}).status_code == 400

    with patch(ENQUEUE, return_value=True):
        run = api.post(f"{base}/search-matches/run", headers=_h(user))
    assert run.status_code == 200, run.text
    assert (run.json()["captured"], run.json()["emails_queued"], run.json()["criteria"]["matches"]["contacted"]) == (1, 1, 1)
    matches = api.get(f"{base}/search-matches", headers=_h(user)).json()["matches"]
    assert [(m["candidate_id"], m["status"]) for m in matches] == [(found.candidateID, "CONTACTED")]
    people = api.get(f"{base}/candidates", headers=_h(user)).json()
    assert people["counts"]["Sourced"] == 1 and people["candidates"][0]["how"] == "Found by search"

    reset = api.post(f"{base}/search-criteria/reset", headers=_h(user))
    assert reset.status_code == 200 and reset.json()["query"] == '"Zylotech"' and not reset.json()["edited"]
    for method, path in (("get", "search-criteria"), ("get", "search-matches"), ("get", "candidates"), ("get", "workspace"),
                         ("post", "search-matches/run")):
        assert getattr(api, method)(f"{base}/{path}", headers=_h(outsider)).status_code == 403, path
    job.jobStatus = "closed"
    db.commit()
    assert api.post(f"{base}/search-matches/run", headers=_h(user)).status_code == 409
