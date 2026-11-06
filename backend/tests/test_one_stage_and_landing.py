"""CEO 2026-11-06: a candidate has one stage: the badge, the stage line and the stepper agree, nobody moves
a candidate ahead of what has happened, and logging an interview does what scheduling one does. People land
where their function says, else on their own profile. Workforce Overview filters by function, BU, company, location."""
from datetime import datetime

import pytest

from app.core import authority
from app.models.candidate import CandidateStatus
from app.models.candidate_history import CandidateHistory
from app.models.location import Location
from app.models.org_structure import Department
from app.models.task import Task
from app.models.user import Interview
from app.services import hiring_pipeline_service as pipeline
from app.services.candidate_journey_service import get_candidate_journey
from app.services.interview_log_service import INTERVIEW_TYPES, log_completed_interview, transcript_meta
from app.services.interview_verdict_service import infer_level
from app.services.workforce_report_service import workforce_filters, workforce_overview
from tests.scope_fixtures import ApiClient, scoped_role, uid
from tests.test_expense_review_and_pnl import _logger, db, w  # noqa: F401 -- fixtures


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@pytest.fixture
def person(db, w):
    from app.models.candidate import Candidate

    candidate = Candidate(candidateID=f"CAN-{uid()}", candidateFirstName="Raj", candidateLastName="P", candidateEmail=f"{uid()}@x.test",
                          tenant_id=1, total_experience_months=180, candidatePassword="x")
    db.add(candidate)
    db.flush()
    db.add(CandidateStatus(candidateID=candidate.candidateID, status="Active", piplineStatus="Applied"))
    db.commit()
    return candidate


def _log(db, w, person, round_name, recommendation="Hire"):
    return log_completed_interview(db, w.org_user, person, interview_type=round_name, meeting_platform="Teams",
                                   recommendation=recommendation, summary="Good", panel_member_ids=[],
                                   interview_start=datetime(2026, 11, 4, 16, 0))


def _status(db, person):
    db.expire_all()
    return db.query(CandidateStatus).filter_by(candidateID=person.candidateID).one().piplineStatus


def _stage(db, person):
    db.expire_all()
    return pipeline.get_or_create_pipeline(db, person.candidateID).stage


def test_both_forms_offer_rounds_that_lead_to_a_level():
    levels = {name: infer_level(name) for name in INTERVIEW_TYPES}
    assert levels["Screening"] == "SCREEN" and levels["L1 Interview"] == "L1" and levels["L2 Interview"] == "L2"


def test_logging_rounds_moves_the_stage_at_once_and_closes_the_schedule_task(db, w, person):
    _log(db, w, person, "Screening")
    assert _stage(db, person) == "L1" and _status(db, person) == "Interview"
    db.add(Task(title="Schedule L1 (technical) interview: Raj", category="INTERVIEW_SCHEDULING", candidate_id=person.candidateID, tenant_id=1))
    db.commit()
    _log(db, w, person, "L1 Interview")
    assert _stage(db, person) == "L2"
    task = db.query(Task).filter_by(candidate_id=person.candidateID, category="INTERVIEW_SCHEDULING").first()
    assert task.status == "COMPLETED"
    _log(db, w, person, "L2 Interview")
    assert _stage(db, person) == "OFFER"


def test_a_no_hire_logged_rejects_the_candidate(db, w, person):
    _log(db, w, person, "Screening", "No Hire")
    assert _stage(db, person) == "REJECTED"


@pytest.mark.parametrize("status", ["Pre-Onboarding", "Onboarded", "Hired", "OfferApproval", "Pre-onboarding-Approval"])
def test_a_manual_move_ahead_of_the_facts_is_refused_with_what_is_missing(db, w, person, api, status):
    _log(db, w, person, "Screening")
    res = api.put(w.org_user, f"/api/v1/status/{person.candidateID}", json={"pipeline_status": status})
    assert res.status_code == 409, res.text
    assert "L1 (technical) interview not scheduled" in res.json()["detail"]
    assert _status(db, person) == "Interview"


def test_a_move_the_facts_support_and_rejection_are_allowed(db, w, person, api):
    for round_name in ("Screening", "L1 Interview", "L2 Interview"):
        _log(db, w, person, round_name)
    pipeline.assert_status_allowed(db, person.candidateID, "Pre-Onboarding")
    pipeline.assert_status_allowed(db, person.candidateID, "Rejected")


def test_a_status_already_ahead_is_corrected_with_a_history_line(db, w, person):
    _log(db, w, person, "Screening")
    db.query(CandidateStatus).filter_by(candidateID=person.candidateID).update({"piplineStatus": "Pre-Onboarding"})
    db.commit()
    pipeline.evaluate_and_act(db, person.candidateID, "sweep")
    assert _status(db, person) == "Interview"
    note = db.query(CandidateHistory).filter_by(candidateID=person.candidateID, event_type="Custom Status Change").first().note
    assert "Pre-Onboarding -> Interview" in note and "L1 (technical) interview not scheduled" in note


def test_the_stepper_follows_the_real_interviews(db, w, person):
    _log(db, w, person, "Screening")
    journey = get_candidate_journey(db, person.candidateID, "1")
    assert journey["current_stage"] == "INTERVIEW"
    stages = {s["stage_name"]: s for s in journey["stages"]}
    assert stages["SCREENED"]["status"] == "completed" and stages["INTERVIEW"]["metrics"]["screening_outcome"] == "PASS"
    assert stages["INTERVIEW"]["entered_at"] == datetime(2026, 11, 4, 16, 0)


def test_a_logged_time_is_stored_in_utc_from_its_timezone(db, w, person, api):
    res = api.post(w.org_user, "/api/v1/interviews/log-completed", data={
        "candidate_id": person.candidateID, "interview_type": "Screening", "meeting_platform": "Teams", "recommendation": "Hire",
        "interview_date": "2026-11-04", "interview_time": "21:30", "timezone": "Asia/Kolkata", "summary": "Good"})
    assert res.status_code == 201, res.text
    assert db.get(Interview, res.json()["interview_id"]).start_time == datetime(2026, 11, 4, 16, 0)


@pytest.mark.parametrize("name", ["call.txt", "call.md"])
def test_a_text_or_markdown_transcript_is_accepted(db, w, person, api, name):
    res = api.post(w.org_user, "/api/v1/interviews/log-completed", data={
        "candidate_id": person.candidateID, "interview_type": "Screening", "meeting_platform": "Teams", "recommendation": "Hire",
        "interview_date": "2026-11-04"}, files={"transcript_file": (name, b"# Call\nHe knows BillingCenter", "text/plain")})
    assert res.status_code == 201, res.text
    got = api.get(w.org_user, f"/api/v1/interviews/{res.json()['interview_id']}/transcript").json()
    assert "BillingCenter" in got["transcript_text"] and got["transcript_file_name"] == name


def test_other_transcript_files_are_refused(db, w, person, api):
    res = api.post(w.org_user, "/api/v1/interviews/log-completed", data={
        "candidate_id": person.candidateID, "interview_type": "Screening", "meeting_platform": "Teams", "recommendation": "Hire",
        "interview_date": "2026-11-04"}, files={"transcript_file": ("call.pdf", b"x", "application/pdf")})
    assert res.status_code == 400 and transcript_meta("") == (None, None)


# ---- landing
def _function(db, name=None, **kw):
    function = Department(id=uid(), tenant_id=1, name=name or f"F-{uid()}", active=True, **kw)
    db.add(function)
    db.flush()
    return function


def test_someone_with_no_function_home_lands_on_their_profile(db, w):
    user = _logger(db, w)
    user.role_template_id = scoped_role(db).id
    user.department_id = _function(db).id
    db.commit()
    assert authority.home_dashboard(db, user) == "profile"


@pytest.mark.parametrize("home,permission", [("fy_progress", "revenue.view"), ("workforce", "workforce-overview.view"),
                                             ("recruitment", "candidates.view")])
def test_a_function_home_needs_its_permission(db, w, monkeypatch, home, permission):
    user = _logger(db, w)
    user.department_id = _function(db, home_screen=home).id
    db.commit()
    monkeypatch.setattr(authority, "_home", lambda session, person: None)
    monkeypatch.setattr(authority, "has_permission", lambda session, person, wanted: wanted == permission)
    assert authority.home_dashboard(db, user) == home
    monkeypatch.setattr(authority, "has_permission", lambda session, person, wanted: False)
    assert authority.home_dashboard(db, user) == "profile"


def test_the_function_form_saves_the_landing_page(db, w, api):
    res = api.post(w.org_user, "/api/v1/org/departments", json={"name": f"F-{uid()}", "home_screen": "workforce"})
    assert res.status_code in (200, 201), res.text and res.json()["home_screen"] == "workforce"
    assert api.post(w.org_user, "/api/v1/org/departments", json={"name": f"F-{uid()}", "home_screen": "nope"}).status_code == 400
    assert {"key": "fy_progress", "label": "FY progress"} in api.get(w.org_user, "/api/v1/org/departments/home-options").json()


# ---- workforce filters
def test_the_overview_filters_by_function_business_unit_company_and_location(db, w):
    india = Location(tenant_id=1, name=f"IN-{uid()}", country="India")
    us = Location(tenant_id=1, name=f"US-{uid()}", country="United States")
    db.add_all([india, us])
    db.flush()
    hr, dev = _function(db), _function(db)
    one = _logger(db, w, unit=w.bu_a, company=india)
    two = _logger(db, w, unit=w.bu_b, company=us)
    one.department_id, two.department_id = hr.id, dev.id
    db.commit()
    viewer = w.org_user
    base = workforce_overview(db, viewer)["headcount"]
    assert base >= 2
    assert workforce_overview(db, viewer, function_id=hr.id)["headcount"] == 1
    assert workforce_overview(db, viewer, company_id=us.id)["headcount"] == 1
    assert workforce_overview(db, viewer, business_unit_id=w.bu_a.id, function_id=dev.id)["headcount"] == 0
    assert workforce_overview(db, viewer, location="IN", function_id=hr.id)["headcount"] == 1
    choices = workforce_filters(db, viewer)
    assert {hr.id, dev.id} <= {f["id"] for f in choices["functions"]} and {"IN", "US"} <= set(choices["locations"])

