"""Candidate-facing autonomy (CEO 2026-10-13): Thunder engages every contactable candidate,
every pipeline-status change is emailed to the candidate with no human step, and a tenant
other than the first can use the shared permission catalog."""
import os
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

os.environ.setdefault("JWT_SECRET", "test-secret-0123456789abcdef0123456789abcdef")

from app.models.candidate import Candidate, CandidateStatus  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402


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


def candidate(db, **kw):
    c = Candidate(candidateID=f"CAN-{uid()}", candidateFirstName="Asha", candidateLastName="R",
                  candidateEmail=kw.pop("email", f"{uid()}@candidate.example.com"), candidatePassword="x", tenant_id=1,
                  thunder_enabled=kw.pop("thunder_enabled", True), **kw)
    db.add(c)
    db.flush()
    return c


# ---- Thunder first engagement ------------------------------------------------------------

def test_the_sweep_queues_every_contactable_candidate_once(db):
    from app.services import thunder_engagement_sweep as sweep

    fresh = candidate(db)
    placeholder = candidate(db, email=f"x{uid()}@linkedin-pending.blitzenx.com")
    opted_out = candidate(db, thunder_enabled=False)
    old = candidate(db)
    old.candidateCreatedAt = datetime.utcnow() - timedelta(days=400)
    db.flush()

    queued = []
    with patch("app.services.thunder_mail.cadence_service.enqueue_once",
               side_effect=lambda task, task_id, data, tenant_id: queued.append((task, task_id)) or True):
        result = sweep.run_sweep(db)
    ids = {task_id for _, task_id in queued}
    assert sweep.engage_task_id(fresh.candidateID) in ids
    assert not ids & {sweep.engage_task_id(c.candidateID) for c in (placeholder, opted_out, old)}
    assert all(task == "engage_candidate_with_thunder" for task, _ in queued)
    assert result["status"] == "ok"


def test_the_sweep_stops_on_the_kill_switches(db):
    from app.services import thunder_engagement_sweep as sweep

    candidate(db)
    with patch("app.services.thunder_pause_service.is_thunder_paused", return_value=True):
        assert sweep.run_sweep(db) == {"status": "paused"}
    with patch("app.core.config.settings.THUNDER_ENGAGEMENT_ENABLED", False):
        assert sweep.run_sweep(db) == {"status": "disabled"}


def test_engagement_conversations_belong_to_the_ai_agent_so_thunder_may_send(db):
    from app.services.message_handlers.thunder_engagement_handler import ThunderEngagementHandler
    from app.models.candidate_ai import CandidateConversation
    from app.services.whatsapp_routing_service import is_ai_owner
    from tests.hiring_fixtures import full_access_role
    from app.models.user import Users

    role = full_access_role(db)
    db.add(Users(UserID=f"U-{uid()}", UserName="R", UserEmail=f"{uid()}@x.com", UserPassword="x",
                 UserRole="x", tenant_id=1, role_template_id=role.id))
    c = candidate(db)
    message = type("M", (), {"id": "m1", "payload": {"candidate_id": c.candidateID}, "retry_count": 0})
    with patch("app.services.thunder_mail.cadence_service.enqueue_send", return_value=True):
        result = ThunderEngagementHandler.process.__wrapped__(message, db) \
            if hasattr(ThunderEngagementHandler.process, "__wrapped__") else ThunderEngagementHandler.process(message, db)
    conversation = db.query(CandidateConversation).filter_by(candidate_id=c.candidateID).one()
    assert is_ai_owner(conversation)
    assert result["email_cadence_started"] is True and result["message_sent"] is False  # no WhatsApp sender


# ---- status emails ----------------------------------------------------------------------

def test_every_status_change_from_any_writer_is_queued_after_commit_only(db):
    c = candidate(db)
    queued = []
    with patch("app.services.candidate_status_notifications.queue_status_change",
               side_effect=lambda cid, old, new: queued.append((cid, old, new))):
        status = CandidateStatus(candidateID=c.candidateID, piplineStatus="Applied", status="Active")
        db.add(status)
        db.commit()
        status.piplineStatus = "Interview"
        db.commit()
        status.piplineStatus = "Rejected"
        db.flush()
        db.rollback()  # never committed -> never sent
    assert queued == [(c.candidateID, None, "Applied"), (c.candidateID, "Applied", "Interview")]


def test_status_email_is_a_thunder_notice_once_per_status_and_never_to_a_placeholder(db):
    from app.services.candidate_status_notifications import seed_templates, send_status_email

    seed_templates(db, 1)
    db.flush()
    c = candidate(db)
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", return_value=True) as queued:
        result = send_status_email(db, c, "Rejected")
        again = send_status_email(db, c, "Rejected")  # same status, same job: one email
        skipped = send_status_email(db, candidate(db, email=f"y{uid()}@linkedin-pending.blitzenx.com"), "Interview")
        unknown = send_status_email(db, c, "SomethingInternal")
    assert result["queued"] and result["template"] == "CANDIDATE_STATUS_REJECTED"
    assert result["email_id"] == f"pe:CANDIDATE_STATUS_REJECTED:{c.candidateID}:Rejected:none"
    assert queued.call_args.args[0] == "send_pipeline_email"  # the Thunder mailbox path
    assert not again["queued"] and not skipped["queued"] and not unknown["queued"] and queued.call_count == 1


def test_a_failed_queue_is_retried_not_swallowed(db):
    from app.services.candidate_status_notifications import seed_templates, send_status_email

    seed_templates(db, 1)
    db.flush()
    with patch("app.services.thunder_mail.cadence_service.enqueue_once", side_effect=RuntimeError("queue down")):
        with pytest.raises(RuntimeError):
            send_status_email(db, candidate(db), "Interview")


# ---- tenants share one catalog ------------------------------------------------------------

def test_a_second_tenant_uses_the_shared_catalog_with_its_own_templates(db):
    from app.models.role_template import RoleTemplate, RoleTemplatePermission
    from app.models.user import Users
    from app.services.role_template_permission_service import RoleTemplatePermissionService as Perms
    from tests.hiring_fixtures import full_access_role

    full_access_role(db)  # contract resources exist (tenant 1 catalog)
    if db.query(Tenant).filter_by(id=7).first() is None:
        db.add(Tenant(id=7, name=f"Parent co {uid()}"))
        db.flush()
    template = RoleTemplate(tenant_id=7, name=f"t-{uid()}", display_name="T", enabled=True)
    db.add(template)
    db.flush()
    jobs = Perms.get_resource_by_name(db, "jobs", 7)
    db.add(RoleTemplatePermission(role_template_id=template.id, resource_id=jobs.id, tenant_id=7, can_view=True))
    # a stray row filed under another tenant is ignored
    cands = Perms.get_resource_by_name(db, "candidates", 7)
    db.add(RoleTemplatePermission(role_template_id=template.id, resource_id=cands.id, tenant_id=1, can_view=True))
    user = Users(UserID=f"U-{uid()}", UserName="P", UserEmail=f"{uid()}@p.com", UserPassword="x", UserRole="x",
                 tenant_id=7, role_template_id=template.id)
    db.add(user)
    db.flush()
    assert Perms.has_permission(db, user.UserID, "jobs", "view", 7)
    assert not Perms.has_permission(db, user.UserID, "candidates", "view", 7)
    assert "jobs" in Perms._fetch_user_permissions_internal(db, user.UserID, 7)
