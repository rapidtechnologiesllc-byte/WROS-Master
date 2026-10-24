"""Employee performance (CEO 2026-10-24): scheduled reviews by the reporting chain, Teams meeting and
recording, the reviewer's write-up and who sees it, peer praise / feedback, internal notes."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.models.business_unit import BusinessUnitLocationHead
from app.models.location import Location
from app.models.performance import PerformanceReview
from app.models.role_template import Module, Resource, RoleTemplate, RoleTemplatePermission
from app.models.task import Task
from app.services import performance_service as perf
from app.services import performance_teams
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient

JOINED = date(2026, 1, 5)
TODAY = date(2026, 1, 20)


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def _role(db, views, specialization="General"):
    """A role granting view on these contract resources (created if missing)."""
    from app.contracts.api_contract import MODULES_AND_RESOURCES

    role = RoleTemplate(tenant_id=1, name=f"perf-{factories.uid()}", display_name="Perf", hierarchy_level=5,
                        enabled=True, org_level_access=False, specialization=specialization)
    db.add(role)
    db.flush()
    for name in views:
        module_name = next(m for m, names in MODULES_AND_RESOURCES.items() if name in names)
        module = db.query(Module).filter_by(name=module_name).first()
        if module is None:
            module = Module(tenant_id=1, name=module_name, display_name=module_name, enabled=True)
            db.add(module)
            db.flush()
        resource = db.query(Resource).filter_by(module_id=module.id, name=name).first()
        if resource is None:
            resource = Resource(tenant_id=1, module_id=module.id, name=name, display_name=name, enabled=True)
            db.add(resource)
            db.flush()
        db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=resource.id, tenant_id=1, can_view=True))
    db.flush()
    return role


@pytest.fixture
def world(db):
    unit = factories.business_unit(db)
    company = Location(tenant_id=1, name=f"co-{factories.uid()}")
    db.add(company)
    db.flush()
    staff_role = _role(db, ["my-tasks", "employees"])
    manager = factories.user(db, UserName="Mira Manager", role_template_id=staff_role.id)
    bu_head = factories.user(db, UserName="Hari Head", role_template_id=staff_role.id)
    partner = factories.user(db, UserName="Paul Partner", role_template_id=staff_role.id)
    hr = factories.user(db, UserName="Hema HR", role_template_id=_role(db, ["my-tasks", "employees"], "HR").id)
    peer = factories.user(db, UserName="Pia Peer", role_template_id=staff_role.id)
    peer2 = factories.user(db, UserName="Raj Peer", role_template_id=staff_role.id)
    me = factories.user(db, UserName="Asha Rao", role_template_id=_role(db, ["my-tasks"]).id)
    unit.partner_user_id = partner.UserID
    db.add(BusinessUnitLocationHead(tenant_id=1, business_unit_id=unit.id, company_id=company.id,
                                    head_user_id=bu_head.UserID))
    factories.employee(db, wros_user_id=manager.UserID, first_name="Mira", last_name="Manager", status="ALLOCATED",
                       joining_date=date(2024, 1, 1))
    employee = factories.employee(db, wros_user_id=me.UserID, first_name="Asha", last_name="Rao", status="BENCH",
                                  bu_id=unit.id, company_id=company.id, joining_date=JOINED,
                                  reporting_manager_user_id=manager.UserID)
    db.commit()
    return SimpleNamespace(unit=unit, company=company, manager=manager, bu_head=bu_head, partner=partner, hr=hr,
                           peer=peer, peer2=peer2, me=me, employee=employee)


def _reviews(db, world, **filters):
    return db.query(PerformanceReview).filter(PerformanceReview.employee_id == world.employee.id, **{}) \
        .filter_by(**filters).order_by(PerformanceReview.level).all()


def _open(db, world, today=TODAY):
    result = perf.run_performance_reviews(db, today=today, now=datetime.combine(today, datetime.min.time()))
    db.expire_all()
    return result


# --- periods and reviewers ---------------------------------------------------------------------

def test_periods_manager_fortnights_from_joining_month_and_quarter(world):
    assert perf.period("MANAGER", world.employee, TODAY) == (date(2026, 1, 19), date(2026, 2, 1))
    assert perf.period("MANAGER", world.employee, JOINED) == (JOINED, date(2026, 1, 18))
    assert perf.period("BU_HEAD", world.employee, TODAY) == (date(2026, 1, 1), date(2026, 1, 31))
    assert perf.period("PARTNER", world.employee, date(2026, 5, 9)) == (date(2026, 4, 1), date(2026, 6, 30))


def test_reviewer_at_each_level(db, world):
    assert perf.reviewer_for(db, "MANAGER", world.employee).UserID == world.manager.UserID
    assert perf.reviewer_for(db, "BU_HEAD", world.employee).UserID == world.bu_head.UserID
    assert perf.reviewer_for(db, "PARTNER", world.employee).UserID == world.partner.UserID
    world.employee.bu_id = None
    assert perf.reviewer_for(db, "BU_HEAD", world.employee) is None
    assert perf.reviewer_for(db, "PARTNER", world.employee) is None


# --- the job -----------------------------------------------------------------------------------

def test_job_opens_one_review_per_level_with_a_task_idempotently(db, world):
    _open(db, world)
    reviews = _reviews(db, world)
    assert {r.level: r.reviewer_user_id for r in reviews} == {
        "MANAGER": world.manager.UserID, "BU_HEAD": world.bu_head.UserID, "PARTNER": world.partner.UserID}
    for review in reviews:
        task = db.query(Task).filter(Task.id == review.task_id).one()
        assert task.assigned_to_user_id == review.reviewer_user_id
        assert task.link == f"/employees/{world.employee.id}?tab=performance&review={review.id}"
        assert review.status == "PENDING" and review.due_date == review.period_end
    _open(db, world)
    assert len(_reviews(db, world)) == 3


@pytest.mark.parametrize("status", ["PRE_JOINING", "NOTICE_PERIOD", "EXITED"])
def test_people_not_reviewed(db, world, status):
    world.employee.status = status
    db.commit()
    _open(db, world)
    assert _reviews(db, world) == []


def test_serving_notice_cancels_open_reviews_and_their_tasks(db, world):
    _open(db, world)
    world.employee.status = "NOTICE_PERIOD"
    db.commit()
    _open(db, world)
    reviews = _reviews(db, world)
    assert {r.status for r in reviews} == {"CANCELLED"}
    assert {t.status for t in db.query(Task).filter(Task.id.in_([r.task_id for r in reviews]))} == {"COMPLETED"}


def test_reviews_past_due_are_missed_and_the_next_period_opens(db, world):
    _open(db, world)
    _open(db, world, today=date(2026, 2, 2))
    manager_reviews = _reviews(db, world, level="MANAGER")
    assert [(r.period_start, r.status) for r in manager_reviews] == [
        (date(2026, 1, 19), "MISSED"), (date(2026, 2, 2), "PENDING")]


def test_teams_features_are_off_by_default():
    assert settings.PERF_REVIEW_TEAMS_ENABLED is False
    assert settings.PERF_REVIEW_FETCH_RECORDINGS is False


def test_meeting_is_booked_and_recorded_when_teams_is_on(db, world, monkeypatch):
    booked, recorded = [], []
    monkeypatch.setattr(settings, "PERF_REVIEW_TEAMS_ENABLED", True)
    monkeypatch.setattr(performance_teams, "book_meeting",
                        lambda **kw: (booked.append(kw) or ("event-1", "https://teams.example/join/1")))
    monkeypatch.setattr(performance_teams, "record_automatically", lambda url: recorded.append(url))
    _open(db, world)
    review = _reviews(db, world, level="MANAGER")[0]
    assert review.status == "SCHEDULED" and review.meeting_join_url == "https://teams.example/join/1"
    assert review.meeting_start.date() <= review.due_date
    assert review.meeting_start.weekday() < 5 and review.meeting_start.hour == settings.PERF_REVIEW_MEETING_HOUR
    assert (review.meeting_end - review.meeting_start) == timedelta(minutes=settings.PERF_REVIEW_MEETING_MINUTES)
    assert booked[0]["attendee_emails"] == [world.manager.UserEmail, world.employee.email]
    assert "https://teams.example/join/1" in recorded


def test_a_booking_failure_is_recorded_and_not_retried(db, world, monkeypatch):
    calls = []

    def fail(**kw):
        calls.append(kw)
        raise performance_teams.GraphError("Booking the Teams meeting: HTTP 403 Access denied")

    monkeypatch.setattr(settings, "PERF_REVIEW_TEAMS_ENABLED", True)
    monkeypatch.setattr(performance_teams, "book_meeting", fail)
    _open(db, world)
    review = _reviews(db, world, level="MANAGER")[0]
    assert review.status == "PENDING" and "HTTP 403" in review.meeting_note
    count = len(calls)
    _open(db, world)
    assert len(calls) == count


def _scheduled(db, world):
    review = _reviews(db, world, level="MANAGER")[0]
    review.meeting_join_url = "https://teams.example/join/1"
    review.meeting_end = datetime(2026, 1, 21, 12, 0)
    review.status = "SCHEDULED"
    db.commit()
    return review


def test_recording_is_pulled_from_teams_after_the_meeting(db, world, monkeypatch, tmp_path):
    _open(db, world)
    review = _scheduled(db, world)
    monkeypatch.setattr(settings, "PERF_REVIEW_FETCH_RECORDINGS", True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(performance_teams, "fetch_recording", lambda url, max_bytes: b"video-bytes")
    perf.run_performance_reviews(db, today=date(2026, 1, 22), now=datetime(2026, 1, 22, 9, 0))
    db.refresh(review)
    assert review.recording_source == "TEAMS"
    with open(review.recording_path, "rb") as handle:
        assert handle.read() == b"video-bytes"


@pytest.mark.parametrize("outcome, message", [
    (None, "Teams has no recording for this meeting yet"),
    (performance_teams.GraphError("Listing the meeting recordings: HTTP 403 denied"), "HTTP 403 denied"),
])
def test_recording_fetch_problems_are_recorded(db, world, monkeypatch, tmp_path, outcome, message):
    _open(db, world)
    review = _scheduled(db, world)

    def fetch(url, max_bytes):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(settings, "PERF_REVIEW_FETCH_RECORDINGS", True)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(performance_teams, "fetch_recording", fetch)
    perf.run_performance_reviews(db, today=date(2026, 1, 22), now=datetime(2026, 1, 22, 9, 0))
    db.refresh(review)
    assert review.recording_path is None and message in review.recording_fetch_error


# --- reviews: writing and who sees them ----------------------------------------------------------

def _seen(api, user, world):
    response = api.get(user, f"/api/v1/performance/employees/{world.employee.id}")
    assert response.status_code == 200, response.text
    return response.json()


def test_chain_and_hr_see_reviews_peers_do_not(db, api, world):
    _open(db, world)
    assert len(_seen(api, world.manager, world)["reviews"]) == 3
    assert len(_seen(api, world.partner, world)["reviews"]) == 3
    assert len(_seen(api, world.hr, world)["reviews"]) == 3
    assert _seen(api, world.peer, world)["reviews"] == []
    assert api.get(world.me, "/api/v1/performance/me").json()["reviews"] == []


def test_reviewer_writes_and_completes_and_the_employee_sees_only_what_is_shared(db, api, world):
    _open(db, world)
    manager_review, bu_review = (_reviews(db, world, level=level)[0] for level in ("MANAGER", "BU_HEAD"))
    url = f"/api/v1/performance/reviews/{manager_review.id}"
    assert api.put(world.peer, url, json={"summary": "x"}).status_code == 403
    assert api.put(world.manager, url, json={"rating": 9}).status_code == 400
    assert api.put(world.manager, url, json={"summary": "Good fortnight", "complete": True}).status_code == 400
    saved = api.put(world.manager, url, json={"rating": 4, "summary": "Good fortnight", "goals": "Lead a demo",
                                               "visibility": "EMPLOYEE_AND_CHAIN"})
    assert saved.status_code == 200 and saved.json()["status"] == "PENDING"
    assert api.get(world.me, "/api/v1/performance/me").json()["reviews"] == []  # not until completed
    done = api.put(world.manager, url, json={"complete": True})
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "COMPLETED"
    assert db.query(Task).filter(Task.id == manager_review.task_id).one().status == "COMPLETED"
    assert api.put(world.manager, url, json={"summary": "changed"}).status_code == 400  # final
    api.put(world.bu_head, f"/api/v1/performance/reviews/{bu_review.id}",
            json={"rating": 3, "summary": "Chain only", "visibility": "CHAIN_ONLY", "complete": True})
    mine = api.get(world.me, "/api/v1/performance/me").json()
    assert [r["summary"] for r in mine["reviews"]] == ["Good fortnight"]


def test_reviews_i_owe_are_listed_on_my_performance(db, api, world):
    _open(db, world)
    owed = api.get(world.manager, "/api/v1/performance/me").json()
    assert [(r["employee_id"], r["employee_name"], r["level_label"]) for r in owed["to_review"]] == [
        (world.employee.id, "Asha Rao", "Reporting manager")]


# --- peer feedback and notes -------------------------------------------------------------------

def test_praise_for_all_feedback_for_the_chain_and_the_anonymous_author_for_hr_only(db, api, world):
    url = f"/api/v1/performance/employees/{world.employee.id}/feedback"
    assert api.post(world.peer, url, json={"kind": "PRAISE", "body": "Great demo!"}).status_code == 201
    assert api.post(world.peer, url, json={"kind": "FEEDBACK", "body": "Share updates earlier",
                                           "anonymous": True}).status_code == 201
    assert api.post(world.me, url, json={"kind": "PRAISE", "body": "Me!"}).status_code == 400
    assert api.post(world.peer, url, json={"kind": "GOSSIP", "body": "nope"}).status_code == 400

    def authors(user):
        data = _seen(api, user, world) if user is not world.me else api.get(user, "/api/v1/performance/me").json()
        return {item["kind"]: item["author_name"] for item in data["feedback"]}

    assert authors(world.peer2) == {"PRAISE": "Pia Peer"}  # another peer: praise only
    assert authors(world.me) == {"PRAISE": "Pia Peer", "FEEDBACK": None}
    assert authors(world.manager) == {"PRAISE": "Pia Peer", "FEEDBACK": None}
    assert authors(world.hr) == {"PRAISE": "Pia Peer", "FEEDBACK": "Pia Peer"}
    assert authors(world.peer) == {"PRAISE": "Pia Peer", "FEEDBACK": "Pia Peer"}  # the author


def test_internal_notes_are_for_the_chain_and_hr(db, api, world):
    url = f"/api/v1/performance/employees/{world.employee.id}/notes"
    assert api.post(world.manager, url, json={"body": "Discussed workload"}).status_code == 201
    assert api.post(world.peer, url, json={"body": "Not mine to write"}).status_code == 403
    assert [n["body"] for n in _seen(api, world.hr, world)["notes"]] == ["Discussed workload"]
    assert _seen(api, world.peer, world)["notes"] == []
    assert api.get(world.me, "/api/v1/performance/me").json()["notes"] == []


def test_colleagues_list_excludes_me(db, api, world):
    names = [c["name"] for c in api.get(world.me, "/api/v1/performance/colleagues").json()["colleagues"]]
    assert "Asha Rao" not in names and "Mira Manager" in names


# --- recordings --------------------------------------------------------------------------------

def test_recording_upload_link_and_access_checked_download(db, api, world, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    _open(db, world)
    review = _reviews(db, world, level="MANAGER")[0]
    base = f"/api/v1/performance/reviews/{review.id}"
    assert api.post(world.manager, f"{base}/recording",
                    files={"file": ("notes.txt", b"hello", "text/plain")}).status_code == 400
    assert api.post(world.peer, f"{base}/recording",
                    files={"file": ("s.mp4", b"video", "video/mp4")}).status_code == 403
    monkeypatch.setattr(settings, "PERF_REVIEW_RECORDING_MAX_BYTES", 3)
    assert api.post(world.manager, f"{base}/recording",
                    files={"file": ("s.mp4", b"video", "video/mp4")}).status_code == 400
    monkeypatch.setattr(settings, "PERF_REVIEW_RECORDING_MAX_BYTES", 1024)
    assert api.post(world.manager, f"{base}/recording",
                    files={"file": ("s.mp4", b"video", "video/mp4")}).status_code == 200
    assert api.get(world.manager, f"{base}/recording").content == b"video"
    assert api.get(world.me, f"{base}/recording").status_code == 404  # not shared with them
    assert api.get(world.peer, f"{base}/recording").status_code == 404
    assert api.put(world.manager, f"{base}/recording-link", json={"url": "http://x"}).status_code == 400
    linked = api.put(world.manager, f"{base}/recording-link", json={"url": "https://stream.example/rec/1"})
    assert linked.status_code == 200 and linked.json()["recording_source"] == "LINK"


def test_my_performance_works_without_an_employee_record(db, api, world):
    _open(db, world)
    owed = api.get(world.bu_head, "/api/v1/performance/me")
    assert owed.status_code == 200, owed.text
    data = owed.json()
    assert data["employee_id"] is None and data["reviews"] == []
    assert [r["level_label"] for r in data["to_review"]] == ["BU head"]
