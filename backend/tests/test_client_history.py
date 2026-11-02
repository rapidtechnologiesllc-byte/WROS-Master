"""Client History (CEO 2026-11-02: "there is no history for this client, doesnt show what emails was
sent when, by whom ... when we change internal changes is it being sent as email to the responsible
resource" / "when an email is sent from my email to this client you need to log it on this client
... we can always CC helpdesk").

Every saved change is in ClientHistory (who, when, old -> new). A change that moves responsibility
(business unit, status, account manager, client owner, contracting company) emails the client's team
once, including the new BU's partner and the person who was replaced; plain field edits do not. Every
team email, and every email to or from the client's people that reaches the helpdesk mailbox, is
listed on the client's History."""
import uuid
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.client import Client, ClientContact, ClientEmail, ClientHistory
from app.models.mailbox_intake import MailboxIntakeMessage
from app.services.thunder_mail.mail_poll_service import poll_thunder_mailbox
from tests.scope_fixtures import ApiClient, person, two_bu_world

QUEUE = "app.services.staff_mail_service.queue_staff_email"
HEAD = "app.services.bu_leadership.head_for_client"
MAILBOX = "helpdesk_hrms@blitzenx.com"


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
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@pytest.fixture
def world(db):
    w = two_bu_world(db)
    w.manager = person(db, w.org_role, "Manager")
    w.other_manager = person(db, w.org_role, "Other Manager")
    w.client_a.account_manager_user_id = w.manager.UserID
    w.client_a.website = f"www.acme{uuid.uuid4().hex[:6]}.com"
    db.commit()
    return w


def _history(api, world):
    response = api.get(world.org_user, f"/api/v1/clients/{world.client_a.id}/history")
    assert response.status_code == 200, response.text
    return response.json()


def _mailed(queue) -> dict:
    return {call.args[0].UserID: call.kwargs for call in queue.call_args_list}


def test_field_edits_are_history_only(api, db, world):
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=None):
        response = api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}",
                             json={"country": "India", "payment_terms_days": 45})
    assert response.status_code == 200, response.text
    assert response.json()["country"] == "India"
    assert queue.call_count == 0

    entry = next(e for e in _history(api, world)["entries"] if e["title"] == "Details edited")
    assert entry["by"] == "Org user"
    assert "Country: blank -> India" in entry["lines"]
    assert "Payment terms days: 30 -> 45" in entry["lines"]


def test_blank_to_empty_text_is_not_a_change(api, db, world):
    world.client_a.notes = None
    db.commit()
    with patch(QUEUE, return_value=True), patch(HEAD, return_value=None):
        api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}", json={"notes": "", "country": "India"})
    entry = next(e for e in _history(api, world)["entries"] if e["title"] == "Details edited")
    assert entry["lines"] == ["Country: blank -> India"]


def test_unchanged_save_writes_no_history(api, db, world):
    with patch(QUEUE, return_value=True), patch(HEAD, return_value=None):
        api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}",
                  json={"business_unit_id": world.bu_a.id, "tier": world.client_a.tier})
    assert db.query(ClientHistory).filter(ClientHistory.client_id == world.client_a.id).count() == 0


def test_business_unit_change_emails_team_and_new_partner_and_is_listed(api, db, world):
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=None):
        response = api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}",
                             json={"business_unit_id": world.bu_b.id})
    assert response.status_code == 200, response.text
    mailed = _mailed(queue)
    assert set(mailed) == {world.manager.UserID, world.partner_b.UserID}
    moved = f"Business unit: {world.bu_a.name} -> {world.bu_b.name}"
    assert any(moved in p for p in mailed[world.partner_b.UserID]["paragraphs"])
    assert "Partner of the new business unit" in " ".join(mailed[world.partner_b.UserID]["paragraphs"])

    history = _history(api, world)["entries"]
    change = next(e for e in history if e["title"] == "Business unit changed")
    assert change["lines"] == [moved]
    team_emails = [e for e in history if e["kind"] == "EMAIL" and e["direction"] == "TEAM"]
    assert {e["to_addresses"] for e in team_emails} == {world.manager.UserEmail, world.partner_b.UserEmail}


def test_account_manager_change_tells_new_and_former_manager(api, db, world):
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=None):
        response = api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}",
                             json={"account_manager_user_id": world.other_manager.UserID})
    assert response.status_code == 200, response.text
    mailed = _mailed(queue)
    assert set(mailed) == {world.manager.UserID, world.other_manager.UserID}
    assert "Former Account Manager" in " ".join(mailed[world.manager.UserID]["paragraphs"])
    assert any("active demand(s)" in p for p in mailed[world.other_manager.UserID]["paragraphs"])


def test_failed_save_leaves_nothing_half_saved(api, db, world):
    original_bu = world.client_a.business_unit_id
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=None):
        response = api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}",
                             json={"business_unit_id": world.bu_b.id, "payment_terms_days": -1})
    assert response.status_code == 400
    db.expire_all()
    assert db.query(Client).filter(Client.id == world.client_a.id).one().business_unit_id == original_bu
    assert db.query(ClientHistory).filter(ClientHistory.client_id == world.client_a.id).count() == 0
    assert queue.call_count == 0


class FakeMailbox:
    def __init__(self, inbox):
        self.inbox = inbox

    def list_inbox(self, since, page_cap=10):
        return self.inbox


def _message(sender, to, cc=(), subject="Hello"):
    return {
        "id": f"graph-{uuid.uuid4().hex}", "conversationId": f"conv-{uuid.uuid4().hex}",
        "receivedDateTime": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "from": {"emailAddress": {"address": sender}},
        "toRecipients": [{"emailAddress": {"address": a}} for a in to],
        "ccRecipients": [{"emailAddress": {"address": a}} for a in cc],
        "subject": subject, "uniqueBody": {"content": "Following up on the proposal."},
        "internetMessageHeaders": [],
    }


def test_staff_email_with_helpdesk_on_cc_is_logged_on_the_client(db, api, world):
    contact = ClientContact(client_id=world.client_a.id, name="Pat Buyer", email=f"pat{uuid.uuid4().hex[:6]}@buyer.io",
                            role_type="HIRING_MANAGER")
    db.add(contact)
    db.commit()
    domain = world.client_a.website.replace("www.", "")
    sent = _message(world.manager.UserEmail, [contact.email], cc=[MAILBOX], subject="Proposal")
    reply = _message(f"cfo@{domain}", [MAILBOX], subject="Re: Proposal")

    result = poll_thunder_mailbox(db, mailbox=FakeMailbox([sent, reply]))
    assert result["client_emails"] == 2
    assert db.query(MailboxIntakeMessage).filter(
        MailboxIntakeMessage.graph_message_id == sent["id"]).count() == 0  # not treated as a forward

    rows = {e.message_key: e for e in db.query(ClientEmail).filter(ClientEmail.client_id == world.client_a.id)}
    assert rows[sent["id"]].direction == "OUT"
    assert rows[sent["id"]].sent_by_user_id == world.manager.UserID
    assert rows[reply["id"]].direction == "IN"

    history = _history(api, world)
    assert history["logging_mailbox"].lower() == MAILBOX
    titles = [e["title"] for e in history["entries"] if e["kind"] == "EMAIL"]
    assert "Email sent to the client: Proposal" in titles
    assert "Email from the client: Re: Proposal" in titles

    # the next poll overlaps: nothing is logged twice
    poll_thunder_mailbox(db, mailbox=FakeMailbox([sent, reply]))
    assert db.query(ClientEmail).filter(ClientEmail.client_id == world.client_a.id).count() == 2
