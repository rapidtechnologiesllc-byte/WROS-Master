"""Why Thunder read a reply the way it did, and the Messages tab showing it.

The opt-out rule reads only the candidate's own words (never our quoted footer, which says
"we will stop emailing you"), stores the words it matched, and the candidate's thread lists
Thunder's emails, the replies and any opt-out with its source. Fake Graph + fake LLM, no network.
"""
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.consent import ConsentRecord
from app.models.thunder_email import ThunderEmailMessage
from app.models.user import Users
from app.services.thunder_delivery_outcome_handler import ThunderDeliveryOutcomeHandler
from app.services.thunder_mail import cadence_service as cadence
from app.services.thunder_mail.reply_classifier import OPT_OUT_PATTERN, candidate_words, classify_reply
from app.services.thunder_mail.seed_variants import FOOTER, SEED_VARIANTS
from app.models.thunder_email import ThunderOutreachVariant
from tests.hiring_fixtures import full_access_role
from tests.test_thunder_email_loop import FakeMailbox, _inbound, _send, db, world  # noqa: F401 (fixtures)

FOOTER_TEXT = cadence.plain_text(FOOTER.format(source_note=""))


def _llm(intent, seen=None):
    def call(*args, **kwargs):
        if seen is not None:
            seen.append(" ".join(str(a) for a in args))
        return f'{{"intent": "{intent}", "confidence": 0.8}}'
    return call


def _quoted(reply, our_text):
    quoted = "\n".join(f"> {line}" for line in our_text.splitlines())
    return f"{reply}\n\nOn Mon, 27 Oct 2026 at 10:00, Helpdesk <helpdesk_hrms@blitzenx.com> wrote:\n{quoted}"


# ---- the rule never reads our own copy ----------------------------------------------------------

def test_our_footer_alone_would_trip_the_rule():
    # the reason for stripping: our footer contains an opt-out phrase
    assert OPT_OUT_PATTERN.search(FOOTER_TEXT).group(0) == "stop emailing"


@pytest.mark.parametrize("body", [
    _quoted("Sounds good, let's talk tomorrow.", FOOTER_TEXT),            # Gmail-style quote
    "Sounds good, let's talk tomorrow.\n\n" + FOOTER_TEXT,                 # uniqueBody kept our text, no header
    "Sounds good, let's talk tomorrow.\n\nYou’re hearing from us because your professional profile is in "
    "the BlitzenX talent network. Reply “remove” and we will\nstop emailing you and delete your details.",
    "Sounds good, let's talk tomorrow.\n\nFrom: Helpdesk <helpdesk_hrms@blitzenx.com>\nSent: Monday\n" + FOOTER_TEXT,
    "Sounds good, let's talk tomorrow.\n-----Original Message-----\n" + FOOTER_TEXT,
])
def test_a_reply_quoting_our_footer_is_not_an_opt_out(db, body):
    seen = []
    result = classify_reply(db, 1, None, "Re: a quick question", body, llm_call=_llm("INTERESTED", seen))
    assert result.intent == "INTERESTED" and result.source == "llm"
    assert "stop emailing" not in seen[0]  # the LLM is not shown our copy either


def test_no_seeded_email_trips_the_rule_even_when_echoed_whole(db, world):
    variants = db.query(ThunderOutreachVariant).all()
    assert len(variants) >= len(SEED_VARIANTS)
    for variant in variants:
        candidate = SimpleNamespace(candidateFirstName="Neha")
        subject, body = cadence.render(variant, candidate, None, {"source_note": " (via LinkedIn)"})
        result = classify_reply(db, 1, None, f"Re: {subject}", cadence.plain_text(body),
                                llm_call=_llm("OTHER"))
        assert result.intent != "UNSUBSCRIBE", variant.key


def test_sentences_of_the_emails_we_sent_are_not_the_candidates():
    ours = "Hi Neha,\nPlease tell us if you would rather we stop contacting you about roles.\nRegards,\nThunder"
    assert candidate_words("Yes, call me.\n" + ours, [ours]) == "Yes, call me."


@pytest.mark.parametrize("body,evidence", [
    (_quoted("Please stop emailing me.", FOOTER_TEXT), "stop emailing"),
    (_quoted("remove", FOOTER_TEXT), "remove"),
    ("Unsubscribe", "Unsubscribe"),
])
def test_a_real_opt_out_still_wins_and_says_which_words(db, body, evidence):
    result = classify_reply(db, 1, None, "Re: a quick question", body, llm_call=_llm("INTERESTED"))
    assert (result.intent, result.source, result.matched_text) == ("UNSUBSCRIBE", "rule", evidence)


def test_the_inbound_handler_stores_the_evidence_and_ignores_the_quoted_footer(db, world):
    mailbox = FakeMailbox()
    _send(db, world, "1", mailbox)
    sent = db.query(ThunderEmailMessage).filter_by(candidate_id=world.candidate.candidateID, direction="OUT").one()
    assert "stop emailing you" in sent.body_text and "<p>" not in sent.body_text  # a copy for staff

    result, _, row = _inbound(db, world, _quoted("Interested, call me after 6.", sent.body_text),
                              llm=_llm("INTERESTED"))
    db.refresh(row)
    assert result["intent"] == "INTERESTED" and world.state.stage == "HANDOFF"
    # (the LLM's log write cannot see this test's uncommitted candidate: the keyword fallback reads it)
    assert row.intent_source in ("llm", "keyword") and row.intent_evidence in (None, "Interested")


# ---- the Messages tab thread --------------------------------------------------------------------

@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.main import app

    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _headers(db):
    from app.core.security import create_access_token

    role = full_access_role(db)
    user = Users(UserID=f"U-{uuid.uuid4().hex[:8]}", UserName="Avinash", UserEmail=f"{uuid.uuid4().hex[:8]}@blitzenx.com",
                 UserPassword="x", UserRole="x", tenant_id=1, role_template_id=role.id, password_reset_required=False)
    db.add(user)
    db.commit()
    return {"Authorization": "Bearer " + create_access_token(
        {"sub": user.UserID, "type": "user", "tenant_id": 1, "role_template_id": role.id})}


def _thread(client, db, world):
    response = client.get(f"/api/v1/ai-agent/conversations/{world.candidate.candidateID}", headers=_headers(db))
    assert response.status_code == 200, response.text
    return response.json()["thunder"]


def test_the_thread_shows_thunders_email_the_reply_and_why_thunder_stopped(client, db, world):
    _send(db, world, "1", FakeMailbox())
    _, _, row = _inbound(db, world, _quoted("Please stop emailing me.", FOOTER_TEXT), llm=_llm("INTERESTED"))

    thunder = _thread(client, db, world)
    assert thunder["stage"] == "STOPPED" and thunder["stop_reason"] == "candidate unsubscribe"
    kinds = [(i["kind"], i.get("direction")) for i in thunder["items"]]
    assert kinds[:2] == [("email", "OUT"), ("email", "IN")] and ("opt_out", None) in kinds
    out, reply = thunder["items"][0], thunder["items"][1]
    assert out["step"] == "1" and "stop emailing you" in out["body"] and out["subject"]
    assert reply["id"] == row.id == thunder["stopped_by_item_id"]
    assert reply["body"].startswith("Please stop emailing me.")
    assert (reply["intent"], reply["intent_source"], reply["intent_confidence"], reply["intent_evidence"]) == \
        ("UNSUBSCRIBE", "rule", 1.0, "stop emailing")
    opt_out = next(i for i in thunder["items"] if i["kind"] == "opt_out")
    assert opt_out["source"] == "the candidate's email reply"


def test_a_candidate_without_thunder_mail_gets_an_empty_thunder_thread(client, db, world):
    thunder = _thread(client, db, world)
    assert thunder["items"] == [] and thunder["stopped_by_item_id"] is None and thunder["stage"] == "ACTIVE"


@pytest.mark.parametrize("event,stop_reason,source", [
    ("unsubscribe", "sendgrid unsubscribed", "sendgrid unsubscribe link"),
    ("spamreport", "sendgrid complained", "sendgrid spam complaint"),
])
def test_a_provider_unsubscribe_stops_thunder_and_names_its_source(client, db, world, event, stop_reason, source):
    with patch("app.services.thunder_delivery_outcome_handler.ThunderLearningIntegration.record_engagement_outcome",
               return_value={"status": "recorded"}):
        result = ThunderDeliveryOutcomeHandler.handle_delivery_event(
            db, "1", world.candidate.candidateID, "conv-1", event,
            {"channel": "email", "provider": "sendgrid", "timestamp": datetime.utcnow().isoformat()})
    assert result == {"status": "recorded"}
    db.refresh(world.state)
    db.refresh(world.candidate)
    assert world.state.stage == "STOPPED" and world.state.stop_reason == stop_reason
    assert world.state.next_action_at is None and world.candidate.thunder_enabled is False
    consent = db.query(ConsentRecord).filter_by(subject_id=world.candidate.candidateID,
                                                consent_type="email_outreach").one()
    assert consent.consent_given is False and consent.captured_by.startswith("provider_")

    thunder = _thread(client, db, world)
    stopper = next(i for i in thunder["items"] if i["id"] == thunder["stopped_by_item_id"])
    assert (stopper["kind"], stopper["source"]) == ("opt_out", source)


def test_a_provider_open_event_changes_nothing(db, world):
    with patch("app.services.thunder_delivery_outcome_handler.ThunderLearningIntegration.record_engagement_outcome",
               return_value={"status": "recorded"}):
        ThunderDeliveryOutcomeHandler.handle_delivery_event(
            db, "1", world.candidate.candidateID, "conv-1", "opened", {"channel": "email", "provider": "sendgrid"})
    db.refresh(world.state)
    assert world.state.stage == "ACTIVE"
    assert db.query(ConsentRecord).filter_by(subject_id=world.candidate.candidateID).count() == 0


# ---- regression: an iPhone reply whose uniqueBody kept our whole email (prod, 2026-10-30) -------

IPHONE_REPLY = """Dear HR team,
Please see the details below:

  *   Years of Experience - 22+ years
  *   Notice Period (in days) - 2/3 weeks

Best Regards,
-A Candidate
Sent from my iPhone

On Oct 30, 2026, at 3:37 PM, Helpdesk_HRMS <helpdesk_hrms@blitzenx.com> wrote:

\ufeff

Hi A,

Following up on our conversation: we are still missing a few details to put your profile forward.

Regards,
the BlitzenX talent team

________________________________

You're hearing from us because your professional profile is in the BlitzenX talent network. Reply "remove" and we will stop emailing you and delete your details.

________________________________

This email and any attachments are confidential. If received in error, please notify the sender and delete this message."""


def test_a_details_reply_quoting_our_whole_email_is_not_an_opt_out(db, world):
    result, _, row = _inbound(db, world, IPHONE_REPLY, subject="Re: Director | Technical Client Partner | BlitzenX")
    db.refresh(row)
    assert result["intent"] != "UNSUBSCRIBE" and row.intent_source != "rule"
    assert world.state.stage != "STOPPED"


# ---- Response Rate reads the same emails as the Thunder card -------------------------------------

def test_response_rate_counts_thunder_emails_and_ignores_automatic_replies(db, world):
    from app.services.engagement_metrics_service import calculate_engagement_health

    _send(db, world, "1", FakeMailbox())
    _inbound(db, world, "Can you share the JD?")
    _inbound(db, world, "I am out of office", subject="Automatic reply: a quick question")
    metrics = calculate_engagement_health(db, world.candidate.candidateID, "1")
    assert metrics["outcome"] == "calculated"
    # 1 sent email; 1 real reply (the out-of-office does not count)
    assert metrics["response_rate"] == 100 and metrics["total_messages_exchanged"] == 2
    assert metrics["last_inbound_at"] is not None


def test_no_messages_at_all_has_no_metrics(db, world):
    from app.services.engagement_metrics_service import calculate_engagement_health

    assert calculate_engagement_health(db, world.candidate.candidateID, "1") == {"outcome": "not_found"}
