"""
EPIC-14/S-435 (HRMS-1408) mail half. graph_call is injected throughout
-- no test ever hits a real Microsoft endpoint. Throwaway SQLite --
never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.activity_timeline import ActivityTimeline
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.employee import Employee
from app.models.tenant import Tenant
from app.models.user import Users

from app.services.msgraph_mail_sync_service import (
    run_msgraph_mail_sync_job,
    sync_mail_for_user,
)


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, Candidate.__table__, Employee.__table__,
        ActivityTimeline.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _make_user(db, user_id="U-HR"):
    user = Users(UserID=user_id, UserRole="Recruiter", UserEmail=f"{user_id}@blitzenx.com", UserPassword="h")
    db.add(user)
    db.commit()
    return user


def _make_candidate(db, candidate_id="C-1", email="priya@example.com"):
    candidate = Candidate(
        candidateID=candidate_id, candidateEmail=email, candidatePassword="h",
        candidateFirstName="Priya", candidateLastName="Rao",
    )
    db.add(candidate)
    db.commit()
    return candidate


def _fake_graph_call(inbox_messages=None, sent_messages=None):
    inbox_messages = inbox_messages or []
    sent_messages = sent_messages or []

    def call(access_token, endpoint):
        if "/inbox/" in endpoint:
            return {"value": inbox_messages}
        if "/sentitems/" in endpoint:
            return {"value": sent_messages}
        return {"value": []}
    return call


def test_links_inbound_message_from_candidate(db_session):
    _make_candidate(db_session, "C-1", "priya@example.com")
    user = _make_user(db_session)
    graph_call = _fake_graph_call(inbox_messages=[{
        "subject": "Re: Interview",
        "from": {"emailAddress": {"address": "priya@example.com"}},
        "receivedDateTime": "2026-08-05T10:00:00Z",
        "webLink": "https://outlook.office.com/mail/id/1",
    }])

    result = sync_mail_for_user(db_session, user, "fake-token", graph_call=graph_call)

    assert result == {"linked": 1, "synced": True}
    entry = db_session.query(ActivityTimeline).first()
    assert entry.entity_id == "C-1"
    assert entry.action == "EMAIL_RECEIVED"


def test_links_outbound_message_to_candidate(db_session):
    _make_candidate(db_session, "C-1", "priya@example.com")
    user = _make_user(db_session)
    graph_call = _fake_graph_call(sent_messages=[{
        "subject": "Offer Letter",
        "toRecipients": [{"emailAddress": {"address": "priya@example.com"}}],
        "sentDateTime": "2026-08-05T11:00:00Z",
    }])

    result = sync_mail_for_user(db_session, user, "fake-token", graph_call=graph_call)

    assert result == {"linked": 1, "synced": True}
    entry = db_session.query(ActivityTimeline).first()
    assert entry.action == "EMAIL_SENT"


def test_unmatched_message_is_not_linked_but_sync_still_advances(db_session):
    user = _make_user(db_session)
    graph_call = _fake_graph_call(inbox_messages=[{
        "subject": "Newsletter",
        "from": {"emailAddress": {"address": "noreply@somevendor.com"}},
        "receivedDateTime": "2026-08-05T10:00:00Z",
    }])

    result = sync_mail_for_user(db_session, user, "fake-token", graph_call=graph_call)

    assert result == {"linked": 0, "synced": True}
    assert db_session.query(ActivityTimeline).count() == 0
    assert user.msgraph_mail_last_synced_at is not None


def test_advances_high_water_mark_on_success(db_session):
    user = _make_user(db_session)
    now = datetime(2026, 8, 5, 12, 0, 0)

    sync_mail_for_user(db_session, user, "fake-token", graph_call=_fake_graph_call(), now=now)

    assert user.msgraph_mail_last_synced_at == now


def test_does_not_advance_high_water_mark_on_fetch_failure(db_session):
    user = _make_user(db_session)
    original = datetime(2026, 8, 4, 12, 0, 0)
    user.msgraph_mail_last_synced_at = original
    db_session.add(user)
    db_session.commit()

    def failing_call(access_token, endpoint):
        raise ConnectionError("Graph API unreachable")

    result = sync_mail_for_user(db_session, user, "fake-token", graph_call=failing_call)

    assert result["synced"] is False
    assert user.msgraph_mail_last_synced_at == original


def test_first_sync_uses_default_lookback_not_full_mailbox(db_session):
    user = _make_user(db_session)
    assert user.msgraph_mail_last_synced_at is None

    captured_endpoints = []

    def call(access_token, endpoint):
        captured_endpoints.append(endpoint)
        return {"value": []}

    now = datetime(2026, 8, 5, 12, 0, 0)
    sync_mail_for_user(db_session, user, "fake-token", graph_call=call, now=now)

    expected_since = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert any(expected_since in e for e in captured_endpoints)


def test_run_job_syncs_every_linked_user(db_session):
    _make_candidate(db_session, "C-1", "priya@example.com")
    user_a = _make_user(db_session, "U-A")
    user_b = _make_user(db_session, "U-B")

    import app.core.msgraph_session_store as store
    store.account_id_by_user_id.clear()
    store.user_tokens.clear()
    store.account_id_by_user_id["U-A"] = "oid-a"
    store.account_id_by_user_id["U-B"] = "oid-b"
    store.user_tokens["oid-a"] = {"access_token": "token-a"}
    store.user_tokens["oid-b"] = {"access_token": "token-b"}

    import app.services.msgraph_mail_sync_service as svc
    original_default = svc._default_graph_messages_call
    svc._default_graph_messages_call = _fake_graph_call(inbox_messages=[{
        "subject": "Hello",
        "from": {"emailAddress": {"address": "priya@example.com"}},
        "receivedDateTime": "2026-08-05T10:00:00Z",
    }])
    try:
        result = run_msgraph_mail_sync_job(db_session)
    finally:
        svc._default_graph_messages_call = original_default
        store.account_id_by_user_id.clear()
        store.user_tokens.clear()

    assert result["synced_users"] == 2
    assert result["total_linked"] == 2  # both users' inbox each produce 1 match


def test_run_job_skips_users_without_a_live_token(db_session):
    user = _make_user(db_session, "U-STALE")

    import app.core.msgraph_session_store as store
    store.account_id_by_user_id.clear()
    store.user_tokens.clear()
    store.account_id_by_user_id["U-STALE"] = "oid-stale"
    # deliberately no user_tokens entry -- mapping exists, token doesn't

    try:
        result = run_msgraph_mail_sync_job(db_session)
    finally:
        store.account_id_by_user_id.clear()
        store.user_tokens.clear()

    assert result == {"synced_users": 0, "total_linked": 0}
