"""Every queued message names its tenant.

Without one the queue fell back to "the only tenant": with a second tenant every candidate status
change failed to queue (no status emails), and the other untagged messages would fail the same way.
"""
import ast
import pathlib
from unittest.mock import patch

from app.services.candidate_event_bus import CandidateEventBus
from tests import factories

APP = pathlib.Path(__file__).resolve().parents[1] / "app"


def test_every_enqueue_call_passes_a_tenant():
    missing = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "enqueue"
                    and getattr(getattr(node.func, "value", None), "id", "") == "MessageQueueService"
                    and "tenant_id" not in {k.arg for k in node.keywords}):
                missing.append(f"{path.relative_to(APP.parent)}:{node.lineno}")
    assert not missing, f"MessageQueueService.enqueue without tenant_id: {missing}"


def test_a_status_change_is_queued_under_the_candidates_own_tenant(db):
    factories.tenant(db, 1)
    factories.tenant(db, 2)  # with two tenants there is no "only tenant" to fall back on
    candidate = factories.candidate(db, tenant_id=2)
    db.commit()
    with patch("app.services.message_queue_service.MessageQueueService.enqueue",
               return_value={"status": "queued", "message_id": "m"}) as enqueue, \
            patch("app.core.database.SessionLocal", return_value=db), patch.object(db, "close"):
        CandidateEventBus.publish_status_changed(candidate.candidateID, "Applied", "Screening")
    assert enqueue.call_args.kwargs["tenant_id"] == 2
