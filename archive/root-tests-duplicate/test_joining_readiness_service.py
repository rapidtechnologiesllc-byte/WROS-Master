"""
S-058/HRMS-0458 -- Joining Readiness Score.

Real architecture under test (see joining_readiness_service module
docstring): no offers table -- offer_id FKs the real OfferLetter.id;
"PREBOARDING" maps to OfferLetter.offer_status=='Accepted' (no
fictional state); Component 2's e-signature condition is vacuously
satisfied (no e-signature mechanism exists in this codebase);
Component 4 (responsiveness) is computed from the real OFFER_ACCEPTED
event + candidate_reply history; Component 5 (background check) is a
real proxy via the BACKGROUND_CHECK_CONSENT document's status, never a
fabricated CLEARED/FAILED state; BR-01's immediate alert only fires on
a real crossing below 50, not every recompute.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.candidate import Candidate
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.models.candidate_joining_score import CandidateJoiningScore
from app.models.notification import Notification
from app.models.offer_letter import OfferLetter
from app.models.preboarding_document import PreboardingDocument
from app.models.submission import Submission
from app.models.user import Users

import app.services.joining_readiness_service as svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Users.__table__, Candidate.__table__, CandidateConversation.__table__, ConversationEvent.__table__,
        OfferLetter.__table__, PreboardingDocument.__table__, CandidateJoiningScore.__table__, Notification.__table__,
        Submission.__table__,
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
    # Notification.tenant_id (Integer, FK tenants.id) matches Users.tenant_id
    # (also Integer, FK tenants.id) -- distinct from the "U-ORG"-style string
    # tenant_id used by candidate_ai.py/CandidateJoiningScore (that one maps
    # to users.UserID, per this codebase's own documented dual convention).
    hr_user = Users(UserID="U-HR", UserRole="HR Manager", UserEmail="hr@blitzenx.com", UserPassword="h", tenant_id=None)
    db_session.add(hr_user)
    db_session.commit()

    candidate = Candidate(candidateID="C-1", candidateEmail="c1@example.com", candidatePassword="h", candidateFirstName="Priya", candidateMobile="+919876543210")
    db_session.add(candidate)
    db_session.commit()

    conv = CandidateConversation(tenant_id="U-ORG", candidate_id="C-1", status="open", owner_type="ai_agent", owner_id="Thunder", escalation_state="none", channel_preference="whatsapp")
    db_session.add(conv)
    db_session.commit()

    submission = Submission(tenant_id=None, demand_id="D-1", client_id="CL-1", candidate_id="C-1", submitted_by_user_id="U-HR", status="OFFER_EXTENDED")
    db_session.add(submission)
    db_session.commit()

    offer = OfferLetter(candidate_id="C-1", position="Sr. Guidewire Developer", salary="24 LPA", joining_date=date.today() + timedelta(days=10), offer_expire_date=date.today() + timedelta(days=20), offer_status="Accepted", approval_status="Approved", created_by="U-HR")
    db_session.add(offer)
    db_session.commit()

    return candidate, conv, offer, submission


def _add_docs(db, offer_id, statuses):
    from app.services.document_collection_service import REQUIRED_DOCUMENTS
    docs = []
    for (doc_type, label, india_only), status in zip(REQUIRED_DOCUMENTS, statuses):
        doc = PreboardingDocument(tenant_id="U-ORG", candidate_id="C-1", offer_id=offer_id, document_type=doc_type, document_label=label, status=status)
        db.add(doc)
        docs.append(doc)
    db.commit()
    return docs


def _add_accepted_event(db, conv, when):
    db.add(ConversationEvent(conversation_id=conv.id, event_type="OFFER_ACCEPTED", event_data={}, triggered_by="candidate", created_at=when))
    db.commit()


# ── TC-001/AC-2: high readiness ────────────────────────────────────────

def test_high_readiness_all_docs_responsive(db_session, seeded):
    candidate, conv, offer, submission = seeded
    _add_docs(db_session, offer.id, ["RECEIVED"] * 7)
    accepted_at = datetime.utcnow() - timedelta(hours=20)
    _add_accepted_event(db_session, conv, accepted_at)
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={}, triggered_by="candidate", created_at=accepted_at + timedelta(hours=10)))
    db_session.commit()

    result = svc.calculate_joining_readiness(db_session, "C-1", offer.id, "U-ORG")
    assert result["readiness_score"] >= 75
    assert result["score_breakdown"]["documents"] == 40
    assert result["score_breakdown"]["responsiveness"] == 15


# ── TC-002/AC-3: low readiness ─────────────────────────────────────────

def test_low_readiness_no_docs_no_response(db_session, seeded):
    candidate, conv, offer, submission = seeded
    offer.joining_date = date.today() + timedelta(days=5)  # 3-7 day bucket = 8pts, not the imminent 15
    db_session.commit()
    _add_accepted_event(db_session, conv, datetime.utcnow() - timedelta(hours=120))  # >96h, no reply

    result = svc.calculate_joining_readiness(db_session, "C-1", offer.id, "U-ORG")
    assert result["readiness_score"] < 40
    assert result["score_breakdown"]["documents"] == 0
    assert result["score_breakdown"]["responsiveness"] == 0


def test_candidate_or_offer_not_found(db_session, seeded):
    result = svc.calculate_joining_readiness(db_session, "NOPE", 99999, "U-ORG")
    assert result["outcome"] == "not_found"


# ── Component 1: documents (40%) ──────────────────────────────────────

def test_document_component_scales_with_received_ratio(db_session, seeded):
    candidate, conv, offer, submission = seeded
    _add_docs(db_session, offer.id, ["RECEIVED"] * 3 + ["PENDING"] * 4)  # 3/7 received
    pts = svc._document_component(db_session, "U-ORG", "C-1", offer.id)
    assert pts == round((3 / 7) * 40)


def test_document_component_zero_when_none_created(db_session, seeded):
    candidate, conv, offer, submission = seeded
    pts = svc._document_component(db_session, "U-ORG", "C-1", offer.id)
    assert pts == 0


def test_cancelled_documents_excluded_from_denominator(db_session, seeded):
    candidate, conv, offer, submission = seeded
    _add_docs(db_session, offer.id, ["RECEIVED"] * 3 + ["CANCELLED"] * 4)
    pts = svc._document_component(db_session, "U-ORG", "C-1", offer.id)
    assert pts == 40  # 3/3 non-cancelled received


# ── Component 2: offer formality (20%) ─────────────────────────────────

def test_offer_formality_full_points_when_accepted_and_start_date_set(db_session, seeded):
    candidate, conv, offer, submission = seeded
    assert svc._offer_formality_component(offer) == 20


def test_offer_formality_partial_when_start_date_missing(db_session, seeded):
    # OfferLetter.joining_date is NOT NULL in the real schema -- this
    # branch is defensive-only. Exercise the pure function against a
    # transient (never-added-to-session) instance so no flush is
    # attempted against the NOT NULL column.
    transient_offer = OfferLetter(offer_status="Accepted", joining_date=None)
    assert svc._offer_formality_component(transient_offer) == 10


def test_offer_formality_zero_when_not_accepted(db_session, seeded):
    candidate, conv, offer, submission = seeded
    offer.offer_status = "Released"
    assert svc._offer_formality_component(offer) == 0


# ── Component 3: timeline (15%) -- the U-shaped curve ──────────────────

def test_timeline_component_matches_literal_buckets(db_session, seeded):
    candidate, conv, offer, submission = seeded
    cases = [
        (35, 15), (20, 12), (10, 10), (5, 8), (1, 15), (-2, 0),
    ]
    for days_away, expected in cases:
        offer.joining_date = date.today() + timedelta(days=days_away)
        assert svc._timeline_component(offer) == expected, f"days_away={days_away}"


# ── Component 4: responsiveness (15%) ───────────────────────────────────

def test_responsiveness_full_points_within_48h(db_session, seeded):
    candidate, conv, offer, submission = seeded
    accepted_at = datetime.utcnow() - timedelta(hours=60)
    _add_accepted_event(db_session, conv, accepted_at)
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={}, triggered_by="candidate", created_at=accepted_at + timedelta(hours=30)))
    db_session.commit()
    assert svc._responsiveness_component(db_session, conv) == 15


def test_responsiveness_partial_points_48_to_96h(db_session, seeded):
    candidate, conv, offer, submission = seeded
    accepted_at = datetime.utcnow() - timedelta(hours=120)
    _add_accepted_event(db_session, conv, accepted_at)
    db_session.add(ConversationEvent(conversation_id=conv.id, event_type="candidate_reply", event_data={}, triggered_by="candidate", created_at=accepted_at + timedelta(hours=70)))
    db_session.commit()
    assert svc._responsiveness_component(db_session, conv) == 10


def test_responsiveness_no_reply_yet_within_window_gets_benefit_of_doubt(db_session, seeded):
    candidate, conv, offer, submission = seeded
    _add_accepted_event(db_session, conv, datetime.utcnow() - timedelta(hours=10))  # no reply, but still within 48h
    assert svc._responsiveness_component(db_session, conv) == 15


def test_responsiveness_zero_with_no_acceptance_event(db_session, seeded):
    candidate, conv, offer, submission = seeded
    assert svc._responsiveness_component(db_session, conv) == 0


# ── Component 5: background check (10%, real proxy) ─────────────────────

def test_background_check_in_progress_when_consent_received(db_session, seeded):
    candidate, conv, offer, submission = seeded
    db_session.add(PreboardingDocument(tenant_id="U-ORG", candidate_id="C-1", offer_id=offer.id, document_type="BACKGROUND_CHECK_CONSENT", document_label="Consent", status="RECEIVED"))
    db_session.commit()
    assert svc._background_check_component(db_session, "U-ORG", "C-1", offer.id) == 5


def test_background_check_not_started_when_no_consent_doc(db_session, seeded):
    candidate, conv, offer, submission = seeded
    assert svc._background_check_component(db_session, "U-ORG", "C-1", offer.id) == 2


# ── BR-01: immediate alert on crossing below 50, only once ─────────────

def test_score_drop_below_50_notifies_recruiter_immediately(db_session, seeded):
    candidate, conv, offer, submission = seeded
    offer.joining_date = date.today() + timedelta(days=5)
    db_session.commit()
    _add_accepted_event(db_session, conv, datetime.utcnow() - timedelta(hours=120))

    result = svc.calculate_joining_readiness(db_session, "C-1", offer.id, "U-ORG")
    assert result["readiness_score"] < 50

    notifications = db_session.query(Notification).all()
    assert len(notifications) == 1
    assert str(result["readiness_score"]) in notifications[0].message


def test_repeated_low_score_does_not_renotify(db_session, seeded):
    candidate, conv, offer, submission = seeded
    offer.joining_date = date.today() + timedelta(days=5)
    db_session.commit()
    _add_accepted_event(db_session, conv, datetime.utcnow() - timedelta(hours=120))

    svc.calculate_joining_readiness(db_session, "C-1", offer.id, "U-ORG")
    svc.calculate_joining_readiness(db_session, "C-1", offer.id, "U-ORG")  # still low, should NOT re-notify

    assert db_session.query(Notification).count() == 1


def test_high_score_never_notifies(db_session, seeded):
    candidate, conv, offer, submission = seeded
    _add_docs(db_session, offer.id, ["RECEIVED"] * 7)
    _add_accepted_event(db_session, conv, datetime.utcnow() - timedelta(hours=1))

    svc.calculate_joining_readiness(db_session, "C-1", offer.id, "U-ORG")
    assert db_session.query(Notification).count() == 0


# ── Upsert behavior ──────────────────────────────────────────────────

def test_recalculation_upserts_not_duplicates(db_session, seeded):
    candidate, conv, offer, submission = seeded
    svc.calculate_joining_readiness(db_session, "C-1", offer.id, "U-ORG")
    svc.calculate_joining_readiness(db_session, "C-1", offer.id, "U-ORG")

    rows = db_session.query(CandidateJoiningScore).filter(CandidateJoiningScore.candidate_id == "C-1").all()
    assert len(rows) == 1


# ── TC-003/AC-5: job scores all Accepted offers ────────────────────────

def test_job_calculates_for_all_accepted_offers(db_session, seeded):
    candidate, conv, offer, submission = seeded
    result = svc.run_joining_readiness_job(db_session)
    assert result["calculated"] == 1


def test_job_skips_non_accepted_offers(db_session, seeded):
    candidate, conv, offer, submission = seeded
    offer.offer_status = "Released"
    db_session.commit()

    result = svc.run_joining_readiness_job(db_session)
    assert result["calculated"] == 0
