"""
Proves HRMS-0110's append-only guarantee at the layer this codebase can
import logging
actually test locally: the ORM-level guard in app.models.audit_log.

The database-grant-level enforcement (DENY UPDATE, DELETE at the SQL
Server login level -- the actual HRMS-0110 requirement) can only be
verified against the real database by whoever has DB access; see the
migration file's docstring for the manual step required there. This
suite is the defense-in-depth layer underneath that, plus the
positive-case and same-transaction behavior of write_audit_log().

Runs entirely against a throwaway SQLite file -- never the real database.
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.audit_log import AuditLog, AppendOnlyViolation
from app.core.audit import write_audit_log


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, AuditLog.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


def test_positive_case_write_audit_log_persists_a_row(db_session):
    write_audit_log(
        db_session, entity_type="candidate", entity_id="C-AISHA",
        action="hard_rule_override", user_id="U-BUHEAD",
        old_value="experience=2yrs", new_value="R-01 override approved",
    )
    db_session.commit()

    rows = db_session.query(AuditLog).all()
    assert len(rows) == 1
    assert rows[0].entity_id == "C-AISHA"
    assert rows[0].action == "hard_rule_override"


def test_write_audit_log_does_not_commit_itself(db_session):
    """
    write_audit_log() must only stage the row (db.add), never commit --
    that's what makes "same transaction as the override" possible. If it
    committed internally, a caller couldn't roll both back together.
    """
    write_audit_log(
        db_session, entity_type="candidate", entity_id="C-AISHA",
        action="create", user_id="U-RECRUITER",
    )
    db_session.rollback()

    assert db_session.query(AuditLog).count() == 0


def test_negative_case_update_is_rejected_even_for_admin_role(db_session):
    """
    HRMS-0110's acceptance test: append-only, tested against the Admin
    role specifically. The guard is unconditional (not a permission
    check), so there is no role -- Admin included -- that can bypass it.
    """
    row = write_audit_log(
        db_session, entity_type="candidate", entity_id="C-AISHA",
        action="create", user_id="U-ADMIN",
    )
    db_session.commit()

    row.new_value = "tampered by admin"
    with pytest.raises(AppendOnlyViolation):
        db_session.commit()


def test_negative_case_delete_is_rejected_even_for_admin_role(db_session):
    row = write_audit_log(
        db_session, entity_type="candidate", entity_id="C-AISHA",
        action="create", user_id="U-ADMIN",
    )
    db_session.commit()

    db_session.delete(row)
    with pytest.raises(AppendOnlyViolation):
        db_session.commit()
