"""Thunder first engagement must survive its side steps (production 2026-10-24: a candidate added
by the CEO was never engaged). A learning lookup compared the text tenant column with the integer
tenant id, its error was swallowed with the transaction left aborted, every later statement failed,
and the email cadence was rolled back with it; the sweep then never queued the candidate again."""
import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.channel_queue import ChannelQueueItem
from app.models.learning_events import SegmentLearningProfile
from app.models.tenant import Tenant
from app.models.thunder_email import ThunderCadenceState
from app.services import thunder_engagement_sweep as sweep
from app.services.message_handlers.thunder_engagement_handler import ThunderEngagementHandler
from app.services.thunder_learning_integration import ThunderLearningIntegration

ENQUEUE = "app.services.message_queue_service.MessageQueueService.enqueue"


def uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    if session.query(Tenant).filter_by(id=1).first() is None:
        session.add(Tenant(id=1, name="BlitzenX"))
        session.flush()
    yield session
    session.close()
    outer.rollback()
    connection.close()


def candidate(db):
    c = Candidate(candidateID=f"CAN-{uid()}", candidateFirstName="Neha", candidateLastName="S",
                  candidateEmail=f"{uid()}@candidate.example.com", candidatePassword="x", tenant_id=1,
                  candidateMobile="+919876543210", candidateCurrentLocation="Bengaluru", thunder_enabled=True)
    db.add(c)
    db.commit()
    return c


def test_the_learning_lookup_works_with_the_integer_tenant_and_never_aborts_the_transaction(db):
    c = candidate(db)
    confidence = ThunderLearningIntegration.get_outreach_confidence(db=db, candidate=c, channel="whatsapp")
    assert 0.0 <= confidence <= 1.0
    assert db.query(SegmentLearningProfile).filter_by(tenant_id="1", module="thunder").count() >= 1
    # the production failure (integer compared with the text column) now undoes only itself:
    # the caller falls back to the baseline and its transaction keeps working
    with patch("app.services.learning_event_collector._tenant_key", side_effect=lambda tenant_id: tenant_id):
        assert ThunderLearningIntegration.get_outreach_confidence(db=db, candidate=c, channel="email") == 0.5
    assert db.query(Candidate).filter_by(candidateID=c.candidateID).one()


def test_a_whatsapp_failure_never_undoes_the_email_cadence(db):
    c = candidate(db)
    message = SimpleNamespace(id=f"q-{uid()}", payload={"candidate_id": c.candidateID}, retry_count=0)
    with patch(ENQUEUE, return_value={"message_id": "x", "task_id": "x"}) as enqueue, \
         patch("app.services.thunder_service.has_active_consent", return_value=True), \
         patch("app.services.whatsapp_routing_service.resolve_outbound_whatsapp_number", return_value="+1555"), \
         patch("app.services.delivery_factory.whatsapp_delivery_ready", return_value=True), \
         patch("app.services.thunder_service.send_thunder_message", side_effect=RuntimeError("WhatsApp down")):
        with pytest.raises(RuntimeError, match="email cadence already started"):
            ThunderEngagementHandler.process(message, db)
    state = db.query(ThunderCadenceState).filter_by(candidate_id=c.candidateID).one()
    assert state.next_step == "1"
    assert any(call.kwargs["task_name"] == "thunder_send_email" for call in enqueue.call_args_list)


def test_a_tenant_without_a_whatsapp_provider_is_engaged_by_email_only(db):
    """Production 2026-10-25: tenant 1 has no WhatsApp provider, so every engagement with a
    WhatsApp-consenting candidate failed after its email cadence had started."""
    from app.models.api_keys_config import APIKeysConfig

    db.query(APIKeysConfig).filter(APIKeysConfig.tenant_id == 1).update({"is_active": False})  # as in production
    db.flush()
    c = candidate(db)
    message = SimpleNamespace(id=f"q-{uid()}", payload={"candidate_id": c.candidateID}, retry_count=0)
    with patch(ENQUEUE, return_value={"message_id": "x", "task_id": "x"}) as enqueue, \
         patch("app.services.thunder_service.has_active_consent", return_value=True), \
         patch("app.services.whatsapp_routing_service.resolve_outbound_whatsapp_number", return_value="+1555"), \
         patch("app.services.thunder_service.send_thunder_message") as send:
        result = ThunderEngagementHandler.process(message, db)
    assert result["status"] == "success" and result["message_sent"] is False
    send.assert_not_called()
    assert db.query(ThunderCadenceState).filter_by(candidate_id=c.candidateID).one().next_step == "1"
    assert any(call.kwargs["task_name"] == "thunder_send_email" for call in enqueue.call_args_list)


def test_whatsapp_is_ready_only_with_an_active_tested_twilio_provider(db):
    from app.models.api_keys_config import APIKeysConfig
    from app.services.delivery_factory import whatsapp_delivery_ready

    tenant_id = 900000 + int(uid(), 16) % 99999  # api_keys_config.tenant_id has no FK: a fresh tenant number
    assert whatsapp_delivery_ready(db, tenant_id) is False
    config = APIKeysConfig(tenant_id=tenant_id, provider="twilio", is_active=True, last_tested_status="failed")
    db.add(config)
    db.flush()
    assert whatsapp_delivery_ready(db, tenant_id) is False
    config.last_tested_status = "success"
    db.flush()
    assert whatsapp_delivery_ready(db, tenant_id) is True
    config.provider = "sendgrid"
    db.flush()
    assert whatsapp_delivery_ready(db, tenant_id) is False


def _engagement(db, c, status, n):
    db.add(ChannelQueueItem(id=f"eng-{uid()}", message_id=f"eng-{uid()}", tenant_id=1, type=sweep.ENGAGE_TASK,
                            channel_type="THUNDER_QUEUE", status=status, payload={"candidate_id": c.candidateID},
                            retry_count=0, created_at=datetime.utcnow()))
    db.commit()


def _sweep(db):
    queued = []
    with patch("app.services.thunder_mail.cadence_service.enqueue_once",
               side_effect=lambda task, task_id, data, tenant_id: queued.append(task_id) or True):
        sweep.run_sweep(db)
    return queued


def test_the_sweep_retries_a_failed_engagement_but_not_one_in_flight_nor_forever(db):
    c = candidate(db)
    _engagement(db, c, "FAILED", 1)
    assert sweep.engage_task_id(c.candidateID, 2) in _sweep(db)

    _engagement(db, c, "PENDING", 2)
    assert not [t for t in _sweep(db) if c.candidateID in t]

    db.query(ChannelQueueItem).filter(ChannelQueueItem.payload["candidate_id"].as_string() == c.candidateID) \
        .update({"status": "FAILED"}, synchronize_session=False)
    _engagement(db, c, "FAILED", 3)
    assert not [t for t in _sweep(db) if c.candidateID in t]
