"""
S-216/HRMS-0118 -- Shared Activity Timeline & File Attachment Framework.

Proves: AC-1 (any entity type writes to the same table, no schema
change), pagination/ordering, AC-2 (no presigned/access URL before a
clean scan), AC-3 (a scan-service failure quarantines rather than
auto-approves), and that a successful upload writes exactly one
activity_timeline entry too (the two halves of this framework working
together, not in isolation).

Throwaway SQLite, real SharePoint call mocked -- never a real network
call or the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.activity_timeline import ActivityTimeline
from app.models.base import Base
from app.models.file_upload import FileUpload
from app.models.tenant import Tenant
from app.models.user import Users

import app.services.activity_timeline_service as timeline_svc
import app.services.file_upload_service as upload_svc


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Users.__table__, ActivityTimeline.__table__, FileUpload.__table__,
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
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    user = Users(UserID="U-1", UserRole="Recruiter", UserEmail="rec@blitzenx.com", UserPassword="h", tenant_id=tenant.id)
    db_session.add(user)
    db_session.commit()
    return tenant, user


def _fake_sharepoint_upload(access_token, entity_type, entity_id, file_content, unique_filename):
    return {"webUrl": f"https://sharepoint.example/{entity_type}/{entity_id}/{unique_filename}"}


# ---------------------------------------------------------------------------
# activity_timeline_service
# ---------------------------------------------------------------------------

def test_two_unrelated_entity_types_write_to_the_same_table(db_session, seeded):
    tenant, user = seeded
    timeline_svc.write_timeline_entry(
        db_session, tenant_id=tenant.id, entity_type="candidate", entity_id="C-1",
        actor_id=user.UserID, action="STATUS_CHANGED", description="Moved to Interview",
    )
    timeline_svc.write_timeline_entry(
        db_session, tenant_id=tenant.id, entity_type="project", entity_id="P-1",
        actor_id=user.UserID, action="MILESTONE_HIT", description="Phase 1 complete",
    )
    db_session.commit()

    candidate_feed = timeline_svc.get_timeline_for_entity(db_session, "candidate", "C-1")
    project_feed = timeline_svc.get_timeline_for_entity(db_session, "project", "P-1")
    assert candidate_feed["total"] == 1
    assert candidate_feed["entries"][0]["action"] == "STATUS_CHANGED"
    assert project_feed["total"] == 1
    assert project_feed["entries"][0]["action"] == "MILESTONE_HIT"


def test_timeline_newest_first_and_paginated(db_session, seeded):
    tenant, user = seeded
    for i in range(3):
        timeline_svc.write_timeline_entry(
            db_session, tenant_id=tenant.id, entity_type="candidate", entity_id="C-1",
            action=f"EVENT_{i}",
        )
    db_session.commit()

    result = timeline_svc.get_timeline_for_entity(db_session, "candidate", "C-1", page=1, per_page=2)
    assert result["total"] == 3
    assert len(result["entries"]) == 2
    assert result["entries"][0]["action"] == "EVENT_2"  # newest first


# ---------------------------------------------------------------------------
# file_upload_service
# ---------------------------------------------------------------------------

def test_successful_upload_is_clean_and_accessible(db_session, seeded, monkeypatch):
    tenant, user = seeded
    monkeypatch.setattr(upload_svc, "_upload_to_sharepoint", _fake_sharepoint_upload)

    file_upload = upload_svc.upload_file(
        db_session, tenant_id=tenant.id, entity_type="candidate", entity_id="C-1",
        file_content=b"fake pdf bytes", original_filename="invoice.pdf", file_category="INVOICE",
        uploaded_by=user.UserID, graph_token_fn=lambda: "fake-token",
        scanner_client=lambda content: "clean",
    )
    db_session.commit()

    assert file_upload.scan_status == "CLEAN"
    url = upload_svc.get_file_access_url(db_session, file_upload.id)
    assert url is not None and "invoice" not in url  # unique filename, not the raw original name


def test_pending_file_never_issues_access_url(db_session, seeded, monkeypatch):
    """AC-2 -- no scan result at all (unconfigured scanner) must never
    unlock access."""
    tenant, user = seeded
    monkeypatch.setattr(upload_svc, "_upload_to_sharepoint", _fake_sharepoint_upload)

    file_upload = upload_svc.upload_file(
        db_session, tenant_id=tenant.id, entity_type="candidate", entity_id="C-1",
        file_content=b"fake bytes", original_filename="resume.pdf",
        uploaded_by=user.UserID, graph_token_fn=lambda: "fake-token",
        # no scanner_client -- falls back to the default unconfigured stub
    )
    db_session.commit()

    assert file_upload.scan_status == "QUARANTINED"
    assert upload_svc.get_file_access_url(db_session, file_upload.id) is None


def test_scan_service_failure_quarantines_not_auto_approves(db_session, seeded, monkeypatch):
    """AC-3."""
    tenant, user = seeded
    monkeypatch.setattr(upload_svc, "_upload_to_sharepoint", _fake_sharepoint_upload)

    def _flaky_scanner(content):
        raise RuntimeError("scanner service unreachable")

    file_upload = upload_svc.upload_file(
        db_session, tenant_id=tenant.id, entity_type="candidate", entity_id="C-1",
        file_content=b"fake bytes", original_filename="doc.pdf",
        uploaded_by=user.UserID, graph_token_fn=lambda: "fake-token",
        scanner_client=_flaky_scanner,
    )
    db_session.commit()

    assert file_upload.scan_status == "QUARANTINED"


def test_upload_writes_exactly_one_activity_timeline_entry(db_session, seeded, monkeypatch):
    tenant, user = seeded
    monkeypatch.setattr(upload_svc, "_upload_to_sharepoint", _fake_sharepoint_upload)

    before = db_session.query(ActivityTimeline).count()
    upload_svc.upload_file(
        db_session, tenant_id=tenant.id, entity_type="candidate", entity_id="C-1",
        file_content=b"fake bytes", original_filename="doc.pdf",
        uploaded_by=user.UserID, graph_token_fn=lambda: "fake-token",
        scanner_client=lambda content: "clean",
    )
    db_session.commit()
    after = db_session.query(ActivityTimeline).filter(
        ActivityTimeline.entity_type == "candidate", ActivityTimeline.entity_id == "C-1",
    ).count()
    assert after == before + 1


def test_list_files_for_entity_scoped_correctly(db_session, seeded, monkeypatch):
    tenant, user = seeded
    monkeypatch.setattr(upload_svc, "_upload_to_sharepoint", _fake_sharepoint_upload)

    upload_svc.upload_file(
        db_session, tenant_id=tenant.id, entity_type="candidate", entity_id="C-1",
        file_content=b"a", original_filename="a.pdf", uploaded_by=user.UserID,
        graph_token_fn=lambda: "t", scanner_client=lambda c: "clean",
    )
    upload_svc.upload_file(
        db_session, tenant_id=tenant.id, entity_type="candidate", entity_id="C-2",
        file_content=b"b", original_filename="b.pdf", uploaded_by=user.UserID,
        graph_token_fn=lambda: "t", scanner_client=lambda c: "clean",
    )
    db_session.commit()

    files = upload_svc.list_files_for_entity(db_session, "candidate", "C-1")
    assert len(files) == 1
    assert files[0].original_filename == "a.pdf"
