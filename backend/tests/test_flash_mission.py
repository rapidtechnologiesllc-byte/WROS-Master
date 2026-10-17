"""Flash missions (flash spec D with the CEO's 2026-10-15 decisions): after "I need a Rails developer
for my new client Acme", Flash sources and schedules interviews as the requester, reads verdicts
(never writes them), interviews up to FLASH_PARALLEL_CANDIDATES per open position, keeps going
through offers, and closes only when the candidate JOINS."""
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.candidate_skill_tag import CandidateSkillTag
from app.models.employee import Employee
from app.models.flash_conversation import FlashMessage
from app.models.flash_mission import FlashMission, FlashMissionCandidate
from app.models.interview_verdict import InterviewRoundVerdict
from app.models.offer_letter import OfferLetter
from app.models.role_template import Resource, RoleTemplate, RoleTemplatePermission
from app.models.task import Task
from app.models.user import Interview, InterviewFeedback, InterviewPanel, Jobs, PanelMember, Users
from app.services import flash_conversation_service as conversations
from app.services import flash_mission_service as missions
from app.services.flash_brain.agent import run_turn
from app.services.flash_brain.decisions import pending_decisions
from app.services.flash_brain.llm import Brains
from app.services.interview_slot_service import next_free_slot
from tests.flash_fakes import FakeLarge
from tests.flash_world import make_world, queued, role_without, uid, user  # noqa: F401 -- fixture

OFFLINE = Brains(small_offline_reason="FLASH_SMALL_LLM_BASE_URL is not set",
                 large_offline_reason="ANTHROPIC_API_KEY is not set")
SCAN = "app.services.ready_for_opportunity_service.scan_new_job_for_matches"


def _next_monday(after: datetime) -> datetime:
    """04:00 UTC (09:30 India) on the first Monday at least a week after `after`."""
    day = (after + timedelta(days=7)).date()
    while day.weekday() != 0:
        day += timedelta(days=1)
    return datetime(day.year, day.month, day.day, 4, 0)


NOW = _next_monday(datetime.utcnow())


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
def on(monkeypatch):
    monkeypatch.setattr(settings, "FLASH_MISSIONS_ENABLED", True)


@pytest.fixture
def world(db):
    return make_world(db)


def _cand(db, skill="Ruby on Rails", *, months=72, name="Priya", tz="Asia/Kolkata"):
    cand = Candidate(candidateID=f"CAN-{uid()}", candidateEmail=f"{uid()}@example.com", candidatePassword="x",
                     candidateFirstName=name, candidateLastName=f"S{uid()}", tenant_id=1,
                     total_experience_months=months, candidateSkills=skill, country="IN",
                     employment_type="FULLTIME", thunder_enabled=True, timezone=tz)
    db.add(cand)
    db.flush()
    db.add(CandidateSkillTag(tenant_id="1", candidate_id=cand.candidateID, skill_canonical=skill))
    db.flush()
    return cand


def _job(db, world, skill, *, hiring_manager="head", recruiter="recruiter", unit=None, client="client", positions=1):
    job = Jobs(jobID=f"JOB-{uid()}", tenant_id=1, jobTitle="Rails Developer", jobDescription="d", jobSkills=skill,
               required_skills_canonical=[{"name": skill, "is_primary": True}], jobExperience="5+ years",
               min_experience_years=5, jobLocation="Remote", work_location="REMOTE", jobStatus="active",
               noOfPositions=positions, companyName=world.client_name if client else None,
               client_id=world.client.id if client else None,
               business_unit_id=(unit or world.unit).id,
               hiringManagerID=getattr(world, hiring_manager).UserID if hiring_manager else None,
               recuriterID=getattr(world, recruiter).UserID if recruiter else None)
    db.add(job)
    db.flush()
    return job


def _mission(db, world, job, *, owner=None, positions=1, created=None):
    mission = missions.start_mission(db, owner or world.requester, job.jobID, positions)
    mission.next_check_at = NOW - timedelta(minutes=1)
    if created:
        mission.created_at = created
    db.flush()
    return mission


def _sweep(db, when=NOW, **kw):
    for mission in db.query(FlashMission).filter(FlashMission.state.in_(("AWAITING_JOB", "ACTIVE", "BLOCKED"))):
        mission.next_check_at = min(mission.next_check_at, when)
    db.flush()
    return missions.run_sweep(db, when, **kw)


def _tracks(db, mission):
    return db.query(FlashMissionCandidate).filter_by(mission_id=mission.id).order_by(FlashMissionCandidate.id).all()


def _feedback(db, track, recommendation):
    interview = db.get(Interview, track.interview_id)
    interview.status = "Completed"
    db.add(InterviewFeedback(interview_id=interview.id, interviewer_id=track.interviewer_user_id,
                             recommendation=recommendation, comments="x"))
    db.flush()


def _events(db, person):
    conversation = conversations.find_active(db, person.UserID)
    if conversation is None:
        return []
    return [m.body for m in db.query(FlashMessage).filter_by(conversation_id=conversation.id, role="event")
            .order_by(FlashMessage.id)]


# --------------------------------------------------------------------------- end to end

def _rails_by_chat(db, world, queued, brains):
    """The requester asks for a Rails developer in the Flash chat; returns the mission."""
    with patch(SCAN, return_value=[]):
        turns = [f"I need a Rails developer for my new client {world.client_name}"]
        turns += ["5 years, remote, 1 position", "yes"] if brains.large else ["Ruby on Rails", "5 years, remote, 1 position",
                                                                             "yes"]
        for text in turns:
            out = run_turn(db, world.requester, text, brains=brains)
        assert out["mission_id"] and out["reply"]
        payload = next(c.data for c in queued.enqueue if c.task_name == "job_created_flash")
        assert payload["structured_skills"][0]["name"] == "Ruby on Rails" and payload["client_id"] == world.client.id
        assert payload["tenant_id"] == 1 and payload["business_unit_id"] == world.unit.id
        mission = db.get(FlashMission, out["mission_id"])
        assert mission.state == "AWAITING_JOB" and mission.job_id == payload["job_id"]
        from app.services.message_handlers.job_creation_flash_handler import JobCreationFlashHandler

        JobCreationFlashHandler.process(SimpleNamespace(payload=payload, tenant_id=1, idempotency_key=None, id="m"), db)
    return mission, out


def _assert_scheduled(db, world, queued, mission):
    assert mission.state == "ACTIVE"
    (track,) = _tracks(db, mission)
    assert track.status == "SCHEDULED" and track.level == "L1"
    panel = db.get(InterviewPanel, track.panel_id)
    assert panel.job_id == mission.job_id and panel.round_name.startswith("L1")
    assert [m.interviewer_id for m in db.query(PanelMember).filter_by(panel_id=panel.id)] == [world.head.UserID]
    interview = db.get(Interview, track.interview_id)
    assert interview.start_time.weekday() < 5 and interview.start_time >= NOW + timedelta(hours=24)
    india = interview.start_time + timedelta(hours=5, minutes=30)
    assert 9 <= india.hour and (india + timedelta(hours=1)).time() <= datetime(2000, 1, 1, 17).time()
    assert any(c.task_name == "send_pipeline_email" and ":INTERVIEW_INVITE:" in c.task_id for c in queued.once)
    assert any("scheduled L1 for Priya" in body for body in _events(db, world.requester))
    return track


def test_rails_developer_end_to_end_with_claude(db, on, world, queued):
    candidate = _cand(db)
    large = FakeLarge(
        [("search_clients", {"name": world.client_name})],
        [("update_job_draft", {"title": "Rails Developer", "skills": ["Ruby on Rails"], "client_id": world.client.id})],
        "How many years, and where?",
        [("update_job_draft", {"min_experience_years": 5, "work_location": "REMOTE", "positions": 1})],
        "Create Rails Developer? yes/no",
        [("create_job", {})],
        "Queued; I'll report back here.",
        [("mission_status", {"query": "rails"})],
        "Your Rails search: 1 in interviews.",
    )
    brains = Brains(large=large, small_offline_reason="FLASH_SMALL_LLM_BASE_URL is not set")
    mission, _ = _rails_by_chat(db, world, queued, brains)
    _sweep(db)
    track = _assert_scheduled(db, world, queued, mission)
    assert track.candidate_id == candidate.candidateID
    run_turn(db, world.requester, "status of my Rails search", brains=brains)
    status_event = db.query(FlashMessage).filter(FlashMessage.role == "event").order_by(FlashMessage.id.desc()).first()
    assert status_event.payload["tool"] == "mission_status" and "1 in interviews" in status_event.body


def test_rails_developer_end_to_end_with_every_brain_offline(db, on, world, queued):
    _cand(db)
    mission, out = _rails_by_chat(db, world, queued, OFFLINE)
    assert out["reply"].endswith("I'll start sourcing within a few minutes and report back here.")
    _sweep(db)
    _assert_scheduled(db, world, queued, mission)
    reply = run_turn(db, world.requester, "status of my Rails search", brains=OFFLINE)["reply"]
    assert "Rails Developer" in reply and "1 in interviews (1 scheduled" in reply and "0 of 1 joined" in reply


def test_missions_need_the_switch_and_the_permission(db, world, queued):
    assert missions.run_sweep(db, NOW) == {"status": "disabled"}
    _cand(db)
    with patch(SCAN, return_value=[]):
        for text in (f"I need a Rails developer for my new client {world.client_name}", "Ruby on Rails",
                     "5 years, remote", "yes"):
            out = run_turn(db, world.requester, text, brains=OFFLINE)
    assert out["job_id"] and out["mission_id"] is None and db.query(FlashMission).filter_by(job_id=out["job_id"]).first() is None


# --------------------------------------------------------------------------- sourcing

def test_no_candidate_rechecks_then_finds_one_and_escalates_once(db, on, world, queued):
    skill = f"Rails{uid()}"
    job = _job(db, world, skill)
    mission = _mission(db, world, job)
    _sweep(db)
    assert mission.state == "ACTIVE" and _tracks(db, mission) == []
    assert mission.next_check_at == NOW + timedelta(hours=4)
    assert job.bench_first_checked and job.sourcing_enabled
    _cand(db, skill)
    missions.run_sweep(db, NOW + timedelta(hours=4, minutes=1))
    assert [t.status for t in _tracks(db, mission)] == ["SCHEDULED"]

    lonely = _job(db, world, f"Cobol{uid()}")
    stuck = _mission(db, world, lonely, created=NOW - timedelta(days=6))
    _sweep(db)
    _sweep(db, NOW + timedelta(hours=5))
    tasks = db.query(Task).filter(Task.link == f"/jobs/{lonely.jobID}").all()
    assert len(tasks) == 1 and tasks[0].assigned_to_user_id == world.recruiter.UserID
    assert tasks[0].title.startswith("No eligible match yet for Rails Developer") and stuck.state == "ACTIVE"


def test_ineligible_candidates_are_never_interviewed(db, on, world, queued):
    skill = f"Rails{uid()}"
    _cand(db, skill, months=48)
    job = _job(db, world, skill)
    mission = _mission(db, world, job)
    _sweep(db)
    assert _tracks(db, mission) == []

    later = _cand(db, skill, name="Later")
    db.add(FlashMissionCandidate(mission_id=mission.id, candidate_id=later.candidateID, status="PROPOSED"))
    later.total_experience_months = None  # unverified between pick and scheduling
    db.flush()
    _sweep(db, NOW + timedelta(hours=5))
    (track,) = _tracks(db, mission)
    assert track.status == "SKIPPED" and "not been verified" in track.reason and db.query(InterviewPanel).filter_by(
        candidate_id=later.candidateID).count() == 0

    from app.services import interview_scheduling_service as scheduling

    direct = _cand(db, skill, name="Direct")
    created = scheduling.create_panel(db, world.requester, candidate_id=direct.candidateID, job_id=job.jobID,
                                      round_name="L1 Technical", level="L1")
    direct.total_experience_months = 48
    with pytest.raises(HTTPException) as refused:
        scheduling.schedule_interview(db, world.requester, panel_id=created.panel.id, candidate_id=direct.candidateID,
                                      start=NOW + timedelta(days=1), end=NOW + timedelta(days=1, hours=1))
    assert refused.value.status_code == 400


def test_parallel_cap_is_per_open_position(db, on, world, queued, monkeypatch):
    assert settings.FLASH_PARALLEL_CANDIDATES == 20  # CEO 2026-10-15
    monkeypatch.setattr(settings, "FLASH_PARALLEL_CANDIDATES", 3)
    skill = f"Rails{uid()}"
    for i in range(8):
        _cand(db, skill, name=f"C{i}")
    job = _job(db, world, skill, positions=2)
    mission = _mission(db, world, job, positions=2)
    _sweep(db)
    tracks = _tracks(db, mission)
    assert len(tracks) == 6 and {t.status for t in tracks} == {"SCHEDULED"}
    starts = sorted(db.get(Interview, t.interview_id).start_time for t in tracks)
    assert all(b - a >= timedelta(minutes=60) for a, b in zip(starts, starts[1:]))  # one interviewer, no overlap


def test_offer_accepted_keeps_sourcing_and_joining_closes(db, on, world, queued, monkeypatch):
    monkeypatch.setattr(settings, "FLASH_PARALLEL_CANDIDATES", 1)
    skill = f"Rails{uid()}"
    first, second = _cand(db, skill, name="First"), _cand(db, skill, name="Second")
    job = _job(db, world, skill)
    mission = _mission(db, world, job)
    _sweep(db)
    (track,) = _tracks(db, mission)
    assert track.candidate_id in (first.candidateID, second.candidateID)
    _feedback(db, track, "Hire")
    _sweep(db, NOW + timedelta(hours=1))
    assert track.status == "SCHEDULED" and track.level == "L2"  # L1 pass -> L2
    _feedback(db, track, "Hire")
    _sweep(db, NOW + timedelta(hours=2))
    tracks = _tracks(db, mission)
    assert tracks[0].status == "OFFER_PENDING" and tracks[1].status == "SCHEDULED"  # still interviewing
    db.add(OfferLetter(candidate_id=track.candidate_id, job_id=job.jobID, position="Rails Developer", salary="1",
                       joining_date=date.today(), offer_expire_date=date.today() + timedelta(days=7),
                       offer_status="Accepted"))
    db.flush()
    _sweep(db, NOW + timedelta(hours=3))
    assert mission.state == "ACTIVE" and tracks[0].status == "OFFER_PENDING"  # accepted is not joined
    db.add(Employee(tenant_id=1, candidate_id=track.candidate_id, first_name="First", last_name="S",
                    email=f"{uid()}@blitzenx.com", joining_date=(NOW + timedelta(hours=4)).date(), status="BENCH"))
    db.flush()
    _sweep(db, NOW + timedelta(hours=4))
    assert tracks[0].status == "FILLED" and mission.state == "CLOSED"
    assert any("joined. Search closed." in body for body in _events(db, world.requester))


# --------------------------------------------------------------------------- the verdict boundary

def test_fail_moves_to_the_next_candidate_and_mixed_feedback_waits_for_a_person(db, on, world, queued, monkeypatch):
    monkeypatch.setattr(settings, "FLASH_PARALLEL_CANDIDATES", 1)
    skill = f"Rails{uid()}"
    for name in ("One", "Two"):
        _cand(db, skill, name=name)
    job = _job(db, world, skill)
    mission = _mission(db, world, job)
    _sweep(db)
    (first,) = _tracks(db, mission)
    _feedback(db, first, "No Hire")
    _sweep(db, NOW + timedelta(hours=1))
    first_after, second = _tracks(db, mission)
    assert first_after.status == "FAILED" and second.status == "SCHEDULED"
    _feedback(db, second, "Hold")
    _sweep(db, NOW + timedelta(hours=2))
    assert second.status == "AWAITING_HUMAN" and mission.state == "ACTIVE"
    verdict = db.query(InterviewRoundVerdict).filter_by(panel_id=second.panel_id).one()
    assert verdict.verdict == "NEEDS_DECISION" and verdict.source == "AUTO"  # computed from feedback, not Flash
    assert any(d.kind == "interview_verdict" and d.ref == str(second.panel_id) for d in pending_decisions(db, world.head))
    _sweep(db, NOW + timedelta(hours=3))
    assert second.status == "AWAITING_HUMAN" and len(_tracks(db, mission)) == 2  # no new write, no new candidate


# --------------------------------------------------------------------------- permissions and blocks

def test_a_requester_who_cannot_schedule_gets_a_hand_off(db, on, world, queued):
    skill = f"Rails{uid()}"
    cand = _cand(db, skill)
    requester = user(db, role_without(db, "interviews.create"), "No Interviews", business_unit_id=world.unit.id)
    job = _job(db, world, skill)
    mission = _mission(db, world, job, owner=requester)
    _sweep(db)
    assert mission.state == "BLOCKED" and mission.block_reason == "permission"
    task = db.query(Task).filter(Task.link == f"/candidates/{cand.candidateID}?tab=interview").one()
    assert task.assigned_to_user_id == world.recruiter.UserID
    assert db.query(Interview).filter_by(candidate_id=cand.candidateID).count() == 0
    assert any("you don't have permission to create interviews" in b for b in _events(db, requester))
    _sweep(db, NOW + timedelta(hours=1))
    assert db.query(Task).filter(Task.link == f"/candidates/{cand.candidateID}?tab=interview").count() == 1


def test_no_interviewer_blocks_with_a_task(db, on, world, queued):
    from app.models.business_unit import BusinessUnit

    skill = f"Rails{uid()}"
    _cand(db, skill)
    headless = BusinessUnit(tenant_id=1, name=f"bu-{uid()}", display_name="Headless")
    db.add(headless)
    db.flush()
    job = _job(db, world, skill, hiring_manager=None, unit=headless, client=None)
    mission = _mission(db, world, job)
    _sweep(db)
    assert mission.state == "BLOCKED" and mission.block_reason == "no_interviewer"
    assert db.query(Task).filter(Task.link == f"/jobs/{job.jobID}", Task.title.like("Assign an L1 interviewer%")).count() == 1


def test_the_recruiter_is_never_the_interviewer(db, on, world, queued):
    job = _job(db, world, "x", hiring_manager="recruiter", recruiter="recruiter")
    assert missions.resolve_interviewer(db, job, "L1", 1).UserID == world.head.UserID  # client's BU head


def test_owner_who_left_hands_over_to_the_hiring_manager(db, on, world, queued):
    skill = f"Rails{uid()}"
    _cand(db, skill)
    job = _job(db, world, skill)
    mission = _mission(db, world, job)
    world.requester.terminated_at = NOW - timedelta(days=1)
    db.flush()
    _sweep(db)
    assert mission.requested_by_user_id == world.head.UserID and mission.state == "ACTIVE"
    assert any("is now yours" in b for b in _events(db, world.head))
    assert [t.status for t in _tracks(db, mission)] == ["SCHEDULED"]

    orphan_job = _job(db, world, skill, hiring_manager=None)
    leaver = user(db, world.role, "Leaver", business_unit_id=world.unit.id)
    orphan = _mission(db, world, orphan_job, owner=leaver)
    leaver.terminated_at = NOW - timedelta(days=1)
    db.flush()
    _sweep(db, NOW + timedelta(hours=1))
    assert orphan.state == "BLOCKED" and orphan.block_reason == "owner_inactive"


# --------------------------------------------------------------------------- idempotency, control, guard

def test_start_and_sweep_are_idempotent(db, on, world, queued):
    skill = f"Rails{uid()}"
    _cand(db, skill)
    job = _job(db, world, skill)
    mission = _mission(db, world, job)
    assert missions.start_mission(db, world.requester, job.jobID, 1).id == mission.id
    assert db.query(FlashMission).filter_by(job_id=job.jobID).count() == 1
    _sweep(db)
    _sweep(db, NOW + timedelta(hours=1))
    assert db.query(InterviewPanel).filter_by(job_id=job.jobID).count() == 1
    assert db.query(Interview).join(InterviewPanel, InterviewPanel.id == Interview.panel_id).filter(
        InterviewPanel.job_id == job.jobID).count() == 1


def test_pause_resume_cancel_by_chat_and_who_may(db, on, world, queued):
    job = _job(db, world, f"Rails{uid()}")
    mission = _mission(db, world, job)
    assert run_turn(db, world.requester, "pause my Rails search", brains=OFFLINE)["reply"].endswith(
        "Say resume to continue.")
    assert mission.state == "PAUSED"
    stranger = user(db, role_without(db, "jobs.edit"), "Stranger")
    with pytest.raises(missions.MissionError):
        missions.control(db, stranger, mission, "resume")
    assert "Resumed" in run_turn(db, world.requester, "resume my Rails search", brains=OFFLINE)["reply"]
    run_turn(db, world.requester, "cancel my Rails search", brains=OFFLINE)
    assert mission.state == "CANCELLED"


def test_backlog_guard_fails_missions_whose_job_never_appeared(db, on, world):
    mission = missions.start_mission(db, world.requester, f"JOB-{uid()}", 1)
    mission.created_at = NOW - timedelta(days=2)
    db.flush()
    missions.backlog_guard(db, NOW)
    assert mission.state == "FAILED"


def test_flash_missions_create_follows_jobs_create(db):
    from app.core.db_contract import _initialize_derived_grants
    from tests.hiring_fixtures import full_access_role

    full_access_role(db)  # resources exist
    jobs_ids = [r.id for r in db.query(Resource).filter_by(name="jobs")]
    roles = {}
    for name, may_create in (("maker", True), ("viewer", False)):
        role = RoleTemplate(tenant_id=1, name=f"{name}-{uid()}", display_name=name, enabled=True)
        db.add(role)
        db.flush()
        db.add(RoleTemplatePermission(role_template_id=role.id, resource_id=jobs_ids[0], tenant_id=1, can_view=True,
                                      can_create=may_create))
        roles[name] = role
    db.flush()
    _initialize_derived_grants(db)
    _initialize_derived_grants(db)
    mission_ids = [r.id for r in db.query(Resource).filter_by(name="flash-missions")]
    for name, expected in (("maker", True), ("viewer", False)):
        rows = db.query(RoleTemplatePermission).filter(RoleTemplatePermission.role_template_id == roles[name].id,
                                                       RoleTemplatePermission.resource_id.in_(mission_ids)).all()
        assert len(rows) == 1 and rows[0].can_create is expected


# --------------------------------------------------------------------------- slots

def _person_tz(tz):
    return SimpleNamespace(UserID=f"U-{uid()}", UserEmail="i@blitzenx.com", timezone=tz)


def _busy(db, interviewer, start, hours):
    """A scheduled interview occupying the interviewer for `hours` from `start`."""
    cand = _cand(db, name="Busy")
    panel = InterviewPanel(candidate_id=cand.candidateID, round_name="L1")
    db.add(panel)
    db.flush()
    db.add(PanelMember(panel_id=panel.id, interviewer_id=interviewer.UserID))
    db.add(Interview(panel_id=panel.id, candidate_id=cand.candidateID, start_time=start,
                     end_time=start + timedelta(hours=hours), status="Scheduled"))
    db.flush()


def test_slot_skips_a_full_day_and_the_weekend(db, world):
    cand = _cand(db)
    interviewer = world.head
    tuesday = NOW + timedelta(days=1)
    _busy(db, interviewer, tuesday.replace(hour=3, minute=30), 8)  # all of Tuesday, 09:00-17:00 India
    start, end = next_free_slot(db, interviewer, cand, now=NOW)
    assert start.date() == (NOW + timedelta(days=2)).date() and end - start == timedelta(minutes=60)
    friday_evening = NOW + timedelta(days=4, hours=8)  # Friday 17:30 India
    start, _ = next_free_slot(db, interviewer, cand, now=friday_evening - timedelta(hours=24))
    assert start.weekday() == 0  # Monday


def test_slot_respects_graph_busy_times_and_both_time_zones(db, world):
    cand = _cand(db)
    tuesday = (NOW + timedelta(days=1)).replace(hour=0, minute=0)
    busy = [(tuesday.replace(hour=3, minute=30), tuesday.replace(hour=6))]
    from datetime import timezone

    calls = []

    def graph(email, start, end):
        calls.append(email)
        return [(s.replace(tzinfo=timezone.utc), e.replace(tzinfo=timezone.utc)) for s, e in busy]

    start, _ = next_free_slot(db, world.head, cand, now=NOW, graph_call=graph)
    assert calls == [world.head.UserEmail] and start == tuesday.replace(hour=6, minute=15)  # after the 15-minute buffer
    london = _cand(db, tz="Europe/London")
    start, _ = next_free_slot(db, world.head, london, now=NOW)
    assert start.hour >= 7 and start.time() < datetime(2000, 1, 1, 11, 30).time()  # London 9:00 is 08:00/09:00 UTC
    new_york = _cand(db, tz="America/New_York")
    assert next_free_slot(db, world.head, new_york, now=NOW) is None  # no shared business hours with India


def test_missing_feedback_is_chased_then_the_hiring_manager_is_told(db, on, world, queued):
    skill = f"Rails{uid()}"
    _cand(db, skill)
    job = _job(db, world, skill)
    mission = _mission(db, world, job)
    _sweep(db)
    (track,) = _tracks(db, mission)
    ended = db.get(Interview, track.interview_id).end_time
    for hours in (1, 25, 26, 50):
        _sweep(db, ended + timedelta(hours=hours))
    assert track.status == "AWAITING_VERDICT" and track.feedback_chases == 2
    assert sum("feedback on Priya" in b for b in _events(db, world.head)) == 2  # the head interviews here
    assert any("still missing after 2 reminders" in b for b in _events(db, world.head))


def test_the_sweep_is_a_guarded_scheduled_job():
    from app.core.scheduled_jobs import JOBS
    from app.workers.scheduled_jobs_worker import enabled_jobs

    job = JOBS["flash_mission_sweep"]
    assert job.sends_external and job.backlog_guard and job.interval == timedelta(minutes=5)
    assert enabled_jobs("flash_mission_sweep", JOBS) == [job]
