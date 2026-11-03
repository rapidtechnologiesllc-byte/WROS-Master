"""Thunder checks what we already know before a cold email (CEO 2026-11-03, about an executive who had
already had a call with the CEO and still got the generic first email: "there should be validation
before sending out -> some if else conditions where thunder checks if this candidate has any previous
data")."""
import random
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.candidate_history import CandidateHistory
from app.models.internal_note import InternalNote
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.thunder_email import ThunderEmailMessage
from app.models.user import Interview, InterviewPanel, Jobs
from app.services.delivery_errors import DeliveryDeferred
from app.services.message_handlers.thunder_send_email_handler import ThunderSendEmailHandler
from app.services.thunder_mail import cadence_service as cadence
from app.services.thunder_mail import preflight
from app.services.thunder_mail.seed_variants import seed_thunder_variants
from tests.hiring_fixtures import finance_approver

ENQUEUE = "app.services.message_queue_service.MessageQueueService.enqueue"


def uid():
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
def owner(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    seed_thunder_variants(db)
    return finance_approver(db)


def _candidate(db, owner, *, job=None, added_minutes_ago=600):
    person = Candidate(tenant_id=1, candidateID=f"CAN-{uid()}", candidateEmail=f"marco{uid()}@example.com",
                       candidatePassword="h", candidateFirstName="Marco", candidateLastName="T",
                       candidateJobTitle="Executive Director", thunder_enabled=True, timezone="UTC",
                       created_by_user_id=owner.UserID, job_id=job.jobID if job else None,
                       candidateCreatedAt=datetime.utcnow() - timedelta(minutes=added_minutes_ago))
    db.add(person)
    db.flush()
    state = cadence.start_cadence(db, person)
    db.commit()
    return person, state


def _job(db):
    job = Jobs(tenant_id=1, jobTitle="Guidewire BillingCenter Architect", jobDescription="d",
               jobSkills="Guidewire", jobExperience="10", jobLocation="Remote")
    db.add(job)
    db.commit()
    return job


class Mailbox:
    mailbox = "helpdesk_hrms@blitzenx.com"

    def __init__(self):
        self.drafts, self.sent = {}, []

    def create_draft(self, to, subject, html, ref):
        mid = f"g-{uid()}"
        self.drafts[mid] = {"subject": subject, "html": html}
        return mid, f"conv-{mid}", f"<{mid}@x>"

    def is_draft(self, mid):
        return mid not in self.sent

    def send(self, mid):
        self.sent.append(mid)


def _send(db, person, step="1"):
    message = SimpleNamespace(id=f"m-{uid()}", payload={"candidate_id": person.candidateID, "cadence_seq": 1,
                                                       "step": step, "tenant_id": 1})
    mailbox = Mailbox()
    with patch.object(cadence, "next_send_slot", return_value=None), \
         patch(ENQUEUE, return_value={"message_id": "x", "task_id": "x"}):
        result = ThunderSendEmailHandler.process(message, db, mailbox=mailbox, rng=random.Random(1))
    return result, mailbox


def _checks(db, person):
    return [n for (n,) in db.query(CandidateHistory.note).filter_by(candidateID=person.candidateID,
                                                                    event_type="Thunder Check")]


def test_someone_we_already_met_gets_no_cold_email(db, owner):
    person, state = _candidate(db, owner, job=_job(db))
    panel = InterviewPanel(candidate_id=person.candidateID, round_name="Screening")
    db.add(panel)
    db.flush()
    db.add(Interview(panel_id=panel.id, candidate_id=person.candidateID, status="Completed",
                     start_time=datetime.utcnow() - timedelta(days=3), end_time=datetime.utcnow() - timedelta(days=3)))
    db.commit()
    result, mailbox = _send(db, person)
    assert result["status"] == "skipped_in_conversation" and not mailbox.sent
    db.refresh(state)
    assert state.stage == "HANDOFF" and not (state.next_step or "").startswith(("1", "2", "3", "4"))
    assert any("WARM" in n and "interview" in n for n in _checks(db, person))


@pytest.mark.parametrize("evidence", ["note", "reply"])
def test_notes_or_a_reply_also_count_as_a_conversation(db, owner, evidence):
    person, _ = _candidate(db, owner, job=_job(db))
    if evidence == "note":
        db.add(InternalNote(candidate_id=person.candidateID, content="Spoke on the phone", created_by_id=owner.UserID))
    else:
        db.add(ThunderEmailMessage(id=str(uuid.uuid4()), tenant_id=1, candidate_id=person.candidateID, direction="IN",
                                   status="PROCESSED", cadence_seq=1, mailbox="helpdesk_hrms@blitzenx.com",
                                   graph_message_id=f"in-{uid()}", received_at=datetime.utcnow()))
    db.commit()
    assert preflight.check(db, person, "1", None).action == "WARM"


def test_a_candidate_just_added_by_a_person_is_given_time_first(db, owner):
    person, _ = _candidate(db, owner, job=_job(db), added_minutes_ago=1)
    with pytest.raises(DeliveryDeferred, match="added by one of our people"):
        _send(db, person)


def test_no_first_email_without_a_role_and_the_adder_is_asked_once(db, owner):
    person, _ = _candidate(db, owner)
    for _ in range(2):
        with pytest.raises(DeliveryDeferred, match="waiting for the role"):
            _send(db, person)
    asks = db.query(Task).filter(Task.category == "THUNDER_BRIEF", Task.candidate_id == person.candidateID).all()
    assert len(asks) == 1 and asks[0].assigned_to_user_id == owner.UserID


def test_with_a_role_and_no_history_the_first_email_names_the_role(db, owner):
    person, _ = _candidate(db, owner, job=_job(db))
    result, mailbox = _send(db, person)
    assert result["status"] == "sent"
    draft = next(iter(mailbox.drafts.values()))
    assert "Guidewire BillingCenter Architect" in draft["subject"] + draft["html"]
    assert "Executive Director" in draft["html"]  # the opening line uses who they are
    assert "people like you tend to do their best work" not in draft["html"]  # never the generic one
    assert any("SEND" in n for n in _checks(db, person))


def test_the_second_email_waits_at_least_a_week_after_the_first(db, owner):
    """CEO 2026-11-03: "after the cold email we give them atleast 1 week to 10 days before we send second one"."""
    person, state = _candidate(db, owner, job=_job(db))
    before = datetime.utcnow()
    assert _send(db, person)[0]["status"] == "sent"
    db.refresh(state)
    assert state.next_step == "2" and state.next_action_at - before >= timedelta(days=7)
    assert state.next_action_at - before <= timedelta(days=10, minutes=1)
    with patch("app.services.thunder_mail.cadence_service.settings.THUNDER_FOLLOWUP_DAYS", "2,14,21"):
        assert cadence.silence_delay_days()["1"] == 7  # never sooner than a week, whatever the setting
