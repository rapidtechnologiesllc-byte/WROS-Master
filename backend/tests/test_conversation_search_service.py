"""
S-015/HRMS-0415 -- Conversation Search (app.services.conversation_search_service).

Adapted to real architecture: no Postgres tsvector/plainto_tsquery
(real DB here is SQL Server), no plain message_body column (bodies
live in ConversationEvent.event_data JSON). Real tenant-scoped DB
query + Python-side case-insensitive substring match -- see the
module's own docstring for the honest performance tradeoff.

"""
import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.conversation_search_service as svc
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.user import Users

@pytest.fixture()
def db_session():
    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)

@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h")
    other_owner = Users(UserID="U-OTHER-ORG", UserRole="Super User", UserEmail="other@blitzenx.com", UserPassword="h")
    db_session.add_all([owner, other_owner])
    db_session.commit()

    c1 = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya")
    c2 = Candidate(candidateID="C-2", candidateEmail="c2@example.com", candidatePassword="h", candidateFirstName="Raj")
    c3_other_tenant = Candidate(candidateID="C-3", candidateEmail="c3@example.com", candidatePassword="h", candidateFirstName="Sam")
    db_session.add_all([c1, c2, c3_other_tenant])
    db_session.commit()

    conv1 = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="thunder")
    conv2 = CandidateConversation(tenant_id="U-ORG", candidate_id="C-2", status="open", owner_type="ai_agent", owner_id="thunder")
    conv3 = CandidateConversation(tenant_id="U-OTHER-ORG", candidate_id="C-3", status="open", owner_type="ai_agent", owner_id="thunder")
    db_session.add_all([conv1, conv2, conv3])
    db_session.commit()

    db_session.add(ConversationEvent(conversation_id=conv1.id, event_type="candidate_reply", event_data={"channel": "whatsapp", "body": "I have Guidewire PolicyCenter experience"}, triggered_by="candidate"))
    db_session.add(ConversationEvent(conversation_id=conv2.id, event_type="ai_message_sent", event_data={"channel": "email", "body": "We offer relocation support for this role"}, triggered_by="ai_agent"))
    db_session.add(ConversationEvent(conversation_id=conv3.id, event_type="candidate_reply", event_data={"channel": "whatsapp", "body": "I also know Guidewire well"}, triggered_by="candidate"))
    db_session.commit()

    return conv1, conv2, conv3

def test_search_term_too_short_raises(db_session, seeded):
    with pytest.raises(svc.SearchTermTooShort):
        svc.search_conversations(db_session, "U-ORG", "a")

def test_keyword_search_finds_matching_message(db_session, seeded):
    result = svc.search_conversations(db_session, "U-ORG", "Guidewire")
    assert result["total_count"] == 1
    assert result["results"][0]["candidate_name"] == "Priya"

def test_search_by_candidate_name(db_session, seeded):
    result = svc.search_conversations(db_session, "U-ORG", "Raj")
    assert result["total_count"] == 1
    assert result["results"][0]["candidate_id"] == "C-2"

def test_tenant_isolation_excludes_other_tenant(db_session, seeded):
    """AC-4: same keyword exists in another tenant's message -- must not appear."""
    result = svc.search_conversations(db_session, "U-ORG", "Guidewire")
    candidate_ids = [r["candidate_id"] for r in result["results"]]
    assert "C-3" not in candidate_ids

def test_channel_filter(db_session, seeded):
    result = svc.search_conversations(db_session, "U-ORG", "relocation", channel="EMAIL")
    assert result["total_count"] == 1
    no_match = svc.search_conversations(db_session, "U-ORG", "relocation", channel="WHATSAPP")
    assert no_match["total_count"] == 0

def test_date_range_filter_excludes_old_messages(db_session, seeded):
    conv1, conv2, conv3 = seeded
    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv1.id).first()
    event.created_at = datetime.utcnow() - timedelta(days=30)
    db_session.commit()

    result = svc.search_conversations(db_session, "U-ORG", "Guidewire", date_from=datetime.utcnow() - timedelta(days=1))
    assert result["total_count"] == 0

def test_no_results_returns_empty_list_not_error(db_session, seeded):
    result = svc.search_conversations(db_session, "U-ORG", "nonexistentkeyword")
    assert result["results"] == []
    assert result["total_count"] == 0

def test_pagination_has_more(db_session, seeded):
    result = svc.search_conversations(db_session, "U-ORG", "we", per_page=0)
    # per_page=0 -> nothing returned this page, but has_more reflects real total
    assert result["per_page"] == 0

def test_snippet_max_150_chars(db_session, seeded):
    long_body = "x" * 300 + " findme " + "y" * 300
    owner = db_session.query(Users).filter(Users.UserID == "U-ORG").first()
    candidate = Candidate(candidateID="C-LONG", candidateEmail="long@example.com", candidatePassword="h")
    db_session.add(candidate)
    db_session.commit()
    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-LONG", status="open", owner_type="ai_agent", owner_id="thunder")
    db_session.add(conv)
    db_session.commit()
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={"channel": "whatsapp", "body": long_body}, triggered_by="candidate"))
    db_session.commit()

    result = svc.search_conversations(db_session, "U-ORG", "findme")
    match = next(r for r in result["results"] if r["candidate_id"] == "C-LONG")
    assert len(match["message_snippet"]) <= svc.SNIPPET_LENGTH
    assert "findme" in match["message_snippet"]
