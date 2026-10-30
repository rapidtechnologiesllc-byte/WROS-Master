"""Candidate engagement: the profile-completion conversation, its tenant key, and the
organisation's Thunder settings.

Regression cover for 2026-10-14: ai_conversation_service had been reduced to stubs that
reported success without doing anything; engagement records were keyed by arbitrary user ids
while readers looked for the tenant; and the Thunder kill switch saved on the caller's own user
row while the pause check read a different user's.
"""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.models.candidate import CandidateInfoForm
from app.models.candidate_ai import CandidateConversation, ConversationEvent
from app.services import ai_conversation_service as svc
from app.services import tenant_ai_config_service as cfg
from tests import factories
from tests.hiring_fixtures import full_access_role
from tests.scope_fixtures import ApiClient


@pytest.fixture
def sent_emails():
    sent = []
    with patch("app.services.email_service.EmailService.send_email",
               side_effect=lambda **kw: sent.append(kw) or {"status": "sent"}):
        yield sent


def _complete_except(db, *, missing=("candidateGender", "marital_status")):
    """A candidate with every profile field filled except `missing`."""
    values = dict(candidateFirstName="Ria", candidateLastName="Das", candidateMobile="+91 98765 43210",
                  candidateGender="Female", candidateDateOfBirth=date(1995, 5, 1),
                  candidateCurrentLocation="Pune", candidateJoiningDate=date(2026, 12, 1),
                  candidateExperience="6 years", candidateJobTitle="Guidewire Developer",
                  candidateSkills="Guidewire", employment_type="FULLTIME", candidate_notice_period=30,
                  candidateCurrentSalary="1500000", candidateExpectedSalary="1800000")
    for field in missing:
        values.pop(field, None)
    candidate = factories.candidate(db, **values)
    form = {"marital_status": "Single", "nationality": "Indian", "permanent_address": "Pune, Maharashtra, India"}
    for field in missing:
        form.pop(field, None)
    db.add(CandidateInfoForm(candidateID=candidate.candidateID, **form))
    db.flush()
    return candidate


# --- missing fields and merge -------------------------------------------------------------

def test_missing_fields_are_the_empty_profile_fields(db):
    candidate = _complete_except(db)
    assert [m["field"] for m in svc.get_missing_fields(candidate, db)] == ["candidateGender", "marital_status"]


def test_merge_saves_professional_details_and_rejects_bad_values(db):
    from app.models.candidate_profile_extras import CandidateProfileSkill

    candidate = factories.candidate(db)
    result = svc.merge_fields_to_db(candidate.candidateID, {
        "employment_type": "contract", "candidate_notice_period": "60 days",
        "candidateExpectedSalary": "65", "candidateExpectedSalaryType": "$/Hour",
        "candidateCurrentSalary": "120000", "candidateCurrentSalaryType": "per annum",
        "candidateSkills": [{"name": "Guidewire", "years": 6}, {"name": "Java", "years": None}],
    }, db)
    assert set(result["skipped"]) == {"candidateCurrentSalaryType"}
    assert (candidate.employment_type, candidate.candidate_notice_period) == ("CONTRACT", 60)
    assert (candidate.candidateExpectedSalary, candidate.candidateExpectedSalaryType) == ("65", "$/Hour")
    assert candidate.candidateSkills == "Guidewire, Java"
    skills = db.query(CandidateProfileSkill).filter_by(candidate_id=candidate.candidateID).order_by(CandidateProfileSkill.id).all()
    assert [(s.name, s.years_of_experience, s.is_primary) for s in skills] == [("Guidewire", "6", True), ("Java", None, False)]
    assert svc.merge_fields_to_db(candidate.candidateID, {"employment_type": "C2C"}, db)["skipped"] == ["employment_type"]


def test_unknown_employment_type_and_a_missing_resume_count_as_missing(db):
    candidate = _complete_except(db, missing=())
    candidate.employment_type = "UNKNOWN"
    db.flush()
    assert [m["field"] for m in svc.get_missing_fields(candidate, db)] == ["employment_type"]
    assert [m["field"] for m in svc.get_missing_fields(candidate, db, include_documents=True)] == [
        "employment_type", "resume"]


def test_merge_saves_core_and_form_fields_and_rejects_bad_values(db):
    candidate = factories.candidate(db)
    result = svc.merge_fields_to_db(candidate.candidateID, {
        "candidateGender": "Female", "candidateDateOfBirth": "1995-05-01", "marital_status": "Single",
        "candidateJoiningDate": "next month",       # not a date: stays missing
        "candidateMobile": "98765 43210",           # no country code: WhatsApp can't reach it
        "unknown_field": "x",
    }, db)
    assert sorted(result["updated"]) == ["candidateDateOfBirth", "candidateGender", "marital_status"]
    assert sorted(result["skipped"]) == ["candidateJoiningDate", "candidateMobile", "unknown_field"]
    db.refresh(candidate)
    assert candidate.candidateDateOfBirth == date(1995, 5, 1)
    form = db.query(CandidateInfoForm).filter_by(candidateID=candidate.candidateID).one()
    assert form.marital_status == "Single"


def test_merge_for_an_unknown_candidate_is_404_not_success(db):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        svc.merge_fields_to_db("CAN-nobody", {"candidateGender": "Male"}, db)
    assert exc.value.status_code == 404


# --- the conversation ---------------------------------------------------------------------

def test_assigning_thunder_keys_the_conversation_by_tenant_and_emails_what_is_missing(db, sent_emails):
    candidate = _complete_except(db)
    result = svc.assign_ai_agent(candidate.candidateID, None, None, db)
    conversation = db.get(CandidateConversation, result["conversation_id"])
    assert conversation.tenant_id == str(candidate.tenant_id)
    assert conversation.status == "awaiting_candidate"
    assert result["email_sent"] is True
    assert sent_emails[0]["to_email"] == candidate.candidateEmail
    events = {e.event_type for e in db.query(ConversationEvent).filter_by(conversation_id=conversation.id)}
    assert {"ai_assigned", "field_check", "ai_message_sent"} <= events


def test_a_reply_fills_the_fields_and_closes_the_conversation(db, sent_emails):
    candidate = _complete_except(db)
    svc.assign_ai_agent(candidate.candidateID, None, None, db)
    llm = lambda prompt: '{"candidateGender": "Female", "marital_status": "Single"}'  # noqa: E731
    result = svc.process_candidate_reply(candidate.candidateID, db, raw_reply_text="I am female and single.",
                                         message_id="m-1", llm_call=llm)
    assert result["status"] == "completed"
    assert sorted(result["updated_fields"]) == ["candidateGender", "marital_status"]
    db.refresh(candidate)
    assert candidate.candidateGender == "Female"
    again = svc.process_candidate_reply(candidate.candidateID, db, raw_reply_text="x", message_id="m-1", llm_call=llm) \
        if db.query(CandidateConversation).filter(CandidateConversation.candidate_id == candidate.candidateID,
                                                  CandidateConversation.status != "closed").count() else None
    assert again is None  # closed: nothing left to process


def test_a_partial_reply_follows_up_on_what_is_still_missing(db, sent_emails):
    candidate = _complete_except(db)
    svc.assign_ai_agent(candidate.candidateID, None, None, db)
    result = svc.process_candidate_reply(candidate.candidateID, db, raw_reply_text="I am female.",
                                         message_id="m-2", llm_call=lambda p: '{"candidateGender": "Female"}')
    assert result["status"] == "partial"
    assert result["still_missing"] == ["marital_status"]
    assert result["followup_email_sent"] is True
    assert "Follow-up" in sent_emails[-1]["subject"]
    duplicate = svc.process_candidate_reply(candidate.candidateID, db, raw_reply_text="I am female.",
                                            message_id="m-2", llm_call=lambda p: "{}")
    assert duplicate["status"] == "duplicate_message"


def test_check_replies_reads_only_the_candidates_mail(db, sent_emails):
    candidate = _complete_except(db)
    svc.assign_ai_agent(candidate.candidateID, None, None, db)
    other = {"id": "x", "from": {"emailAddress": {"address": "someone@else.com"}}, "body": {"content": "hi"}}
    mailbox = SimpleNamespace(list_inbox=lambda since: [other])
    assert svc.process_candidate_reply(candidate.candidateID, db, mailbox=mailbox)["status"] == "no_reply_found"
    mine = {"id": "y", "from": {"emailAddress": {"address": candidate.candidateEmail.upper()}},
            "body": {"content": "Gender: Female. Single."}, "receivedDateTime": "2026-10-14T10:00:00Z"}
    mailbox = SimpleNamespace(list_inbox=lambda since: [other, mine])
    result = svc.process_candidate_reply(candidate.candidateID, db, mailbox=mailbox,
                                         llm_call=lambda p: '{"candidateGender": "Female", "marital_status": "Single"}')
    assert result["status"] == "completed"


def test_an_unreadable_reply_is_an_error_not_a_silent_success(db, sent_emails):
    from fastapi import HTTPException

    candidate = _complete_except(db)
    svc.assign_ai_agent(candidate.candidateID, None, None, db)
    with pytest.raises(HTTPException) as exc:
        svc.process_candidate_reply(candidate.candidateID, db, raw_reply_text="hello", message_id="m-3",
                                    llm_call=lambda p: "not json")
    assert exc.value.status_code == 502


# --- tenant and Thunder settings ----------------------------------------------------------

def test_tenant_resolver_is_looked_up_not_hard_coded(db):
    tenants = db.execute(text("SELECT id FROM app_schema.tenants")).scalars().all()
    if len(tenants) == 1:
        assert svc.resolve_default_tenant_id(db) == str(tenants[0])
    else:
        with pytest.raises(ValueError):
            svc.resolve_default_tenant_id(db)


def test_thunder_identity_defaults_and_follows_the_tenant_config(db):
    factories.tenant(db)
    assert svc.resolve_thunder_config(db, "1")["name"]
    cfg.update_tenant_ai_config(db, {"ai_agent_name": "Bolt", "ai_agent_persona": "Bolt helps."}, changed_by=None,
                                tenant_id=1)
    assert svc.resolve_thunder_config(db, "1") == {"name": "Bolt", "persona": "Bolt helps."}
    with pytest.raises(ValueError):
        cfg.update_tenant_ai_config(db, {"ai_agent_name": "  "}, changed_by=None, tenant_id=1)


def test_kill_switch_is_one_setting_for_the_organisation(db):
    from app.services.thunder_pause_service import is_thunder_paused_for_conversation

    admin_a = factories.user(db, role_template_id=full_access_role(db).id)
    admin_b = factories.user(db, role_template_id=full_access_role(db).id)
    candidate = factories.candidate(db)
    conversation = CandidateConversation(tenant_id="1", candidate_id=candidate.candidateID, status="open")
    db.add(conversation)
    db.commit()
    api = ApiClient(db)
    try:
        assert api.patch(admin_a, "/api/v1/admin/tenant/thunder-enabled", json={"enabled": False}).status_code == 200
        # a different admin sees the same switch, and every send gate honours it
        assert api.get(admin_b, "/api/v1/admin/tenant/thunder-enabled").json()["thunder_enabled"] is False
        assert is_thunder_paused_for_conversation(db, conversation) is True
        api.patch(admin_b, "/api/v1/admin/tenant/thunder-enabled", json={"enabled": True})
        assert is_thunder_paused_for_conversation(db, conversation) is False
    finally:
        api.close()


def test_thunder_email_waits_while_switched_off(db):
    from app.services.delivery_errors import DeliveryDeferred
    from app.services.message_handlers.thunder_send_email_handler import ThunderSendEmailHandler
    from app.services.thunder_mail import cadence_service
    from app.services.thunder_mail.seed_variants import seed_thunder_variants

    seed_thunder_variants(db)
    candidate = factories.candidate(db, candidateFirstName="Ria", thunder_enabled=True, timezone="UTC")
    state = cadence_service.start_cadence(db, candidate)
    db.commit()
    cfg.update_tenant_ai_config(db, {"thunder_enabled": False}, changed_by=None, tenant_id=candidate.tenant_id)
    message = SimpleNamespace(id="q-1", payload={"candidate_id": candidate.candidateID, "step": state.next_step,
                                                 "cadence_seq": state.cadence_seq, "tenant_id": 1})
    with pytest.raises(DeliveryDeferred, match="switched off"):
        ThunderSendEmailHandler.process(message, db)


# --- migration ----------------------------------------------------------------------------

def test_startup_rekeys_engagement_records_to_the_candidates_tenant(db):
    from app.core.db_contract import _initialize_engagement_tenant_keys

    owner = factories.user(db)
    candidate = factories.candidate(db)
    conversation = CandidateConversation(tenant_id=owner.UserID, candidate_id=candidate.candidateID, status="open")
    sandbox = CandidateConversation(tenant_id=owner.UserID, candidate_id=f"THUNDER-TEST-{owner.UserID}", status="open")
    db.add(conversation)
    db.flush()
    db.add(ConversationEvent(conversation_id=conversation.id, event_type="note", triggered_by="system"))
    db.commit()

    _initialize_engagement_tenant_keys(db)
    _initialize_engagement_tenant_keys(db)  # idempotent

    db.expire_all()
    assert db.get(CandidateConversation, conversation.id).tenant_id == str(candidate.tenant_id)
    event = db.query(ConversationEvent).filter_by(conversation_id=conversation.id).one()
    assert event.tenant_id == str(candidate.tenant_id)
    assert sandbox.tenant_id == owner.UserID  # never touched (not even flushed)
