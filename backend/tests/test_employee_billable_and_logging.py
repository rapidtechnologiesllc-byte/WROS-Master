"""CEO 2026-11-04: the Log buttons all failed; the Interview tab failed on a logged interview; a non-billable
employee was counted on the Bench; and Add employee worked out no minimum bill rate."""
import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.candidate import Candidate
from app.models.cost_rate_config import CostRateConfig
from app.models.margin_policy import MarginPolicy
from app.models.user import InterviewFeedback, average_feedback_score
from app.services import margin_guard_service
from app.services.employee_standing import deployment_status
from tests.scope_fixtures import ApiClient, two_bu_world

TODAY = date(2026, 11, 4)


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
    world.candidate = Candidate(tenant_id=1, candidateID=f"CAN-{uuid.uuid4().hex[:10]}", candidatePassword="h",
                                candidateFirstName="Jane", candidateLastName="Doe",
                                candidateEmail=f"j{uuid.uuid4().hex[:6]}@example.com")
    db.add(world.candidate)
    db.commit()
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@pytest.mark.parametrize("event", ["Email Sent", "Call", "LinkedIn Message", "WhatsApp Message", "Meeting"])
def test_every_log_button_records_its_activity(api, w, event):
    response = api.post(w.org_user, f"/api/v1/history/{w.candidate.candidateID}",
                        json={"event_type": event, "note": "Reached out about the role."})
    assert response.status_code in (200, 201), response.text
    listed = api.get(w.org_user, f"/api/v1/history/{w.candidate.candidateID}").json()
    assert event in str(listed)


def test_average_uses_the_scores_given():
    assert average_feedback_score(InterviewFeedback()) is None
    assert average_feedback_score(InterviewFeedback(technical_score=8, culture_fit_score=6)) == 7
    assert average_feedback_score(InterviewFeedback(technical_score=8, communication_score=7,
                                                    problem_solving_score=6, culture_fit_score=5)) == 6.5


def test_a_logged_interview_without_scores_does_not_break_my_interviews(api, db, w):
    logged = api.client.post(
        "/api/v1/interviews/log-completed", headers=ApiClient.headers(w.org_user),
        data={"candidate_id": w.candidate.candidateID, "interview_type": "Technical", "meeting_platform": "Teams",
              "recommendation": "Hire", "summary": "Strong on BillingCenter.", "interview_date": "2026-11-01"})
    assert logged.status_code == 201, logged.text
    feedback = db.query(InterviewFeedback).order_by(InterviewFeedback.id.desc()).first()
    assert feedback.technical_score is None
    feedback.interviewer_id = w.org_user.UserID
    db.commit()
    response = api.get(w.org_user, "/api/v1/interviews/my-interviews")
    assert response.status_code == 200, response.text
    assert api.get(w.org_user, f"/api/v1/interviews/candidate-history/{w.candidate.candidateID}").status_code == 200
    assert api.get(w.org_user, "/api/v1/interviews/statistics").status_code == 200


def test_non_billable_staff_are_non_billable_not_bench():
    assert deployment_status("ACTIVE", "GRADUATED", [], None, TODAY, billable=False) == {
        "status": "NON_BILLABLE", "until": None, "days": None}
    assert deployment_status("BENCH", "GRADUATED", [], 12, TODAY)["status"] == "BENCH"


def test_minimum_bill_rate_is_pay_plus_location_overhead_grossed_up_by_the_floor(db, w):
    db.add(CostRateConfig(tenant_id=None, business_unit_id=None, country="ZZ", statutory_pct=10, overhead_pct=15,
                          effective_date=date(2020, 1, 1)))
    db.add(MarginPolicy(tenant_id=w.org_user.tenant_id, delivery_engine="CORE", country="ZZ", min_margin_pct=50, hard_floor_pct=20))
    db.flush()
    monthly = settings.STANDARD_MONTHLY_HOURS * 8000  # $80 / hour of pay
    result = margin_guard_service.minimum_bill_rate(db, tenant_id=w.org_user.tenant_id, business_unit_id=None, country="ZZ",
                                                    monthly_usd_cents=monthly)
    assert result["pay_hourly_usd_cents"] == 8000
    assert result["break_even_usd_cents"] == 10000  # 80 x 1.25
    core = next(l for l in result["lines"] if l["delivery_engine"] == "CORE")
    assert core["minimum_usd_cents"] == 20000  # 100 / (1 - 0.5)
    assert core["hard_floor_usd_cents"] == 12500  # 100 / (1 - 0.2)


def test_minimum_bill_rate_names_what_is_missing_and_never_guesses(db, w):
    result = margin_guard_service.minimum_bill_rate(db, tenant_id=w.org_user.tenant_id, business_unit_id=None, country="ZY",
                                                    monthly_usd_cents=1_000_000)
    assert result["break_even_usd_cents"] is None
    assert any("statutory" in m for m in result["missing"])


def test_a_sub_vendors_rate_is_the_whole_cost(db, w):
    db.add(MarginPolicy(tenant_id=w.org_user.tenant_id, delivery_engine="SPECIALITY", country="ZX", min_margin_pct=20, hard_floor_pct=10))
    db.flush()
    result = margin_guard_service.minimum_bill_rate(db, tenant_id=w.org_user.tenant_id, business_unit_id=None, country="ZX",
                                                    vendor_rate_usd_cents=8000)
    assert result["break_even_usd_cents"] == 8000
    assert next(l for l in result["lines"] if l["delivery_engine"] == "SPECIALITY")["minimum_usd_cents"] == 10000
