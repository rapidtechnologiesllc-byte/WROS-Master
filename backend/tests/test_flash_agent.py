"""Flash as an agent (flash spec C): a tool registry checked against the requester's permissions
twice (offered, then executed), every call an event message, no tool for any decision people take,
and a job created by talking to Flash -- the same job whether Claude, the small model or only the
rules are up."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.flash_conversation import FlashMessage
from app.services import flash_conversation_service as conversations
from app.services.flash_brain import tools as flash_tools
from app.services.flash_brain.agent import run_turn
from app.services.flash_brain.llm import BrainUnavailable, Brains, get_brains
from app.services.flash_brain.tools import FORBIDDEN_TOOL_WORDS, TOOLS, ToolContext, execute, tools_for
from tests.flash_fakes import FakeLarge, FakeSmall
from tests.flash_world import headers, make_world, queued, role_without, uid, user  # noqa: F401 -- fixture

OFFLINE = Brains(small_offline_reason="FLASH_SMALL_LLM_BASE_URL is not set",
                 large_offline_reason="ANTHROPIC_API_KEY is not set")


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
def world(db):
    return make_world(db)


def _ctx(db, person):
    from datetime import datetime

    return ToolContext(db, person, conversations.active_conversation(db, person), datetime.utcnow())


def _job_payload(queued):
    calls = [c for c in queued.enqueue if c.task_name == "job_created_flash"]
    assert len(calls) == 1, [c.task_name for c in queued.enqueue]
    return calls[0].data


# --------------------------------------------------------------------------- the registry

def test_no_tool_takes_a_decision_people_take():
    flash_tools._load_registry()
    for name in TOOLS:
        assert not any(word in name for word in FORBIDDEN_TOOL_WORDS), name
    assert "create_job" in TOOLS and "update_job_draft" in TOOLS
    with pytest.raises(ValueError):
        flash_tools.register(flash_tools.FlashTool("record_verdict", "x", flash_tools.schema({}), None,
                                                   lambda c, a: {}, "x"))


def test_every_offered_tool_is_strict(db, world):
    for tool in tools_for(db, world.requester):
        assert tool.input_schema["additionalProperties"] is False
        assert set(tool.input_schema["required"]) == set(tool.input_schema["properties"]), tool.name


def test_finance_is_never_offered_to_a_model(db, world):
    names = {t.name for t in tools_for(db, world.requester)}
    assert "bu_pnl" not in names and "overdue_invoices" not in names


def test_a_tool_is_offered_and_executed_only_with_the_permission(db, world, queued):
    clerk = user(db, role_without(db, "jobs.create", "employees.view"), "Clerk")
    names = {t.name for t in tools_for(db, clerk)}
    assert "create_job" not in names and "update_job_draft" not in names and "bench_availability" not in names
    assert "find_candidates" in names
    ctx = _ctx(db, clerk)
    outcome = execute(ctx, "update_job_draft", {"title": "Rails Developer"})
    assert outcome == {"error": "You don't have permission to create jobs."}
    assert execute(ctx, "create_job", {})["error"] == "You don't have permission to create jobs."
    assert queued.enqueue == [] and ctx.conversation.active_workflow is None
    event = db.query(FlashMessage).filter_by(conversation_id=ctx.conversation.id, role="event").all()
    assert [e.payload["tool"] for e in event] == ["update_job_draft", "create_job"]
    assert all(e.payload["ok"] is False for e in event)


def test_create_job_needs_the_users_yes(db, world, queued):
    ctx = _ctx(db, world.requester)
    execute(ctx, "update_job_draft", {"title": "Rails Developer", "skills": ["Ruby on Rails"], "client_id": world.client.id,
                                      "min_experience_years": 5, "work_location": "REMOTE"})
    assert ctx.state["confirm"]["action"] == "create_job"
    assert execute(ctx, "create_job", {})["error"].startswith("Not confirmed yet. Ask the user: Create Rails Developer")
    assert queued.enqueue == []


# --------------------------------------------------------------------------- creating a job by chat

def _say(db, person, text, brains):
    return run_turn(db, person, text, brains=brains)


def _assert_rails_job(payload, world):
    assert payload["tenant_id"] == 1 and payload["client_id"] == world.client.id
    assert payload["business_unit_id"] == world.unit.id and payload["company_name"] == world.client_name
    assert payload["structured_skills"][0]["name"] == "Ruby on Rails" and payload["structured_skills"][0]["is_primary"]
    assert payload["min_experience_years"] == 5 and payload["work_location"] == "REMOTE"
    assert payload["job_title"] == "Rails Developer" and payload["company_type"] == "Full time"
    assert payload["no_of_positions"] == 1 and payload["job_location"] == "Remote"
    assert payload["hiring_manager_id"] == world.head.UserID  # the client's BU Head
    assert payload["created_by_user_id"] == world.requester.UserID


def test_job_by_chat_with_every_brain_offline(db, world, queued):
    first = _say(db, world.requester, f"I need a Rails developer for my new client {world.client_name}", OFFLINE)
    assert first["reply"].startswith("Heads-up: my planning brain (Claude) is offline because ANTHROPIC_API_KEY")
    assert "my parsing model is offline because FLASH_SMALL_LLM_BASE_URL is not set" in first["reply"]
    assert first["reply"].endswith("Which skills are required? (comma-separated)")
    assert first["active_workflow"] == "job_intake"
    assert _say(db, world.requester, "Ruby on Rails", OFFLINE)["reply"] == \
        "How many years of experience does the role need?"
    confirm = _say(db, world.requester, "5 years, remote, 1 position", OFFLINE)["reply"]
    assert confirm == (f"Create Rails Developer for {world.client_name} (Ruby on Rails; 5+ years; remote; "
                       "1 position; Full time)? yes/no")
    assert queued.enqueue == []
    done = _say(db, world.requester, "yes", OFFLINE)
    payload = _job_payload(queued)
    _assert_rails_job(payload, world)
    assert done["job_id"] == payload["job_id"] and done["reply"] == \
        f"Job {payload['job_id']} for {world.client_name} is queued."
    assert done["active_workflow"] is None
    assert payload["job_description"] == f"Rails Developer for {world.client_name}. Required: Ruby on Rails; 5+ years."


def test_job_by_chat_with_claude_gives_the_same_job(db, world, queued):
    large = FakeLarge(
        [("search_clients", {"name": world.client_name})],
        [("update_job_draft", {"title": "Rails Developer", "skills": ["Ruby on Rails"], "client_id": world.client.id,
                               "client_name": None, "description": None, "min_experience_years": None,
                               "location": None, "work_location": None, "company_type": None, "positions": None})],
        "How many years of experience, and where is the role?",
        [("update_job_draft", {"min_experience_years": 5, "work_location": "REMOTE", "positions": 1})],
        "Create Rails Developer? yes/no",
        [("create_job", {})],
        "Done -- the job is queued.",
    )
    brains = Brains(large=large, small_offline_reason="FLASH_SMALL_LLM_BASE_URL is not set")
    first = _say(db, world.requester, f"I need a Rails developer for my new client {world.client_name}", brains)
    assert first["reply"].startswith("Heads-up: my parsing model is offline")
    assert first["active_workflow"] == "job_intake" and first["brain_status"] == "large_only"
    _say(db, world.requester, "5 years, remote, 1 position", brains)
    done = _say(db, world.requester, "yes", brains)
    payload = _job_payload(queued)
    _assert_rails_job(payload, world)
    assert done["job_id"] == payload["job_id"] and done["reply"] == "Done -- the job is queued."
    assert large.requests[1]["purpose"] == "intake" and "create_job" in large.requests[1]["tools"]
    events = [m.payload["tool"] for m in db.query(FlashMessage).filter_by(role="event").order_by(FlashMessage.id)
              if m.payload and m.payload.get("tool")]
    assert events[-4:] == ["search_clients", "update_job_draft", "update_job_draft", "create_job"]


def test_tool_events_read_as_one_line_and_keep_the_full_trace(db, world, queued):
    """The bubble shows what Flash did in words ("Created job Rails Developer for Acme"); internal
    steps (client lookup, draft updates, the unconfirmed attempt) are hidden; the payload keeps the
    whole call for audit."""
    ctx = _ctx(db, world.requester)
    execute(ctx, "search_clients", {"name": world.client_name})
    execute(ctx, "update_job_draft", {"title": "Rails Developer", "skills": ["Ruby on Rails"],
                                      "client_id": world.client.id, "min_experience_years": 5,
                                      "work_location": "REMOTE"})
    execute(ctx, "create_job", {})  # not confirmed yet
    state = ctx.state
    state["confirmed"] = "create_job"
    ctx.save_state(state)
    created = execute(ctx, "create_job", {})
    events = db.query(FlashMessage).filter_by(conversation_id=ctx.conversation.id, role="event").order_by(
        FlashMessage.id).all()
    assert [e.payload["hidden"] for e in events] == [True, True, True, False]
    assert events[1].body.startswith("update_job_draft: Draft:")  # the raw line stays for audit only
    assert events[1].payload["trace"] == events[1].body and events[1].payload["outcome"]["missing"] == []
    assert events[2].payload["ok"] is False and events[2].payload["outcome"]["error"].startswith("Not confirmed yet")
    assert events[3].body == f"Created job Rails Developer for {world.client_name}."
    assert events[3].payload["outcome"]["job_id"] == created["job_id"] == _job_payload(queued)["job_id"]
    assert events[3].payload["args"] == {} and events[3].payload["trace"].startswith("create_job: Job ")


def test_a_refusal_and_a_failure_are_shown_in_words(db, world, queued):
    clerk = user(db, role_without(db, "jobs.create"), "Clerk")
    ctx = _ctx(db, clerk)
    execute(ctx, "update_job_draft", {"title": "Rails Developer"})
    execute(ctx, "candidate_status", {"name": ""})
    execute(ctx, "no_such_tool", {})
    events = db.query(FlashMessage).filter_by(conversation_id=ctx.conversation.id, role="event").order_by(
        FlashMessage.id).all()
    assert [(e.body, e.payload["hidden"]) for e in events[:2]] == [
        ("You don't have permission to create jobs.", False), ("Say whose status you want.", False)]
    assert events[2].payload["hidden"] is True  # Flash's own protocol, never the person's business


def test_every_tool_declares_what_the_person_reads():
    flash_tools._load_registry()
    assert all(tool.summary is not None for tool in TOOLS.values())
    with pytest.raises(ValueError, match="has no summary"):
        flash_tools.register(flash_tools.FlashTool("look_around", "x", flash_tools.schema({}), None,
                                                   lambda c, a: {}, "x"))
    line = TOOLS["find_candidates"].summary({"query": "rails"}, {"text": "...", "results": [{}, {}]})
    assert line == "Searched candidates for rails: 2 found."


def test_claude_creating_without_a_yes_is_refused(db, world, queued):
    large = FakeLarge(
        [("update_job_draft", {"title": "Rails Developer", "skills": ["Ruby on Rails"], "client_id": world.client.id,
                               "min_experience_years": 5, "work_location": "REMOTE"})],
        [("create_job", {})],
        "Created.",
    )
    _say(db, world.requester, f"Rails developer for {world.client_name}, 5 years, remote", Brains(large=large))
    assert queued.enqueue == []


def test_job_by_chat_with_the_small_model_only(db, world, queued):
    small = FakeSmall(
        {"intent": "job_create", "query": "rails developer"},
        {"title": "Rails Developer", "client_name": world.client_name, "skills": ["Ruby on Rails"],
         "min_experience_years": None, "location": None, "work_location": None, "company_type": None,
         "client_id": None, "description": None, "positions": None},
        {"title": None, "client_name": None, "skills": None, "min_experience_years": 5, "location": None,
         "work_location": "REMOTE", "company_type": None, "client_id": None, "description": None, "positions": 1},
    )
    brains = Brains(small=small, large_offline_reason="ANTHROPIC_API_KEY is not set")
    _say(db, world.requester, f"new opening at {world.client_name} for rails work", brains)
    assert _say(db, world.requester, "five years, fully remote", brains)["reply"].startswith("Create Rails Developer")
    _say(db, world.requester, "yes", brains)
    _assert_rails_job(_job_payload(queued), world)


def test_claude_failing_mid_turn_falls_back_to_the_rules(db, world, queued):
    large = FakeLarge(BrainUnavailable("Claude timed out"))
    reply = _say(db, world.requester, f"I need a Rails developer for my new client {world.client_name}",
                 Brains(large=large))
    assert "Claude timed out" in reply["reply"] and reply["active_workflow"] == "job_intake"
    assert reply["reply"].endswith("Which skills are required? (comma-separated)")


def test_a_missing_client_is_created_after_a_yes(db, world, queued):
    name = f"Zeta{uid()}"
    reply = _say(db, world.requester, f"I need a Java developer for client {name}", OFFLINE)["reply"]
    assert reply.endswith(f"{name} isn't a client yet. Create it (attributed to your business unit)? yes/no")
    assert db.query(Client).filter_by(company_name=name).first() is None
    reply = _say(db, world.requester, "yes", OFFLINE)["reply"]
    client = db.query(Client).filter_by(company_name=name).one()
    assert client.tenant_id == 1 and client.business_unit_id == world.unit.id
    assert reply == f"Created client {name}. How many years of experience does the role need?"


def test_a_user_who_cannot_create_clients_is_asked_for_an_existing_one(db, world, queued):
    person = user(db, role_without(db, "clients.create"), "No Clients", business_unit_id=world.unit.id)
    name = f"Zeta{uid()}"
    reply = _say(db, person, f"I need a Java developer for client {name}", OFFLINE)["reply"]
    assert reply.endswith(f"{name} isn't a client yet, and you can't create clients. Which existing client is this for?")


def test_several_matching_clients_are_asked_about(db, world, queued):
    stem = f"Orbit{uid()}"
    for suffix in ("Labs", "Bank"):
        db.add(Client(tenant_id=1, company_name=f"{stem} {suffix}", business_unit_id=world.unit.id))
    db.flush()
    reply = _say(db, world.requester, f"I need a Java developer for client {stem}", OFFLINE)["reply"]
    assert reply.endswith(f"Which client do you mean: {stem} Bank or {stem} Labs?")
    reply = _say(db, world.requester, f"{stem} Labs", OFFLINE)["reply"]
    assert reply == "How many years of experience does the role need?"


def test_no_and_cancel(db, world, queued):
    _say(db, world.requester, f"I need a Java developer for client {world.client_name}, 6 years, remote", OFFLINE)
    assert _say(db, world.requester, "no", OFFLINE)["reply"].startswith("Okay, nothing was created.")
    out = _say(db, world.requester, "cancel", OFFLINE)
    assert out["active_workflow"] is None and queued.enqueue == []


def test_a_user_without_jobs_create_is_told_plainly(db, world, queued):
    person = user(db, role_without(db, "jobs.create"), "No Jobs")
    out = _say(db, person, f"I need a Rails developer for client {world.client_name}", OFFLINE)
    assert out["reply"].endswith("You don't have permission to create jobs.") and out["active_workflow"] is None


def test_decisions_intent(db, world):
    out = _say(db, world.requester, "any pending decisions for me?", OFFLINE)
    assert out["intent"] == "decisions" and out["reply"].endswith("Nothing is waiting for your decision.")


def test_the_api_returns_the_job_and_the_events(db, world, queued):
    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_brains] = lambda: OFFLINE
    try:
        api = TestClient(app)
        for text in (f"I need a Rails developer for my new client {world.client_name}", "Ruby on Rails",
                     "5 years, remote"):
            assert api.post("/api/v1/flash/", headers=headers(world.requester), json={"message": text}).status_code == 200
        body = api.post("/api/v1/flash/", headers=headers(world.requester), json={"message": "yes"}).json()
    finally:
        app.dependency_overrides.clear()
    assert body["job_id"] == _job_payload(queued)["job_id"]
    assert [m["role"] for m in body["messages"]] == ["user", "event", "flash"]
    assert body["messages"][1]["payload"]["tool"] == "create_job"


def test_flash_says_which_profile_details_a_candidate_is_missing(db, world):
    from app.models.candidate import Candidate

    last = f"Sequeira{uid()}"
    db.add(Candidate(tenant_id=1, candidateID=f"CAN-{uid()}", candidateEmail=f"{uid()}@example.com",
                     candidatePassword="h", candidateFirstName="Joss", candidateLastName=last,
                     candidateMobile="+1 312 555 0100", candidateGender="Male",
                     candidateCurrentLocation="Chicago, Illinois, United States"))
    db.flush()
    outcome = execute(_ctx(db, world.recruiter), "candidate_profile", {"name": f"Joss {last}"})
    assert outcome["text"].startswith(f"Joss {last}: ") and "Date of Birth" in outcome["missing"]
    assert "Expected Salary" in outcome["missing"] and "Your latest resume" in outcome["missing"]
    assert "Gender" not in outcome["missing"] and "Thunder has not emailed them yet." in outcome["text"]
