"""HRMS watches certificate expiry itself (CEO 2026-11-02, after JobDiva's expiring-certifications
email: "HRMS should be doing it similar on its own"): each threshold before expiry alerts the employee
and their manager once, with one renewal task per certificate term."""
import uuid
from datetime import date, datetime
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.activity_timeline import ActivityTimeline
from app.models.certification import Certification, CertificationExpiryAlert, EmployeeCertification
from app.models.employee import Employee
from app.models.task import Task
from app.services.certification_expiry_monitor import alert_thresholds, run_expiry_monitor
from tests.scope_fixtures import two_bu_world

QUEUE = "app.services.staff_mail_service.queue_staff_email"
TODAY = date(2026, 11, 2)


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def w(db):
    world = two_bu_world(db)
    world.employee = Employee(tenant_id=1, first_name="Aniket", last_name="Magar", status="ACTIVE",
                              email=f"aniket{uuid.uuid4().hex[:6]}@blitzenx.com", joining_date=date(2025, 1, 6),
                              reporting_manager_user_id=world.partner_a.UserID, wros_user_id=world.org_user.UserID)
    world.cert = Certification(tenant_id=1, cert_name="Ace Guidewire", cert_code=f"ACE-{uuid.uuid4().hex[:8]}")
    db.add_all([world.employee, world.cert])
    db.commit()
    return world


def _hold(db, w, expires, employee=None):
    record = EmployeeCertification(tenant_id=1, employee_id=(employee or w.employee).id, certification_id=w.cert.id,
                                   earned_date=datetime(2024, 1, 1), expires_date=expires, cert_number="ACP-1")
    db.add(record)
    db.commit()
    return record


def _run(db, today=TODAY):
    with patch(QUEUE) as queue:
        result = run_expiry_monitor(db, today=today)
    return result, queue


def _alerts(queue):
    """The expiry emails (the new renewal task also emails its assignee)."""
    return [c for c in queue.call_args_list if c.kwargs["key"].startswith("cert-expiry-")]


def _renewals(db, w):
    return db.query(Task).filter(Task.link == f"/employees/{w.employee.id}", Task.category == "CERTIFICATION").all()


def test_a_certificate_inside_the_window_alerts_the_employee_and_manager_once(db, w):
    record = _hold(db, w, datetime(2027, 1, 20))  # 79 days: the 180 and 90 thresholds are both crossed
    result, queue = _run(db)
    assert result["alerted"] == 1
    assert {c.args[0].UserID for c in _alerts(queue)} == {w.partner_a.UserID, w.org_user.UserID}
    subject = _alerts(queue)[0].kwargs["subject"]
    assert "Ace Guidewire for Aniket Magar expires on 20 Jan 2027 (79 days)" in subject
    [task] = _renewals(db, w)
    assert task.assigned_to_user_id == w.partner_a.UserID and task.title.startswith("Renew Ace Guidewire")
    marks = db.query(CertificationExpiryAlert).filter_by(employee_certification_id=record.id).all()
    assert sorted(m.threshold_days for m in marks) == [90, 180] and {m.task_id for m in marks} == {task.id}
    assert db.query(ActivityTimeline).filter_by(entity_id=w.employee.id, action="certification_expiry").count() == 1

    again, queue = _run(db)  # the next day: nothing new crossed
    assert again["alerted"] == 0 and not queue.call_args_list


def test_each_threshold_alerts_again_on_the_same_task(db, w):
    _hold(db, w, datetime(2027, 1, 20))
    _run(db)
    result, queue = _run(db, today=date(2026, 12, 21))  # 30 days left
    assert result["alerted"] == 1 and len(_alerts(queue)) == 2
    assert len(_renewals(db, w)) == 1


def test_an_expired_certificate_is_marked_expired(db, w):
    record = _hold(db, w, datetime(2026, 10, 20))
    _, queue = _run(db)
    db.refresh(record)
    assert record.status == "Expired"
    assert "expired on 20 Oct 2026" in _alerts(queue)[0].kwargs["subject"]
    assert _renewals(db, w)[0].priority == "HIGH"


def test_far_off_long_lapsed_and_leavers_are_not_alerted(db, w):
    _hold(db, w, datetime(2028, 1, 1))  # beyond 180 days
    _hold(db, w, datetime(2025, 1, 1))  # lapsed long ago
    leaver = Employee(tenant_id=1, first_name="Gone", last_name="Person", status="EXITED",
                      email=f"gone{uuid.uuid4().hex[:6]}@blitzenx.com", joining_date=date(2024, 1, 1))
    db.add(leaver)
    db.commit()
    _hold(db, w, datetime(2026, 12, 1), employee=leaver)
    result, queue = _run(db)
    assert result["alerted"] == 0 and not queue.call_args_list


def test_a_renewed_certificate_gets_its_own_alerts(db, w):
    record = _hold(db, w, datetime(2026, 12, 1))
    _run(db)
    record.expires_date = datetime(2027, 3, 1)  # renewed: a new term
    db.commit()
    result, _ = _run(db)
    assert result["alerted"] == 1 and len(_renewals(db, w)) == 2


def test_alert_days_are_validated():
    with patch("app.services.certification_expiry_monitor.settings.CERT_EXPIRY_ALERT_DAYS", "180,soon"):
        with pytest.raises(ValueError, match="CERT_EXPIRY_ALERT_DAYS"):
            alert_thresholds()
    assert alert_thresholds() == [180, 90, 30, 0]
