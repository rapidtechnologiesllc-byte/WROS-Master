"""Client Owner and the client team's emails (CEO 2026-10-30: "New Client and edit client doesnt have
client owner field it only has account manager fields, i added a client, i added an opportunity
nothing trigerred email to the internal team who is involved on that").

A client has a Client Owner beside its account manager (defaults to whoever adds it; editable,
audited). Adding a client or an opportunity emails the team -- Client Owner, account manager, BU
head, and the opportunity's own Client Owner and Account Manager -- once each, never the person who
did it. A new opportunity's Client Owner defaults to the client's. Held notifications are released
by the notification_release job, and a stale backlog is not mailed days late."""
import datetime as dt
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.scheduled_jobs import _JOBS
from app.models.client import Client, ClientContact, ClientHistory
from app.models.notification import Notification
from app.services.notification_service import release_backlog_guard
from tests.scope_fixtures import ApiClient, person, two_bu_world

QUEUE = "app.services.staff_mail_service.queue_staff_email"
HEAD = "app.services.bu_leadership.head_for_client"


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
    w.owner = person(db, w.org_role, "Owner")
    db.commit()
    return w


def _mailed(queue) -> dict:
    """user_id -> kwargs of the email queued for them."""
    return {call.args[0].UserID: call.kwargs for call in queue.call_args_list}


def _new_client(world, **extra):
    return {"company_name": f"Acme {uuid.uuid4().hex[:8]}", "business_unit_id": world.bu_a.id, **extra}


def test_new_client_emails_owner_account_manager_and_bu_head_but_not_the_creator(api, db, world):
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=world.partner_a.UserID):
        response = api.post(world.org_user, "/api/v1/clients", json=_new_client(
            world, client_owner_user_id=world.owner.UserID, account_manager_user_id=world.manager.UserID))
    assert response.status_code == 201, response.text
    client = db.query(Client).filter(Client.id == response.json()["id"]).one()
    assert client.client_owner_user_id == world.owner.UserID
    mailed = _mailed(queue)
    assert set(mailed) == {world.owner.UserID, world.manager.UserID, world.partner_a.UserID}
    assert "You are on it as: Client Owner." in mailed[world.owner.UserID]["paragraphs"]
    assert "You are on it as: Account Manager." in mailed[world.manager.UserID]["paragraphs"]
    assert mailed[world.owner.UserID]["key"] == f"client-created-{client.id}-{world.owner.UserID}"
    assert mailed[world.owner.UserID]["subject"].startswith("New client: Acme")
    assert db.query(ClientHistory).filter(ClientHistory.client_id == client.id,
                                          ClientHistory.change_type == "CLIENT_OWNER").count() == 1


def test_client_owner_defaults_to_the_creator_and_shows_in_the_list(api, db, world):
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=None):
        response = api.post(world.org_user, "/api/v1/clients", json=_new_client(world))
    assert response.status_code == 201, response.text
    assert queue.call_count == 0  # the creator alone is the team: nobody else to tell
    listed = {c["id"]: c for c in api.get(world.org_user, "/api/v1/clients?active_only=false").json()["clients"]}
    item = listed[response.json()["id"]]
    assert (item["client_owner_user_id"], item["client_owner_name"]) == (world.org_user.UserID, "Org user")


def test_a_failed_email_never_undoes_the_client(api, db, world):
    with patch(QUEUE, side_effect=RuntimeError("queue down")), patch(HEAD, return_value=None):
        response = api.post(world.org_user, "/api/v1/clients",
                            json=_new_client(world, client_owner_user_id=world.owner.UserID))
    assert response.status_code == 201, response.text
    assert db.query(Client).filter(Client.id == response.json()["id"]).count() == 1


def test_editing_the_client_owner_is_audited_and_emails_the_new_owner(api, db, world):
    with patch(QUEUE, return_value=True) as queue:
        response = api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}",
                             json={"client_owner_user_id": world.owner.UserID})
    assert response.status_code == 200, response.text
    assert (response.json()["client_owner_user_id"], response.json()["client_owner_name"]) == (world.owner.UserID, "Owner")
    assert set(_mailed(queue)) == {world.owner.UserID}
    with patch(QUEUE, return_value=True) as queue:  # same owner again: no change, no email
        api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}", json={"client_owner_user_id": world.owner.UserID})
    assert queue.call_count == 0
    assert db.query(ClientHistory).filter(ClientHistory.client_id == world.client_a.id,
                                          ClientHistory.change_type == "CLIENT_OWNER").count() == 1


def test_a_terminated_or_unknown_client_owner_is_refused(api, db, world):
    leaver = person(db, world.org_role, "Leaver")
    leaver.terminated_at = dt.datetime.utcnow()
    db.commit()
    for user_id in (leaver.UserID, "U-nobody"):
        response = api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}",
                             json={"client_owner_user_id": user_id})
        assert response.status_code == 400, response.text


def test_edit_client_status_goes_through_the_contact_rule(api, db, world):
    refused = api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}", json={"status": "ACTIVE"})
    assert refused.status_code == 400 and "client_contact" in refused.json()["detail"]
    db.add(ClientContact(client_id=world.client_a.id, tenant_id=1, name="Hiring", email="h@acme.test",
                         role_type="HIRING_MANAGER"))
    db.commit()
    accepted = api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}", json={"status": "ACTIVE"})
    assert accepted.status_code == 200 and accepted.json()["status"] == "ACTIVE"
    assert api.patch(world.org_user, f"/api/v1/clients/{world.client_a.id}",
                     json={"status": "BOGUS"}).status_code == 400


def test_new_opportunity_defaults_to_the_clients_owner_and_emails_the_team(api, db, world):
    world.client_a.client_owner_user_id = world.owner.UserID
    world.client_a.account_manager_user_id = world.manager.UserID
    db.commit()
    with patch(QUEUE, return_value=True) as queue, patch(HEAD, return_value=world.partner_a.UserID):
        response = api.post(world.org_user, "/api/v1/opportunities", json={
            "client_id": world.client_a.id, "revenue_value_usd_cents": 250_000_00, "service": "QA & Testing"})
    assert response.status_code == 201, response.text
    opportunity = response.json()
    assert opportunity["client_owner_id"] == world.owner.UserID
    mailed = _mailed(queue)
    assert set(mailed) == {world.owner.UserID, world.manager.UserID, world.partner_a.UserID}
    assert "You are on it as: Client Owner (opportunity), Client Owner." in mailed[world.owner.UserID]["paragraphs"]
    facts = mailed[world.manager.UserID]["paragraphs"][2]
    assert "Service: QA & Testing" in facts and "$250,000" in facts
    assert mailed[world.manager.UserID]["key"] == f"opportunity-created-{opportunity['id']}-{world.manager.UserID}"
    assert mailed[world.manager.UserID]["link_path"] == "/opportunity-pipeline"


def test_held_notifications_are_released_by_a_scheduled_job(db, world):
    assert "notification_release" in {job.name for job in _JOBS}
    now = dt.datetime.utcnow()
    stale = Notification(tenant_id=1, recipient_id=world.owner.UserID, channel="EMAIL", priority_tier="P1",
                         message="old", delivery_status="PENDING", scheduled_release_at=now - dt.timedelta(days=3))
    fresh = Notification(tenant_id=1, recipient_id=world.owner.UserID, channel="EMAIL", priority_tier="P1",
                         message="new", delivery_status="PENDING", scheduled_release_at=now - dt.timedelta(hours=1))
    db.add_all([stale, fresh])
    db.flush()
    release_backlog_guard(db, now)
    db.refresh(stale)
    db.refresh(fresh)
    assert (stale.delivery_status, fresh.delivery_status) == ("FAILED", "PENDING")
