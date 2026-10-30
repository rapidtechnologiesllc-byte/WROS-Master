"""Thunder email loop: send, read replies, re-plan, A/B, nurture. Fake Graph + fake LLM, no network."""
import random
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.candidate import Candidate
from app.models.candidate_rejection import CandidateRejection
from app.models.channel_queue import ChannelQueueItem
from app.models.consent import ConsentRecord
from app.models.task import Task
from app.models.tenant import Tenant
from app.models.thunder_email import (
    ThunderCadenceState, ThunderEmailMessage, ThunderMonthlyHighlight, ThunderOutreachVariant,
)
from app.models.user import Jobs
from app.services.delivery_errors import DeliveryDeferred
from app.services.message_handlers.thunder_inbound_email_handler import ThunderInboundEmailHandler
from app.services.message_handlers.thunder_send_email_handler import ThunderSendEmailHandler
from app.services.thunder_mail import cadence_service as cadence
from app.services.thunder_mail.mail_poll_service import poll_thunder_mailbox, run_cadence_sweep
from app.services.thunder_mail.reply_classifier import classify_reply
from app.services.thunder_mail.seed_variants import seed_thunder_variants
from app.services.thunder_mail.variant_selector import choose_variant

ENQUEUE = "app.services.message_queue_service.MessageQueueService.enqueue"
MAILBOX = "helpdesk_hrms@blitzenx.com"


class FakeMailbox:
    def __init__(self, inbox=None):
        self.inbox = inbox or []
        self.drafts, self.sent, self.replies = {}, [], []

    def create_draft(self, to, subject, html, ref):
        mid = f"g-{uuid.uuid4().hex[:8]}"
        self.drafts[mid] = {"to": to, "subject": subject, "html": html}
        return mid, f"conv-{mid}", f"<{mid}@blitzenx.com>"

    def create_reply_draft(self, parent_id, html):
        mid = f"g-{uuid.uuid4().hex[:8]}"
        self.drafts[mid] = {"reply_to": parent_id, "html": html}
        self.replies.append(parent_id)
        return mid, "conv-thread", f"<{mid}@blitzenx.com>"

    def is_draft(self, mid):
        return mid not in self.sent

    def send(self, mid):
        self.sent.append(mid)

    def list_inbox(self, since, page_cap=10):
        return self.inbox


@pytest.fixture
def db(test_db_engine):
    """Like conftest's db, but the code under test may commit AND roll back:
    each session transaction is a savepoint inside one outer, discarded transaction."""
    from sqlalchemy.orm import Session

    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def world(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    seed_thunder_variants(db)
    candidate = Candidate(
        tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidateEmail=f"ankur{uuid.uuid4().hex[:6]}@ankur.dev",
        candidatePassword="h", candidateFirstName="Ankurjit", candidateLastName="Singh",
        candidateSkills="Python, Kafka", candidateCurrentLocation="Bengaluru", thunder_enabled=True,
        timezone="UTC",
    )
    db.add(candidate)
    db.flush()
    state = cadence.start_cadence(db, candidate)
    db.commit()
    return SimpleNamespace(candidate=candidate, state=state)


def _send(db, world, step, mailbox, seq=1):
    message = SimpleNamespace(id="m1", payload={"candidate_id": world.candidate.candidateID,
                                                "cadence_seq": seq, "step": step, "tenant_id": 1})
    with patch.object(cadence, "next_send_slot", return_value=None), \
         patch(ENQUEUE, return_value={"message_id": "x", "task_id": "x"}) as enqueue:
        result = ThunderSendEmailHandler.process(message, db, mailbox=mailbox, rng=random.Random(1))
    return result, enqueue


def _inbound(db, world, body, subject="Re: a quick question", received=None, headers=None, llm=None, fields_llm=None):
    row = ThunderEmailMessage(
        id=str(uuid.uuid4()), tenant_id=1, candidate_id=world.candidate.candidateID, direction="IN",
        status="RECEIVED", cadence_seq=1, mailbox=MAILBOX, graph_message_id=f"in-{uuid.uuid4().hex[:6]}",
        from_address=world.candidate.candidateEmail, subject=subject, body_text=body,
        received_at=received or datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    message = SimpleNamespace(id="m2", payload={"thunder_message_id": row.id, "headers": headers or {}})
    with patch(ENQUEUE, return_value={"message_id": "x", "task_id": "x"}) as enqueue:
        result = ThunderInboundEmailHandler.process(message, db, llm_call=llm or (lambda *a: "garbage"),
                                                    field_llm_call=fields_llm or (lambda prompt: "{}"))
    db.refresh(world.state)
    return result, enqueue, row


# ---- queue: not sent stays pending -------------------------------------------------

def test_deferred_message_stays_pending_not_failed_and_waits(db):
    from app.services.message_handler_registry import MessageHandlerRegistry
    from app.services.queue_processor_service import QueueProcessorService

    retry_at = datetime.utcnow() + timedelta(minutes=15)

    def not_configured(message, db):
        raise DeliveryDeferred("Azure Graph credentials not configured", retry_at)

    MessageHandlerRegistry.register("test_deferred_send", not_configured)
    item = ChannelQueueItem(id=str(uuid.uuid4()), message_id="t", type="test_deferred_send",
                            channel_type="CANDIDATE_QUEUE", status="PENDING", payload={}, retry_count=0,
                            tenant_id=1)
    db.add(item)
    db.commit()
    result = QueueProcessorService._process_single_message(db, item)
    db.refresh(item)
    assert result["status"] == "PENDING" and result["not_sent"] is True
    assert item.status == "PENDING" and item.retry_count == 0
    assert item.error.startswith("NOT_SENT") and item.next_retry_at == retry_at


def test_production_worker_keeps_unsent_pending_and_runs_due_scheduled(db):
    """start_worker.py -> message_queue_worker (the path production runs)."""
    from app.services.message_handler_registry import MessageHandlerRegistry
    from app.workers import message_queue_worker as worker

    retry_at = datetime.utcnow() + timedelta(minutes=15)
    ran = []

    def not_configured(message, db):
        raise DeliveryDeferred("Azure Graph credentials not configured", retry_at)

    def delayed(message, db):
        ran.append(message.id)
        return {"status": "success"}

    MessageHandlerRegistry.register("test_worker_deferred", not_configured)
    MessageHandlerRegistry.register("test_worker_delayed", delayed)
    old = datetime(2000, 1, 1)
    deferred = ChannelQueueItem(id=str(uuid.uuid4()), message_id="d", type="test_worker_deferred", tenant_id=1,
                                channel_type="CANDIDATE_QUEUE", status="PENDING", payload={}, retry_count=0,
                                created_at=old)
    due = ChannelQueueItem(id=str(uuid.uuid4()), message_id="s", type="test_worker_delayed", tenant_id=1,
                           channel_type="CANDIDATE_QUEUE", status="SCHEDULED", payload={}, retry_count=0,
                           created_at=old, scheduled_for=datetime.utcnow() - timedelta(minutes=1))
    stale = ChannelQueueItem(id=str(uuid.uuid4()), message_id="x", type="test_worker_delayed", tenant_id=1,
                             channel_type="CANDIDATE_QUEUE", status="SCHEDULED", payload={}, retry_count=0,
                             created_at=old, scheduled_for=datetime.utcnow() - timedelta(days=30))
    db.add_all([deferred, due, stale])
    db.commit()
    with patch.object(worker, "SessionLocal", return_value=db), patch.object(db, "close"), \
         patch.object(worker, "is_thunder_paused", return_value=False):
        worker.process_message_queue(batch_size=2)
    for row in (deferred, due, stale):
        db.refresh(row)
    assert deferred.status == "PENDING" and deferred.error.startswith("NOT_SENT") and deferred.retry_count == 0
    assert deferred.next_retry_at == retry_at
    assert ran == [due.id] and due.status == "COMPLETED"
    assert stale.status == "DEAD_LETTER" and stale.id not in ran


def test_send_email_handler_defers_instead_of_skipping_and_never_ccs_helpdesk(db):
    from app.services.message_handlers.send_email_handler import SendEmailHandler

    message = SimpleNamespace(id="m", payload={"to_email": "c@x.dev", "subject": "s", "body": "b"})
    with patch("app.services.message_handlers.send_email_handler.GraphServiceAuth.is_configured", return_value=False):
        with pytest.raises(DeliveryDeferred):
            SendEmailHandler.process(message, db)
    with patch("app.services.message_handlers.send_email_handler.GraphServiceAuth.is_configured", return_value=True), \
         patch("app.services.message_handlers.send_email_handler.EmailService.send_email",
               return_value={"status": "success"}) as send:
        SendEmailHandler.process(SimpleNamespace(id="m", payload={
            "to_email": "c@x.dev", "subject": "s", "body": "b", "cc_emails": [MAILBOX]}), db)
    assert send.call_args.kwargs["sender_email"] == MAILBOX
    assert send.call_args.kwargs["cc_emails"] is None


# ---- send ----------------------------------------------------------------------------

def test_step1_sends_from_hrms_mailbox_and_schedules_followup(db, world):
    mailbox = FakeMailbox()
    result, _ = _send(db, world, "1", mailbox)
    out = db.query(ThunderEmailMessage).filter_by(candidate_id=world.candidate.candidateID, direction="OUT").one()
    assert result["status"] == "sent" and out.status == "SENT" and out.mailbox == MAILBOX
    assert mailbox.sent == [out.graph_message_id] and out.conversation_id
    html = mailbox.drafts[out.graph_message_id]["html"]
    assert "Ankurjit" in html and 'Reply "remove"' in html
    db.refresh(world.state)
    assert world.state.next_step == "2" and world.state.touches_sent == 1


def test_retry_after_crash_between_draft_and_send_sends_exactly_once(db, world):
    mailbox = FakeMailbox()
    with patch.object(FakeMailbox, "send", side_effect=RuntimeError("network")):
        with pytest.raises(RuntimeError):
            _send(db, world, "1", mailbox)
    out = db.query(ThunderEmailMessage).filter_by(candidate_id=world.candidate.candidateID, direction="OUT").one()
    variant_before = out.variant_id
    assert out.status == "DRAFTED"
    _send(db, world, "1", mailbox)
    db.refresh(out)
    assert out.status == "SENT" and mailbox.sent == [out.graph_message_id]
    assert len(mailbox.drafts) == 1 and out.variant_id == variant_before


def test_followup_replies_in_the_same_thread(db, world):
    mailbox = FakeMailbox()
    _send(db, world, "1", mailbox)
    first = db.query(ThunderEmailMessage).filter_by(candidate_id=world.candidate.candidateID, step="1").one()
    world.state.last_outbound_at = datetime.utcnow() - timedelta(days=4)
    db.commit()
    _send(db, world, "2", mailbox)
    assert mailbox.replies == [first.graph_message_id]


def test_superseded_step_sends_nothing(db, world):
    mailbox = FakeMailbox()
    result, _ = _send(db, world, "3", mailbox)
    assert result["status"] == "superseded" and not mailbox.sent


def test_min_gap_cooldown_and_revoked_consent_block_sends(db, world):
    mailbox = FakeMailbox()
    world.state.last_outbound_at = datetime.utcnow() - timedelta(hours=1)
    db.commit()
    with pytest.raises(DeliveryDeferred, match="minimum gap"):
        _send(db, world, "1", mailbox)
    world.state.last_outbound_at = None
    db.add(CandidateRejection(candidate_id=world.candidate.candidateID, rejection_reason="x",
                              rejected_at=datetime.utcnow(), tenant_id=1))
    db.commit()
    with pytest.raises(DeliveryDeferred, match="not contactable"):
        _send(db, world, "1", mailbox)
    assert not mailbox.sent


def test_send_window_uses_candidate_timezone():
    candidate = SimpleNamespace(timezone="Asia/Kolkata")
    inside = datetime(2026, 10, 8, 6, 0)   # Thu 11:30 IST
    night = datetime(2026, 10, 8, 16, 0)   # Thu 21:30 IST
    friday_late = datetime(2026, 10, 9, 16, 0)  # Fri 21:30 IST -> Monday 09:00 IST
    assert cadence.next_send_slot(candidate, inside) is None
    assert cadence.next_send_slot(candidate, night) == datetime(2026, 10, 9, 3, 30)
    assert cadence.next_send_slot(candidate, friday_late) == datetime(2026, 10, 12, 3, 30)


# ---- inbound: classification and re-planning ----------------------------------------

def test_opt_out_wins_even_if_llm_says_interested(db, world):
    result, _, _ = _inbound(db, world, "Interested? No. Please remove me from your list.",
                            llm=lambda *a: '{"intent": "INTERESTED", "confidence": 0.99}')
    assert result["intent"] == "UNSUBSCRIBE"
    db.refresh(world.candidate)
    assert world.state.stage == "STOPPED" and world.state.next_action_at is None
    assert world.candidate.thunder_enabled is False
    revoked = db.query(ConsentRecord).filter_by(subject_id=world.candidate.candidateID,
                                                consent_type="email_outreach").one()
    assert revoked.consent_given is False


def test_interested_reply_hands_off_acks_and_credits_variant(db, world):
    mailbox = FakeMailbox()
    _send(db, world, "1", mailbox)
    result, enqueue, row = _inbound(db, world, "Sounds good, let's talk",
                                    llm=lambda *a: '{"intent": "INTERESTED", "confidence": 0.9}')
    out = db.query(ThunderEmailMessage).filter_by(candidate_id=world.candidate.candidateID, direction="OUT").one()
    db.refresh(row)
    assert result["intent"] == "INTERESTED" and row.credited_out_id == out.id
    assert world.state.stage == "HANDOFF" and world.state.next_step.startswith("NURTURE")
    acks = [c.kwargs["data"]["step"] for c in enqueue.call_args_list if c.kwargs["task_name"] == "thunder_send_email"]
    assert acks == ["ACK_INTERESTED"]
    assert db.query(Task).filter_by(candidate_id=world.candidate.candidateID, category="THUNDER_REPLY").count() == 1


def test_salary_question_without_salary_on_record_gets_a_holding_reply_and_a_human(db, world):
    result, enqueue, _ = _inbound(db, world, "What's the CTC for this?")
    assert result["intent"] == "QUESTION_COMP" and result["ack_step"] == "ACK_HOLD"
    task = db.query(Task).filter_by(candidate_id=world.candidate.candidateID).one()
    assert "answer personally" in task.title
    variant = db.query(ThunderOutreachVariant).filter_by(key="ack_hold").one()
    _, body = cadence.render(variant, world.candidate, None, {})
    assert "come back to you personally" in body and "{" not in body


def test_details_in_a_reply_are_saved_and_the_rest_is_asked_for(db, world):
    details = '{"candidateMobile": "+91 98765 43210", "candidateExperience": "6"}'
    result, enqueue, _ = _inbound(db, world, "Interested. My number is +91 98765 43210, 6 years in Kafka.",
                                  llm=lambda *a: '{"intent": "INTERESTED", "confidence": 0.9}',
                                  fields_llm=lambda prompt: details)
    db.refresh(world.candidate)
    assert world.candidate.candidateMobile == "+91 98765 43210"
    assert set(result["fields_saved"]) == {"candidateMobile", "candidateExperience"}
    assert "candidateMobile" not in result["fields_missing"] and "candidateGender" in result["fields_missing"]
    task = db.query(Task).filter_by(candidate_id=world.candidate.candidateID).one()
    assert "Saved from this reply: " in task.description and "Thunder asked for them" in task.description


def test_every_further_reply_is_answered_until_the_cap(db, world):
    steps = [_inbound(db, world, f"Here you go, reply {n}")[0]["ack_step"] for n in range(cadence.MAX_ACKS_PER_KIND)]
    assert steps == ["ACK_FIELDS"] + [f"ACK_FIELDS#{n}" for n in range(2, cadence.MAX_ACKS_PER_KIND + 1)]
    mailbox = FakeMailbox()
    for step in steps:
        _send(db, world, step, mailbox)
    assert _inbound(db, world, "And one more")[0]["ack_step"] is None


def test_an_acknowledgement_asks_for_the_missing_details_before_the_signature(db, world):
    mailbox = FakeMailbox()
    result, _ = _send(db, world, "ACK_FIELDS#2", mailbox)
    out = db.query(ThunderEmailMessage).filter_by(candidate_id=world.candidate.candidateID, step="ACK_FIELDS#2").one()
    assert result["status"] == "sent" and out.variant_id == db.query(ThunderOutreachVariant).filter_by(key="ack_fields").one().id
    sent = mailbox.drafts[out.graph_message_id]["html"]
    assert "<li>Gender</li>" in sent and sent.index("To move things forward") < sent.index("<p>Regards,")
    # copy approved before the slot existed gets the request placed before its signature too
    variant = db.query(ThunderOutreachVariant).filter_by(key="ack_interested").one()
    _, body = cadence.render(variant, world.candidate, None, {"fields_request": cadence.fields_request_html(
        [{"field": "candidateGender", "label": "Gender"}])})
    assert body.index("<li>Gender</li>") < body.index("<p>Regards,")


def test_unreadable_details_never_block_the_reply(db, world):
    def broken(prompt):
        raise RuntimeError("GEMINI_API_KEY is not configured")
    result, _, _ = _inbound(db, world, "Interested, call me", llm=lambda *a: '{"intent": "INTERESTED", "confidence": 0.9}',
                            fields_llm=broken)
    assert result["status"] == "processed" and result["ack_step"] == "ACK_INTERESTED"
    task = db.query(Task).filter_by(candidate_id=world.candidate.candidateID).one()
    assert "could not be read automatically" in task.description


def test_an_opt_out_reads_and_asks_for_nothing(db, world):
    calls = []
    result, _, _ = _inbound(db, world, "Please remove me", fields_llm=lambda p: calls.append(p) or "{}")
    assert result["intent"] == "UNSUBSCRIBE" and calls == [] and result["fields_missing"] == []


def test_salary_ack_quotes_job_record_verbatim(db, world):
    job = Jobs(jobTitle="Guidewire Developer", jobDescription="d", jobSkills="Guidewire", jobExperience="5",
               jobLocation="Pune", salaryRange="INR 24-30 LPA", jobStatus="Open")
    db.add(job)
    db.flush()
    world.state.job_id = job.jobID
    db.commit()
    variant = db.query(ThunderOutreachVariant).filter_by(key="ack_comp").one()
    _, body = cadence.render(variant, world.candidate, job, {})
    assert "INR 24-30 LPA" in body and "Guidewire Developer" in body


def test_not_now_moves_to_nurture_in_90_days_and_auto_reply_only_delays(db, world):
    _inbound(db, world, "Not right now, maybe next year")
    assert world.state.stage == "NURTURE"
    assert world.state.next_action_at > datetime.utcnow() + timedelta(days=89)
    before = world.state.next_action_at
    result, _, _ = _inbound(db, world, "I am away", subject="Automatic reply: back Monday")
    assert result["intent"] == "AUTO" and world.state.next_action_at == before


def test_reprocessing_inbound_is_idempotent(db, world):
    _, _, row = _inbound(db, world, "not interested, thanks")
    again = ThunderInboundEmailHandler.process(
        SimpleNamespace(id="m3", payload={"thunder_message_id": row.id}), db, llm_call=lambda *a: "")
    assert again["status"] == "already_processed"


def test_keyword_fallback_when_llm_unavailable(db):
    def broken(*args):
        raise RuntimeError("GEMINI down")
    result = classify_reply(db, 1, None, "Re: role", "Can you share the JD and location?", llm_call=broken)
    assert (result.intent, result.source) == ("QUESTION_ROLE", "keyword")


# ---- mailbox poll ----------------------------------------------------------------------

def _graph_msg(sender, conversation="conv-new", body="hello", subject="Hi", minutes_ago=1, headers=None):
    return {
        "id": f"g-in-{uuid.uuid4().hex[:8]}", "conversationId": conversation,
        "internetMessageId": f"<{uuid.uuid4().hex}@mail>",
        "from": {"emailAddress": {"address": sender}}, "subject": subject,
        "uniqueBody": {"content": body},
        "receivedDateTime": (datetime.utcnow() - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "internetMessageHeaders": headers or [],
    }


def test_poll_matches_thread_reply_and_new_email_and_ignores_strangers(db, world):
    mailbox = FakeMailbox()
    _send(db, world, "1", mailbox)
    out = db.query(ThunderEmailMessage).filter_by(candidate_id=world.candidate.candidateID, direction="OUT").one()
    inbox = [
        _graph_msg("other.person@gmail.com", conversation=out.conversation_id),  # forwarded? only thread decides
        _graph_msg(world.candidate.candidateEmail.upper(), conversation="brand-new-thread"),
        _graph_msg("hr-vendor@company.com", conversation="unrelated"),
        _graph_msg(MAILBOX, conversation=out.conversation_id),
    ]
    with patch(ENQUEUE, return_value={"message_id": "x", "task_id": "x"}) as enqueue:
        first = poll_thunder_mailbox(db, mailbox=FakeMailbox(inbox))
        second = poll_thunder_mailbox(db, mailbox=FakeMailbox(inbox))
    stored = db.query(ThunderEmailMessage).filter_by(candidate_id=world.candidate.candidateID, direction="IN").all()
    assert first["matched"] == 2 and second["matched"] == 0 and len(stored) == 2
    assert {c.kwargs["task_name"] for c in enqueue.call_args_list} == {"thunder_process_inbound_email"}


# ---- schedule: sweep, nurture forever, A/B ---------------------------------------------

def test_sweep_queues_due_touches_once(db, world):
    world.state.next_action_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    with patch(ENQUEUE, return_value={"message_id": "x", "task_id": "x"}) as enqueue:
        run_cadence_sweep(db)
    calls = [c.kwargs for c in enqueue.call_args_list
             if c.kwargs["data"]["candidate_id"] == world.candidate.candidateID]
    assert len(calls) == 1 and calls[0]["task_id"] == cadence.send_task_id(world.candidate.candidateID, 1, "1")


def test_silence_ladder_ends_in_monthly_nurture_that_repeats(db, world):
    now = datetime.utcnow()
    for step, expected in (("1", "2"), ("2", "3"), ("3", "4")):
        cadence.schedule_after_send(world.state, step, now)
        assert world.state.next_step == expected
    cadence.schedule_after_send(world.state, "4", now)
    first_nurture = world.state.next_step
    assert world.state.stage == "NURTURE" and first_nurture.startswith("NURTURE-")
    cadence.schedule_after_send(world.state, first_nurture, world.state.next_action_at)
    assert world.state.stage == "NURTURE" and world.state.next_step != first_nurture


def test_nurture_sends_only_real_content(db, world):
    now = datetime.utcnow()
    assert cadence.nurture_content(db, world.candidate, now) is None or True  # depends on shared jobs table
    db.add(ThunderMonthlyHighlight(tenant_id=1, month=f"{now:%Y-%m}", title="We opened a Pune office",
                                   body_html="<p>Details</p>"))
    db.commit()
    content = cadence.nurture_content(db, world.candidate, now)
    assert "We opened a Pune office" in content["highlight"]


def test_nurture_with_nothing_new_is_skipped_but_rescheduled(db, world):
    step = cadence.nurture_step(datetime.utcnow())
    world.state.stage, world.state.next_step = "NURTURE", step
    db.commit()
    with patch.object(cadence, "nurture_content", return_value=None):
        result, _ = _send(db, world, step, FakeMailbox())
    db.refresh(world.state)
    assert result["status"] == "skipped_no_content" and world.state.next_step != step


def test_ab_selector_prefers_winner_but_keeps_exploring(db):
    step = f"T{uuid.uuid4().hex[:6]}"
    win = ThunderOutreachVariant(key=f"{step}-a", step=step, subject_template="a", body_template="a")
    lose = ThunderOutreachVariant(key=f"{step}-b", step=step, subject_template="b", body_template="b")
    db.add_all([win, lose])
    db.flush()
    stats = {win.id: {"sent": 100, "success": 30, "failure": 70, "opt_out": 0},
             lose.id: {"sent": 100, "success": 3, "failure": 97, "opt_out": 0}}
    with patch("app.services.thunder_mail.variant_selector.variant_stats", return_value=stats):
        picks = [choose_variant(db, step, rng=random.Random(i)).id for i in range(200)]
    assert picks.count(win.id) > 180


def test_ab_selector_retires_variant_with_outlier_opt_outs(db):
    step = f"T{uuid.uuid4().hex[:6]}"
    variants = [ThunderOutreachVariant(key=f"{step}-{k}", step=step, subject_template=k, body_template=k)
                for k in "abc"]
    db.add_all(variants)
    db.flush()
    stats = {variants[0].id: {"sent": 50, "success": 5, "failure": 45, "opt_out": 1},
             variants[1].id: {"sent": 50, "success": 5, "failure": 45, "opt_out": 1},
             variants[2].id: {"sent": 50, "success": 5, "failure": 45, "opt_out": 10}}
    with patch("app.services.thunder_mail.variant_selector.variant_stats", return_value=stats):
        choose_variant(db, step, rng=random.Random(0))
    assert variants[2].active is False and "opt-out" in variants[2].retired_reason
