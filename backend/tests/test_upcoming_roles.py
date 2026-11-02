"""Client meetings, upcoming roles and personal outreach (CEO 2026-11-02: "we met with this client and
they asked to start an inception for billingcenter which will require us a BC developer, BC Business
Analyst ... Recruitment should start working on it as it takes 60-90 days to hire ... open job on its
own, search for candidate in DB ... send individual emails to each of the candidates ... Never reveal
the client name" -- fully automatic).

A meeting update keeps what was discussed and agreed on the client's History; its next steps are
tasks. An upcoming role on an opportunity opens a potential job at once and starts recruiting. When
Flash ranks the pool, each new match gets an email written for them alone, sent through Thunder with
every Thunder rule, and the client is never named."""
import json
import random
import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.client_update import RoleOutreach, UpcomingRole
from app.models.opportunity import Opportunity
from app.models.task import Task
from app.models.thunder_email import ThunderCadenceState, ThunderEmailMessage
from app.models.user import Jobs
from app.services.flash_brain.llm import BrainUnavailable
from app.services.message_handlers.thunder_send_email_handler import ThunderSendEmailHandler
from app.services.role_outreach_service import compose_role_email, queue_role_outreach
from app.services.thunder_mail import cadence_service as cadence
from app.services.upcoming_role_service import UpcomingRoleError, create_upcoming_role
from tests.scope_fixtures import ApiClient, two_bu_world

ENQUEUE = "app.services.message_queue_service.MessageQueueService.enqueue"
START = "app.services.recruiting_service.start_recruiting"


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
    world.client_a.company_name = f"Moter Insurance {uuid.uuid4().hex[:4]}"
    world.opportunity = Opportunity(tenant_id=1, client_id=world.client_a.id, stage="PROPOSAL",
                                    revenue_value_usd_cents=20_000_000, probability_pct=50)
    db.add(world.opportunity)
    db.commit()
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


ROLE = {"title": "BillingCenter Developer", "description": "Configure and extend Guidewire BillingCenter.",
        "skills": ["Guidewire BillingCenter", "Gosu"], "client_description": "a mid-size P&C carrier",
        "positions": 2, "work_location": "REMOTE", "min_experience_years": 5,
        "target_start": str(date.today() + timedelta(days=75)), "likelihood_pct": 70}


class FakeBrain:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, []

    def extract_json(self, *, purpose, system, user, schema, tenant_id):
        self.calls.append(json.loads(user))
        if self.error:
            raise self.error
        return self.reply


class FakeMailbox:
    def __init__(self):
        self.drafts, self.sent = {}, []

    def create_draft(self, to, subject, html, ref):
        mid = f"g-{uuid.uuid4().hex[:8]}"
        self.drafts[mid] = {"to": to, "subject": subject, "html": html}
        return mid, f"conv-{mid}", f"<{mid}@blitzenx.com>"

    def is_draft(self, mid):
        return mid not in self.sent

    def send(self, mid):
        self.sent.append(mid)


def _candidate(db, **extra):
    candidate = Candidate(
        tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidateEmail=f"bc{uuid.uuid4().hex[:6]}@dev.io",
        candidatePassword="h", candidateFirstName="Priya", candidateLastName="Rao", thunder_enabled=True,
        candidateSkills="Guidewire BillingCenter, Gosu, Java", candidateExperience="9", timezone="UTC", **extra)
    db.add(candidate)
    db.commit()
    return candidate


def _role(db, w, **extra):
    job = create_upcoming_role(db, w.opportunity, actor=w.org_user, **{**ROLE, **extra,
                               "target_start": date.today() + timedelta(days=75)})
    db.commit()
    return job, db.query(UpcomingRole).filter_by(job_id=job.jobID).one()


def test_meeting_update_creates_owned_next_steps_and_shows_on_history(db, w, api):
    body = {"meeting_date": str(date.today()), "attendees": "CIO, Head of Billing",
            "summary": "They want to start a BillingCenter inception.", "decisions": "Staff a BC developer and BA",
            "opportunity_id": w.opportunity.id,
            "next_steps": [{"title": "Send the inception proposal", "owner_user_id": w.partner_a.UserID,
                            "due_date": str(date.today() + timedelta(days=3))}]}
    response = api.post(w.org_user, f"/api/v1/clients/{w.client_a.id}/updates", json=body)
    assert response.status_code == 201, response.text
    task = db.query(Task).filter(Task.id == response.json()["task_ids"][0]).one()
    assert task.assigned_to_user_id == w.partner_a.UserID
    assert task.title.endswith("Send the inception proposal")

    history = api.get(w.org_user, f"/api/v1/clients/{w.client_a.id}/history").json()["entries"]
    meeting = next(e for e in history if e["kind"] == "UPDATE")
    assert "Agreed: Staff a BC developer and BA" in meeting["lines"]
    assert any(line.startswith("Next step:") and "Partner A" in line for line in meeting["lines"])


def test_meeting_update_rejects_a_next_step_without_owner(w, api):
    body = {"meeting_date": str(date.today()), "summary": "Call", "next_steps": [{"title": "x", "owner_user_id": ""}]}
    assert api.post(w.org_user, f"/api/v1/clients/{w.client_a.id}/updates", json=body).status_code == 400


def test_upcoming_role_opens_a_potential_job_and_starts_recruiting(db, w, api):
    with patch(START) as start:
        response = api.post(w.org_user, f"/api/v1/opportunities/{w.opportunity.id}/upcoming-roles", json=ROLE)
    assert response.status_code == 201, response.text
    role = response.json()["roles"][0]
    job = db.query(Jobs).filter(Jobs.jobID == role["job_id"]).one()
    assert (job.confirmation_status, job.demand_status, job.source_type) == ("POTENTIAL", "OPEN", "OPPORTUNITY")
    assert (job.opportunity_id, job.client_id, job.noOfPositions) == (w.opportunity.id, w.client_a.id, 2)
    assert role["client_description"] == "a mid-size P&C carrier"
    start.assert_called_once()


def test_upcoming_role_may_not_name_the_client(db, w):
    with pytest.raises(UpcomingRoleError):
        create_upcoming_role(db, w.opportunity, actor=w.org_user,
                             **{**ROLE, "client_description": f"{w.client_a.company_name}'s billing team"})


def test_email_is_written_for_the_person_from_our_history(db, w):
    job, role = _role(db, w)
    candidate = _candidate(db)
    db.add(ThunderEmailMessage(id=str(uuid.uuid4()), tenant_id=1, candidate_id=candidate.candidateID,
                               direction="IN", status="PROCESSED", cadence_seq=1, mailbox="m",
                               subject="Re: next move", body_text="I want to lead BillingCenter work next."))
    db.commit()
    brain = FakeBrain({"subject": "Priya, a BillingCenter role", "why_fit": "9 years BC",
                       "paragraphs": ["You told us you want to lead BillingCenter work.", "This team needs that."]})
    email = compose_role_email(db, candidate, job, role, brain=brain)
    assert email["composed_by"] == "claude"
    assert "lead BillingCenter work" in email["body_html"] and "remove" in email["body_html"]
    facts = brain.calls[0]
    assert facts["past_emails"][0]["text"].startswith("I want to lead")
    assert facts["role"]["client_description"] == "a mid-size P&C carrier"
    assert w.client_a.company_name not in json.dumps(facts)


def test_model_text_naming_the_client_is_replaced_by_the_rules(db, w):
    job, role = _role(db, w)
    candidate = _candidate(db)
    brain = FakeBrain({"subject": "Role", "why_fit": "x",
                       "paragraphs": [f"{w.client_a.company_name} needs you."]})
    email = compose_role_email(db, candidate, job, role, brain=brain)
    assert email["composed_by"] == "rules"
    assert w.client_a.company_name not in email["body_html"] + email["subject"]
    assert "a mid-size P&amp;C carrier" in email["body_html"]  # escaped in the email's HTML


def test_without_a_model_the_rules_write_it(db, w):
    job, role = _role(db, w)
    candidate = _candidate(db)
    email = compose_role_email(db, candidate, job, role, brain=FakeBrain(error=BrainUnavailable("no key")))
    assert email["composed_by"] == "rules"
    assert "Guidewire BillingCenter" in email["body_html"]


def test_matches_are_emailed_once_through_thunder_and_the_plan_is_untouched(db, w):
    job, _ = _role(db, w)
    candidate = _candidate(db)
    state = cadence.start_cadence(db, candidate)
    db.commit()
    planned = (state.next_step, state.next_action_at)
    brain = FakeBrain({"subject": "Priya, a BillingCenter role", "why_fit": "fit", "paragraphs": ["Hello again."]})
    with patch(ENQUEUE, return_value={"message_id": "x", "task_id": "x"}) as enqueue:
        assert queue_role_outreach(db, job, [{"candidate_id": candidate.candidateID, "recency_score": 88}],
                                   brain=brain) == 1
        assert queue_role_outreach(db, job, [{"candidate_id": candidate.candidateID}], brain=brain) == 0
    outreach = db.query(RoleOutreach).filter_by(job_id=job.jobID).one()
    step = enqueue.call_args.kwargs.get("data", {}).get("step") or f"ROLE-{outreach.id}"
    assert step == f"ROLE-{outreach.id}"

    mailbox = FakeMailbox()
    message = SimpleNamespace(id="m1", payload={"candidate_id": candidate.candidateID, "cadence_seq": 1,
                                                "step": step, "tenant_id": 1})
    with patch.object(cadence, "next_send_slot", return_value=None), patch(ENQUEUE):
        result = ThunderSendEmailHandler.process(message, db, mailbox=mailbox, rng=random.Random(1))
    assert result["status"] == "sent"
    db.refresh(outreach)
    db.refresh(state)
    assert outreach.status == "SENT" and outreach.thunder_message_id
    assert (state.next_step, state.next_action_at) == planned
    sent = next(iter(mailbox.drafts.values()))
    assert sent["subject"] == "Priya, a BillingCenter role" and "Hello again." in sent["html"]


def test_a_stopped_or_unreachable_candidate_is_skipped(db, w):
    job, _ = _role(db, w)
    stopped = _candidate(db)
    db.add(ThunderCadenceState(candidate_id=stopped.candidateID, tenant_id=1, cadence_seq=1, stage="STOPPED",
                               stop_reason="candidate unsubscribe", touches_sent=1))
    unreachable = _candidate(db, )
    unreachable.thunder_enabled = False
    db.commit()
    with patch(ENQUEUE) as enqueue:
        queued = queue_role_outreach(db, job, [{"candidate_id": stopped.candidateID},
                                               {"candidate_id": unreachable.candidateID}], brain=FakeBrain())
    assert queued == 0 and enqueue.call_count == 0
    notes = {o.candidate_id: o.note for o in db.query(RoleOutreach).filter_by(job_id=job.jobID)}
    assert "unsubscribe" in notes[stopped.candidateID]
    assert "not contactable" in notes[unreachable.candidateID]


def test_a_job_without_an_upcoming_role_gets_no_personal_email(db, w):
    job, role = _role(db, w)
    role.auto_outreach = False
    db.commit()
    candidate = _candidate(db)
    with patch(ENQUEUE) as enqueue:
        assert queue_role_outreach(db, job, [{"candidate_id": candidate.candidateID}], brain=FakeBrain()) == 0
    assert enqueue.call_count == 0
