"""
Proves Phase 1 B6's consent infrastructure: fail-closed by default, and
the most recent record governs even when history has both a grant and
a later revoke.

Runs against a throwaway SQLite file -- never the real database.
"""
import os
import tempfile
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.consent import ConsentRecord
from app.core.consent import record_consent, has_consent


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, ConsentRecord.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def test_negative_case_no_record_means_no_consent(db_session):
    """Fail closed: a subject never asked about consent must not be treated as opted in."""
    assert has_consent(
        db_session, subject_type="candidate", subject_id="C-AISHA", consent_type="whatsapp_outreach",
    ) is False


def test_positive_case_recorded_grant_is_honored(db_session):
    record_consent(
        db_session, subject_type="candidate", subject_id="C-AISHA",
        consent_type="whatsapp_outreach", consent_given=True, captured_by="candidate_self_service",
    )
    db_session.commit()

    assert has_consent(
        db_session, subject_type="candidate", subject_id="C-AISHA", consent_type="whatsapp_outreach",
    ) is True


def test_most_recent_record_wins_after_revoke(db_session):
    record_consent(
        db_session, subject_type="candidate", subject_id="C-AISHA",
        consent_type="whatsapp_outreach", consent_given=True, captured_by="candidate_self_service",
    )
    db_session.commit()
    time.sleep(0.01)
    record_consent(
        db_session, subject_type="candidate", subject_id="C-AISHA",
        consent_type="whatsapp_outreach", consent_given=False, captured_by="candidate_self_service",
    )
    db_session.commit()

    assert has_consent(
        db_session, subject_type="candidate", subject_id="C-AISHA", consent_type="whatsapp_outreach",
    ) is False
    # history is preserved, not overwritten
    assert db_session.query(ConsentRecord).count() == 2


def test_consent_types_and_subjects_are_independent(db_session):
    record_consent(
        db_session, subject_type="candidate", subject_id="C-AISHA",
        consent_type="whatsapp_outreach", consent_given=True,
    )
    db_session.commit()

    assert has_consent(
        db_session, subject_type="candidate", subject_id="C-AISHA", consent_type="interview_recording",
    ) is False
    assert has_consent(
        db_session, subject_type="candidate", subject_id="C-RAVI", consent_type="whatsapp_outreach",
    ) is False
