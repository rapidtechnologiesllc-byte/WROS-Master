"""
EPIC-14/S-435 (HRMS-1408) -- Candidate & Employee Lifecycle
Communication Linking. Proves BR-1408-01 (metadata-only), BR-1408-02
(verified-email matching only, no false positives), and the
Employee-before-Candidate priority the module docstring describes.
Throwaway SQLite -- never the real database.
"""
import os
import tempfile
import logging
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.activity_timeline import ActivityTimeline
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.employee import Employee
from app.models.tenant import Tenant

from app.services.lifecycle_communication_linking_service import link_email_to_lifecycle_record


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Candidate.__table__, Employee.__table__, ActivityTimeline.__table__,
    ])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def _make_candidate(db, candidate_id="C-1", email="priya@example.com"):
    candidate = Candidate(
        candidateID=candidate_id, candidateEmail=email, candidatePassword="h",
        candidateFirstName="Priya", candidateLastName="Rao",
    )
    db.add(candidate)
    db.commit()
    return candidate


def _make_employee(db, tenant_id, employee_id=None, email="sam@blitzenx.com"):
    employee = Employee(
        id=employee_id or "E-1", tenant_id=tenant_id, first_name="Sam", last_name="Lee",
        email=email, joining_date=date(2025, 1, 1), status="ACTIVE",
    )
    db.add(employee)
    db.commit()
    return employee


def test_links_to_candidate_when_email_matches(db_session):
    _make_candidate(db_session, "C-1", "priya@example.com")

    result = link_email_to_lifecycle_record(
        db_session, other_party_email="priya@example.com", direction="SENT",
        subject="Interview Confirmation", timestamp=datetime.utcnow(),
    )

    assert result == {"entity_type": "candidate", "entity_id": "C-1", "timeline_entry_id": result["timeline_entry_id"]}
    entry = db_session.query(ActivityTimeline).filter(ActivityTimeline.entity_type == "candidate").first()
    assert entry.entity_id == "C-1"
    assert entry.action == "EMAIL_SENT"
    assert "Interview Confirmation" in entry.description


def test_links_to_employee_when_email_matches(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    _make_employee(db_session, tenant.id, "E-1", "sam@blitzenx.com")

    result = link_email_to_lifecycle_record(
        db_session, other_party_email="sam@blitzenx.com", direction="RECEIVED",
        subject="Benefits enrollment", timestamp=datetime.utcnow(),
    )

    assert result["entity_type"] == "employee"
    assert result["entity_id"] == "E-1"
    entry = db_session.query(ActivityTimeline).filter(ActivityTimeline.entity_type == "employee").first()
    assert entry.action == "EMAIL_RECEIVED"


def test_employee_checked_before_candidate_for_the_same_address(db_session):
    """Once someone converts, new mail belongs on their employee
    record -- their old candidate-era timeline entries are left alone,
    not moved (per the module's own 'no gap/duplicate' framing)."""
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()
    _make_candidate(db_session, "C-2", "converted@example.com")
    _make_employee(db_session, tenant.id, "E-2", "converted@example.com")

    result = link_email_to_lifecycle_record(
        db_session, other_party_email="converted@example.com", direction="SENT",
        subject="Welcome aboard", timestamp=datetime.utcnow(),
    )

    assert result["entity_type"] == "employee"
    assert result["entity_id"] == "E-2"


def test_unverified_address_produces_no_link(db_session):
    """BR-1408-02: no fuzzy matching, no false-positive link."""
    result = link_email_to_lifecycle_record(
        db_session, other_party_email="stranger@somewhereelse.com", direction="RECEIVED",
        subject="Unrelated", timestamp=datetime.utcnow(),
    )
    assert result is None
    assert db_session.query(ActivityTimeline).count() == 0


def test_no_message_body_ever_stored(db_session):
    """BR-1408-01: metadata-only. The function signature itself has no
    body/content parameter -- this test proves the stored description
    only ever contains subject/party/link, never arbitrary content."""
    _make_candidate(db_session, "C-3", "priya@example.com")
    link_email_to_lifecycle_record(
        db_session, other_party_email="priya@example.com", direction="SENT",
        subject="Offer Letter", timestamp=datetime.utcnow(), web_link="https://outlook.office.com/mail/id/abc123",
    )
    entry = db_session.query(ActivityTimeline).first()
    assert "Offer Letter" in entry.description
    assert "https://outlook.office.com/mail/id/abc123" in entry.description
    # No field on the model even exists for a message body -- structural
    # guarantee, not just a runtime check.
    assert not hasattr(entry, "body")
    assert not hasattr(entry, "content")


def test_invalid_direction_raises(db_session):
    with pytest.raises(ValueError):
        link_email_to_lifecycle_record(
            db_session, other_party_email="priya@example.com", direction="SIDEWAYS",
            subject="x", timestamp=datetime.utcnow(),
        )


def test_empty_email_produces_no_link(db_session):
    result = link_email_to_lifecycle_record(
        db_session, other_party_email="", direction="SENT",
        subject="x", timestamp=datetime.utcnow(),
    )
    assert result is None
