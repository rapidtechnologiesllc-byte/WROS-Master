"""
import logging
S-055/HRMS-0455 -- Offer FAQ Bot.

Real architecture under test (see offer_faq_service module docstring):
no system_configuration table -- offer_faq_entries (new) + a real
module-constant fallback; BR-03's gate maps to the one real signal
that exists (conversation.offer_faq_active); BR-01 negotiation
questions always escalate via the same real primitives S-035's
execute_escalation() is built from; BR-02 enforces answers reference
real offer data via a cheap post-LLM heuristic; Gemini via an
injectable llm_call so no test ever hits a real external API.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.consent import ConsentRecord
from app.models.notification import Notification
from app.models.offer_faq_entry import OfferFAQEntry
from app.models.offer_letter import OfferLetter
from app.models.submission import Submission, SubmissionViolation
from app.models.tenant import Tenant
from app.models.client import Client
from app.models.demand import Demand, DemandHistory
from app.models.recruiter_intervention_queue import RecruiterInterventionQueue
from app.models.user import Users

import app.services.offer_faq_service as svc


@pytest.fixture(autouse=True)
def _fake_whatsapp_number(monkeypatch):
    import app.services.whatsapp_routing_service as wr_svc
    monkeypatch.setattr(wr_svc, "DEFAULT_WHATSAPP_NUMBER", "+15550009999")


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        OfferLetter.__table__, OfferFAQEntry.__table__, ConsentRecord.__table__, Notification.__table__,
        Tenant.__table__, Client.__table__, Demand.__table__, DemandHistory.__table__,
        Submission.__table__, SubmissionViolation.__table__, RecruiterInterventionQueue.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def seeded(db_session):
    owner = Users(UserID="U-ORG", UserRole="Super User", UserEmail="ceo@blitzenx.com", UserPassword="h", tenant_id=None)
    recruiter = Users(UserID="U-RECRUITER", UserRole="Recruiter", UserEmail="recruiter@blitzenx.com", UserPassword="h", tenant_id=None)
    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateMobile="+919876543210")
    db_session.add_all([owner, recruiter, candidate])
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp", offer_faq_active=True)
    db_session.add(conv)
    db_session.add(ConsentRecord(subject_type="candidate", subject_id="C-1", consent_type="whatsapp_outreach", consent_given=True, captured_by="candidate_self_service"))
    db_session.commit()

    offer = OfferLetter(candidate_id="C-1", position="Sr. Guidewire Developer", salary="24 LPA", joining_date=date(2026, 9, 1), offer_expire_date=date(2026, 8, 20), offer_status="Released", approval_status="Approved", released_by="U-ORG")
    db_session.add(offer)
    db_session.commit()

    return candidate, conv, offer


def _fake_llm(answer):
    return lambda prompt: answer


# ── BR-03: only active when offer_faq_active=true ─────────────────────

def test_not_active_when_offer_faq_flag_false(db_session, seeded):
    candidate, conv, offer = seeded
    conv.offer_faq_active = False
    db_session.commit()

    result = svc.answer_offer_question(db_session, candidate, conv, "U-ORG", "When do I start?")
    assert result["outcome"] == "not_active"


def test_no_offer_found(db_session, seeded):
    candidate, conv, offer = seeded
    offer.offer_status = "Pending"
    db_session.commit()

    result = svc.answer_offer_question(db_session, candidate, conv, "U-ORG", "When do I start?")
    assert result["outcome"] == "no_offer_found"


# ── TC-001/AC-1: start date question answered with real offer data ───

def test_start_date_question_answered_with_real_data(db_session, seeded):
    candidate, conv, offer = seeded
    llm_call = _fake_llm("Your start date is 2026-09-01, and we can't wait to have you join!")

    result = svc.answer_offer_question(db_session, candidate, conv, "U-ORG", "When do I start?", llm_call=llm_call)
    assert result["outcome"] == "answered"
    assert "2026-09-01" in result["answer"]

    event = db_session.query(ConversationEvent).filter(ConversationEvent.conversation_id == conv.id, ConversationEvent.event_type == "ai_message_sent").first()
    assert event is not None
    assert "2026-09-01" in event.event_data.get("body", "")


# ── TC-002/AC-2: benefits question uses FAQ content ───────────────────

def test_benefits_question_uses_tenant_faq_entry_when_present(db_session, seeded):
    candidate, conv, offer = seeded
    db_session.add(OfferFAQEntry(tenant_id="U-ORG", topic="BENEFITS", answer_text="Custom tenant benefits text mentioning dental coverage."))
    db_session.commit()

    captured_prompt = {}
    def llm_call(prompt):
        captured_prompt["value"] = prompt
        return "We offer dental coverage as part of your benefits package."

    result = svc.answer_offer_question(db_session, candidate, conv, "U-ORG", "What benefits do I get?", llm_call=llm_call)
    assert result["outcome"] == "answered"
    assert "dental coverage" in captured_prompt["value"]


def test_leave_policy_question_falls_back_to_default_content(db_session, seeded):
    candidate, conv, offer = seeded
    captured_prompt = {}

    def llm_call(prompt):
        captured_prompt["value"] = prompt
        return "You'll accrue 18 days of paid leave per year."

    result = svc.answer_offer_question(db_session, candidate, conv, "U-ORG", "What is the leave policy?", llm_call=llm_call)
    assert result["outcome"] == "answered"
    assert "18 days" in captured_prompt["value"]


# ── TC-003/AC-3/BR-01: negotiation escalates, never answered ──────────

def test_negotiation_question_escalates_and_notifies_recruiter(db_session, seeded):
    candidate, conv, offer = seeded

    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    client = Client(tenant_id=tenant.id, company_name="Acme")
    db_session.add(client)
    db_session.commit()
    demand = Demand(tenant_id=tenant.id, client_id=client.id, job_title="Sr. Dev", required_skills="[]", min_experience_years=5.0, work_location="REMOTE", status="OPEN")
    db_session.add(demand)
    db_session.commit()
    submission = Submission(tenant_id=tenant.id, demand_id=demand.id, client_id=client.id, candidate_id="C-1", submitted_by_user_id="U-RECRUITER", status="OFFER_EXTENDED")
    db_session.add(submission)
    db_session.commit()

    called = {"llm": False}
    def _boom(prompt):
        called["llm"] = True
        return "should never be called"

    result = svc.answer_offer_question(db_session, candidate, conv, "U-ORG", "Can I negotiate a higher salary?", llm_call=_boom)
    assert result["outcome"] == "escalated"
    assert called["llm"] is False  # BR-01: never even attempts to answer

    db_session.refresh(conv)
    assert conv.escalation_state == "escalated"
    assert conv.owner_type == "hr_user"

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1


# ── BR-02: implausible/generic answer -> escalate instead ─────────────

def test_generic_non_specific_answer_escalates_instead(db_session, seeded):
    candidate, conv, offer = seeded
    llm_call = _fake_llm("Your details will be communicated soon.")  # no real offer facts referenced

    result = svc.answer_offer_question(db_session, candidate, conv, "U-ORG", "When do I start?", llm_call=llm_call)
    assert result["outcome"] == "escalated"
    assert result["answer"] == svc.SAFE_FALLBACK_MESSAGE


# ── AC-5: LLM failure -> safe fallback + escalate ─────────────────────

def test_llm_failure_sends_safe_fallback_and_escalates(db_session, seeded):
    candidate, conv, offer = seeded

    def _boom(prompt):
        raise RuntimeError("simulated Gemini outage")

    result = svc.answer_offer_question(db_session, candidate, conv, "U-ORG", "When do I start?", llm_call=_boom)  # should not raise
    assert result["outcome"] == "escalated"
    assert result["answer"] == svc.SAFE_FALLBACK_MESSAGE

    db_session.refresh(conv)
    assert conv.escalation_state == "escalated"
