"""Emails go from the person responsible, in their own Outlook, with the helpdesk copied (CEO 2026-11-03:
"all emails should be sent by the user logged in and not helpdesk_hrms. Helpdesk is the kind of thought
where we keep it as a repository"); a new user sets their own password from an emailed link."""
import random
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.mailbox_intake import MailboxIntakeMessage
from app.models.org_structure import OrgNode
from app.models.outbound_email import OutboundEmailSender
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.models.thunder_email import ThunderEmailMessage
from app.models.user import Users
from app.services import mail_sender
from app.services.message_handlers.send_staff_email_handler import SendStaffEmailHandler
from app.services.message_handlers.thunder_send_email_handler import ThunderSendEmailHandler
from app.services.thunder_mail import cadence_service as cadence
from app.services.thunder_mail.graph_mailbox import GraphMailbox
from app.services.thunder_mail.mail_poll_service import poll_connected_mailboxes, poll_thunder_mailbox
from app.services.thunder_mail.seed_variants import seed_thunder_variants

HELPDESK = "helpdesk_hrms@blitzenx.com"
THUNDER = "app.services.message_handlers.thunder_send_email_handler"


def uid():
    return uuid.uuid4().hex[:8]


class FakeMailbox:
    def __init__(self, address, inbox=None):
        self.mailbox, self.inbox = address, inbox or []
        self.drafts, self.sent = {}, []

    def create_draft(self, to, subject, html, ref):
        mid = f"g-{uid()}"
        self.drafts[mid] = {"to": to, "subject": subject}
        return mid, f"conv-{mid}", f"<{mid}@blitzenx.com>"

    def create_reply_draft(self, parent_id, html):
        mid = f"g-{uid()}"
        self.drafts[mid] = {"reply_to": parent_id}
        return mid, "conv-thread", f"<{mid}@blitzenx.com>"

    def is_draft(self, mid):
        return mid not in self.sent

    def send(self, mid):
        self.sent.append(mid)

    def list_inbox(self, since, page_cap=10):
        return self.inbox


class FakeHttp:
    def __init__(self):
        self.calls = []

    def request(self, method, url, json=None, params=None, headers=None, timeout=None):
        self.calls.append((method, url, json))
        body = {"id": f"g-{uid()}", "conversationId": "c", "internetMessageId": "<x@y>", "ccRecipients": []}
        return SimpleNamespace(status_code=201, content=b"x", json=lambda: body, headers={}, text="")


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
def people(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    template = RoleTemplate(tenant_id=1, name=f"staff-{uid()}", display_name="Staff", hierarchy_level=4)
    db.add(template)
    db.flush()
    make = lambda name: Users(UserID=f"U-{uid()}", UserName=name, UserEmail=f"{name.lower()}{uid()}@blitzenx.com",  # noqa: E731
                              UserPassword="h", UserRole="Staff", tenant_id=1, role_template_id=template.id)
    recruiter, colleague = make("Riya"), make("Sam")
    db.add_all([recruiter, colleague])
    db.commit()
    return SimpleNamespace(recruiter=recruiter, colleague=colleague, template=template)


def test_a_persons_mailbox_copies_the_helpdesk_on_new_emails_and_replies():
    http = FakeHttp()
    mine = GraphMailbox("riya@blitzenx.com", http=http, token_provider=lambda: "t", cc=[HELPDESK], delegated=True)
    mine.create_draft("candidate@example.com", "Hello", "<p>Hi</p>", "ref")
    mine.create_reply_draft("parent", "<p>Thanks</p>")
    new, _, patch_call = http.calls
    assert new[2]["ccRecipients"] == [{"emailAddress": {"address": HELPDESK}}]
    assert patch_call[2]["ccRecipients"] == [{"emailAddress": {"address": HELPDESK}}]
    helpdesk_http = FakeHttp()
    GraphMailbox(HELPDESK, http=helpdesk_http, token_provider=lambda: "t", cc=[HELPDESK]) \
        .create_draft("candidate@example.com", "Hello", "<p>Hi</p>", "ref")
    assert "ccRecipients" not in helpdesk_http.calls[0][2]  # the helpdesk never copies itself


def test_the_sender_is_the_connected_person_else_the_helpdesk_and_retries_keep_it(db, people):
    riya = FakeMailbox(people.recruiter.UserEmail)
    with patch.object(mail_sender, "connected_mailbox",
                      side_effect=lambda db, user_id: riya if user_id == people.recruiter.UserID else None):
        assert mail_sender.sender_for(db, "k-1", [people.colleague.UserID]).mailbox == HELPDESK
        assert mail_sender.sender_for(db, "k-2", [None, people.recruiter.UserID]) is riya
        db.commit()
        assert mail_sender.sender_for(db, "k-2", [people.colleague.UserID]) is riya  # a retry: same mailbox
    assert db.get(OutboundEmailSender, "k-2").sender_user_id == people.recruiter.UserID
    with pytest.raises(Exception, match="reconnect"):  # disconnected since: the draft is in their mailbox
        mail_sender.mailbox_for_address(db, people.recruiter.UserEmail)


def test_a_staff_email_goes_from_the_person_who_did_the_action(db, people):
    sam = FakeMailbox(people.colleague.UserEmail)
    message = SimpleNamespace(id=f"m-{uid()}", payload={"user_id": people.recruiter.UserID, "subject": "Task #9",
                                                       "html": "<p>Please</p>", "sender_user_id": people.colleague.UserID})
    with patch.object(mail_sender, "connected_mailbox",
                      side_effect=lambda db, user_id: sam if user_id == people.colleague.UserID else None):
        result = SendStaffEmailHandler.process(message, db)
    assert result["status"] == "sent" and len(sam.sent) == 1
    assert db.get(OutboundEmailSender, f"staff:{message.id}").internet_message_id.endswith("@blitzenx.com>")


@pytest.fixture
def candidate(db, people):
    seed_thunder_variants(db)
    person = Candidate(tenant_id=1, candidateID=f"CAN-{uid()}", candidateEmail=f"ankur{uid()}@ankur.dev",
                       candidatePassword="h", candidateFirstName="Ankurjit", candidateLastName="Singh",
                       candidateSkills="Guidewire", thunder_enabled=True, timezone="UTC",
                       assigned_recruiter_id=people.recruiter.UserID)
    db.add(person)
    db.flush()
    state = cadence.start_cadence(db, person)
    db.commit()
    return SimpleNamespace(candidate=person, state=state)


def _send(db, candidate, step):
    message = SimpleNamespace(id=f"m-{uid()}", payload={"candidate_id": candidate.candidate.candidateID,
                                                       "cadence_seq": 1, "step": step, "tenant_id": 1})
    with patch.object(cadence, "next_send_slot", return_value=None), \
         patch("app.services.message_queue_service.MessageQueueService.enqueue", return_value={"message_id": "x"}):
        return ThunderSendEmailHandler.process(message, db, rng=random.Random(1))


def test_thunder_writes_from_the_recruiter_and_follow_ups_stay_in_that_thread(db, people, candidate):
    riya = FakeMailbox(people.recruiter.UserEmail)
    pick = lambda db, user_id: riya if user_id == people.recruiter.UserID else None  # noqa: E731
    with patch(f"{THUNDER}.connected_mailbox", side_effect=pick), \
         patch(f"{THUNDER}.mailbox_for_address", side_effect=lambda db, address: riya):
        assert _send(db, candidate, "1")["status"] == "sent"
        first = db.query(ThunderEmailMessage).filter_by(candidate_id=candidate.candidate.candidateID, step="1").one()
        assert first.mailbox == people.recruiter.UserEmail and len(riya.sent) == 1
        candidate.state.last_outbound_at = datetime.utcnow() - timedelta(days=10)
        candidate.state.next_step = "2"
        db.commit()
        assert _send(db, candidate, "2")["status"] == "sent"
    follow_up = db.query(ThunderEmailMessage).filter_by(candidate_id=candidate.candidate.candidateID, step="2").one()
    assert follow_up.mailbox == people.recruiter.UserEmail
    assert riya.drafts[follow_up.graph_message_id]["reply_to"] == first.graph_message_id


def test_without_outlook_connected_thunder_writes_from_the_helpdesk(db, candidate):
    helpdesk = FakeMailbox(HELPDESK)
    with patch(f"{THUNDER}.connected_mailbox", return_value=None), \
         patch(f"{THUNDER}.GraphMailbox", return_value=helpdesk):
        assert _send(db, candidate, "1")["status"] == "sent"
    assert db.query(ThunderEmailMessage).filter_by(candidate_id=candidate.candidate.candidateID, step="1").one() \
        .mailbox == HELPDESK


def _inbox_message(sender, *, conversation="conv-x", internet_id=None, subject="Re: the role"):
    return {"id": f"in-{uid()}", "conversationId": conversation, "internetMessageId": internet_id or f"<{uid()}@ext>",
            "from": {"emailAddress": {"address": sender}}, "toRecipients": [], "subject": subject,
            "uniqueBody": {"content": "Yes, interested."}, "receivedDateTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "internetMessageHeaders": []}


def test_the_helpdesk_copy_of_our_own_email_is_never_a_forward(db, people):
    db.add(OutboundEmailSender(key=f"staff:{uid()}", tenant_id=1, mailbox=people.colleague.UserEmail,
                               sender_user_id=people.colleague.UserID, internet_message_id="<ours@blitzenx.com>"))
    db.commit()
    copy = _inbox_message(people.colleague.UserEmail, internet_id="<ours@blitzenx.com>", subject="Task #9")
    with patch("app.services.thunder_mail.mail_poll_service.enqueue_once"):
        poll_thunder_mailbox(db, mailbox=FakeMailbox(HELPDESK, [copy]))
    assert db.query(MailboxIntakeMessage).filter_by(graph_message_id=copy["id"]).count() == 0
    assert db.query(ThunderEmailMessage).filter_by(graph_message_id=copy["id"]).count() == 0


def test_a_persons_mailbox_is_read_only_for_replies_in_our_threads(db, people, candidate):
    address = people.recruiter.UserEmail.lower()
    db.add(ThunderEmailMessage(id=str(uuid.uuid4()), tenant_id=1, candidate_id=candidate.candidate.candidateID,
                               direction="OUT", status="SENT", cadence_seq=1, step="1", mailbox=address,
                               graph_message_id=f"g-{uid()}", conversation_id="conv-ours",
                               internet_message_id="<first@blitzenx.com>", sent_at=datetime.utcnow()))
    db.commit()
    reply = _inbox_message(candidate.candidate.candidateEmail, conversation="conv-ours")
    private = _inbox_message("friend@example.com", conversation="conv-private", subject="Dinner?")
    with patch("app.services.thunder_mail.mail_poll_service.enqueue_once") as queued:
        result = poll_connected_mailboxes(db, mailboxes={address: FakeMailbox(address, [reply, private])})
    assert result["matched"] == 1 and queued.call_count == 1
    stored = db.query(ThunderEmailMessage).filter_by(graph_message_id=reply["id"]).one()
    assert (stored.direction, stored.mailbox) == ("IN", address)
    assert db.query(ThunderEmailMessage).filter_by(graph_message_id=private["id"]).count() == 0
    # the same reply, also reaching the helpdesk (reply-all), is not stored twice
    with patch("app.services.thunder_mail.mail_poll_service.enqueue_once"):
        poll_thunder_mailbox(db, mailbox=FakeMailbox(HELPDESK, [dict(reply, id=f"in-{uid()}")]))
    assert db.query(ThunderEmailMessage).filter_by(internet_message_id=reply["internetMessageId"]).count() == 1


def test_a_new_user_gets_a_set_your_password_link_not_a_password(db, people):
    from app.services.message_handlers.create_user_with_roles_handler import handle_create_user_with_roles
    from app.core.db_contract import _initialize_org_positions
    from app.services.org_structure_service import create_org_node

    _initialize_org_positions(db)  # what startup seeds
    ceo = db.query(OrgNode).filter(OrgNode.tenant_id == 1, OrgNode.hierarchy_level == 17,
                                   OrgNode.active.is_(True)).first() \
        or create_org_node(db, tenant_id=1, name="CEO seat", hierarchy_level=17, specialization="General")
    db.commit()
    email = f"accountant{uid()}@blitzenx.com"
    message = SimpleNamespace(id=f"m-{uid()}", payload={
        "user_email": email, "user_name": "New Accountant", "role_ids": [people.template.id], "tenant_id": 1,
        "hierarchy_level": 16, "parent_node_id": ceo.id, "job_title": "Partner",
        "created_by_user_id": people.colleague.UserID})
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True) as queued:
        result = handle_create_user_with_roles(message, db)
    user = db.query(Users).filter(Users.UserEmail == email).one()
    assert result["welcome_email"] == "queued" and user.password_reset_required is True
    task_name, _, payload = queued.call_args.args[:3]
    assert task_name == "send_account_email" and payload == {"user_id": user.UserID, "purpose": "ACTIVATE"}
    assert "user_password" not in message.payload
