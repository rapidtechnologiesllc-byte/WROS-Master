"""DB-backed tests for the autonomous LinkedIn enrichment handler (fake sources, no network)."""
import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.candidate import Candidate, CandidateEducationForm, CandidateExperienceForm
from app.models.candidate_intelligence import CandidateIntelligenceProfile
from app.models.candidate_rejection import CandidateRejection
from app.models.consent import ConsentRecord
from app.models.tenant import Tenant
from app.models.thunder_email import ThunderCadenceState
from app.models.linkedin_candidate_pipeline import LinkedInCandidatePipeline, LinkedInPipelineStatus
from app.services.candidate_contact_policy import is_contactable
from app.services.linkedin_pipeline_task_service import name_from_slug, placeholder_email
from app.services.message_handlers.enrich_linkedin_candidate_handler import (
    EnrichLinkedInCandidateHandler, MAX_ATTEMPTS,
)
from app.services.talent_intelligence.service import EnrichmentResult, Sources

ENQUEUE = "app.services.message_queue_service.MessageQueueService.enqueue"


def _result(contact=None, name="Ankurjit Singh"):
    profile = {
        "full_name": {"value": name, "source": "search_snippet", "confidence": 0.9},
        "headline": {"value": "Senior Software Engineer", "source": "search_snippet", "confidence": 0.9},
        "current_company": {"value": "Acme Corp", "source": "search_snippet", "confidence": 0.9},
        "education": {"value": "IIT Delhi", "source": "search_snippet", "confidence": 0.9},
        "location": {"value": "Bengaluru", "source": "search_snippet", "confidence": 0.9},
    }
    return EnrichmentResult(
        profile=profile, identity_score=1.0 if contact else 0.4, passive_score=0.7,
        contact_email=contact, contact_source="personal_site:https://ankur.dev" if contact else None,
        found_linkedin_snippet=True,
    )


@pytest.fixture
def pipeline(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    slug = f"ankurjit-singh-{uuid.uuid4().hex[:6]}"
    first, last = name_from_slug(slug)
    candidate = Candidate(
        candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidateEmail=placeholder_email(slug),
        candidatePassword="hashed", candidateFirstName=first, candidateLastName=last,
        linkedin_url=f"https://www.linkedin.com/in/{slug}", thunder_enabled=False,
    )
    item = LinkedInCandidatePipeline(
        linkedin_url=f"https://www.linkedin.com/in/{slug}", linkedin_profile_slug=slug,
        status=LinkedInPipelineStatus.PENDING_CONNECTION, created_by_user_id="tester",
        candidate_id=candidate.candidateID,
    )
    db.add_all([candidate, item])
    db.commit()
    return SimpleNamespace(item=item, candidate=candidate)


def _run(db, pipeline_id, result, attempt=0):
    message = SimpleNamespace(id="msg-1", payload={"pipeline_id": str(pipeline_id), "tenant_id": 1, "attempt": attempt})
    with patch("app.services.message_handlers.enrich_linkedin_candidate_handler.enrich", return_value=result), \
         patch(ENQUEUE, return_value={"message_id": "m", "task_id": "t"}) as enqueue:
        outcome = EnrichLinkedInCandidateHandler.process(
            message, db, sources=Sources(search=[object()]), allow=lambda s: True,
        )
    return outcome, enqueue


def test_confirmed_contact_imports_to_thunder_and_starts_email_cadence(db, pipeline):
    outcome, enqueue = _run(db, pipeline.item.id, _result(contact="hello@ankur.dev"))

    db.refresh(pipeline.candidate)
    db.refresh(pipeline.item)
    assert outcome["status"] == "IMPORTED"
    assert pipeline.candidate.candidateEmail == "hello@ankur.dev"
    assert pipeline.candidate.thunder_enabled is True
    assert pipeline.candidate.candidateFirstName == "Ankurjit"
    assert pipeline.candidate.candidateJobTitle == "Senior Software Engineer"
    assert pipeline.item.status == LinkedInPipelineStatus.IMPORTED_TO_THUNDER
    assert db.query(CandidateExperienceForm).filter_by(candidateID=pipeline.candidate.candidateID).one().company_name == "Acme Corp"
    assert db.query(CandidateEducationForm).filter_by(candidateID=pipeline.candidate.candidateID).one().education_institute == "IIT Delhi"
    sent = [c.kwargs for c in enqueue.call_args_list if c.kwargs.get("task_name") == "thunder_send_email"]
    assert len(sent) == 1 and sent[0]["data"]["step"] == "1"
    state = db.query(ThunderCadenceState).filter_by(candidate_id=pipeline.candidate.candidateID).one()
    assert (state.stage, state.next_step) == ("ACTIVE", "1")
    assert is_contactable(db, pipeline.candidate) == (True, "ok")
    # Enrichment never invents consent
    assert db.query(ConsentRecord).filter_by(subject_id=pipeline.candidate.candidateID).count() == 0


def test_no_contact_keeps_placeholder_thunder_off_and_reschedules(db, pipeline):
    outcome, enqueue = _run(db, pipeline.item.id, _result(contact=None))

    db.refresh(pipeline.candidate)
    assert outcome["status"] == "NO_CONTACT"
    assert pipeline.candidate.thunder_enabled is False
    assert pipeline.candidate.candidateEmail.endswith("@linkedin-pending.blitzenx.com")
    assert pipeline.candidate.candidateCurrentLocation == "Bengaluru"  # profile data still captured
    assert is_contactable(db, pipeline.candidate)[0] is False
    retry = [c.kwargs for c in enqueue.call_args_list if c.kwargs.get("task_name") == "enrich_linkedin_candidate"]
    assert len(retry) == 1 and retry[0]["data"]["attempt"] == 1 and retry[0]["delay_seconds"] >= 6 * 3600 - 60


def test_last_attempt_without_contact_is_exhausted(db, pipeline):
    outcome, enqueue = _run(db, pipeline.item.id, _result(contact=None), attempt=MAX_ATTEMPTS - 1)
    assert outcome["status"] == "EXHAUSTED"
    assert not [c for c in enqueue.call_args_list if c.kwargs.get("task_name") == "enrich_linkedin_candidate"]


def test_email_owned_by_another_candidate_is_duplicate_contact(db, pipeline):
    db.add(Candidate(candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidateEmail="hello@ankur.dev", candidatePassword="h"))
    db.commit()
    outcome, _ = _run(db, pipeline.item.id, _result(contact="hello@ankur.dev"))
    db.refresh(pipeline.candidate)
    assert outcome["status"] == "DUPLICATE_CONTACT"
    assert pipeline.candidate.thunder_enabled is False


def test_rejection_cooldown_blocks_autonomous_import(db, pipeline):
    db.add(CandidateRejection(
        candidate_id=pipeline.candidate.candidateID, rejection_reason="test",
        rejected_at=datetime.utcnow() - timedelta(days=10), tenant_id=1,
    ))
    db.commit()
    outcome, _ = _run(db, pipeline.item.id, _result(contact="hello@ankur.dev"))
    db.refresh(pipeline.candidate)
    assert outcome["status"] == "NO_CONTACT"
    assert pipeline.candidate.thunder_enabled is False
    profile = db.query(CandidateIntelligenceProfile).filter_by(pipeline_id=str(pipeline.item.id)).one()
    assert profile.next_attempt_at > datetime.utcnow() + timedelta(days=79)


def test_second_run_after_import_is_a_noop(db, pipeline):
    _run(db, pipeline.item.id, _result(contact="hello@ankur.dev"))
    outcome, enqueue = _run(db, pipeline.item.id, _result(contact="other@ankur.dev"))
    db.refresh(pipeline.candidate)
    assert outcome["status"] == "noop"
    assert pipeline.candidate.candidateEmail == "hello@ankur.dev"
    enqueue.assert_not_called()


def test_candidate_not_created_yet_is_retryable(db, pipeline):
    pipeline.item.candidate_id = None
    db.commit()
    with pytest.raises(RuntimeError):
        _run(db, pipeline.item.id, _result(contact="hello@ankur.dev"))


def test_unknown_pipeline_is_non_retryable(db):
    with pytest.raises(ValueError):
        _run(db, uuid.uuid4(), _result())


def test_placeholder_candidate_is_never_contactable(db, pipeline):
    pipeline.candidate.thunder_enabled = True
    db.commit()
    assert is_contactable(db, pipeline.candidate) == (False, "no real contact email")


def test_daily_search_budget_is_enforced(db):
    from app.services.talent_intelligence.budget import consume
    source = f"test_src_{uuid.uuid4().hex[:6]}"
    assert [consume(db, source, 2) for _ in range(3)] == [True, True, False]
