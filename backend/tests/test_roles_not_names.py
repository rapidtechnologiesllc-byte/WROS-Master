"""Who partners, heads or is coached is decided by the BU structure, never by a person's
name in code (CEO 2026-10-12): partner incentives, the 3-way alignment call, the Partner
Success Agent and the Partner dashboard."""
import asyncio
import pathlib
import re
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnitCompany, BusinessUnitLocationHead
from app.models.employee import Employee
from app.models.location import Location
from app.models.strategic_goal import GoalTarget
from tests.scope_fixtures import ApiClient, person, two_bu_world, uid


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
    return two_bu_world(db)


def test_new_logo_partner_is_the_bus_partner_not_any_member(db, w):
    from app.services.partner_incentive_service import get_partner_for_bu

    person(db, w.partner_role, "Recruiter in BU A", business_unit_id=w.bu_a.id)  # a member, not the partner
    db.commit()
    assert get_partner_for_bu(db, w.bu_a.id).UserID == w.partner_a.UserID


def test_alignment_call_parties_come_from_the_demand(db, w):
    from app.services.demand_confirmation_service import schedule_alignment_call

    company = Location(tenant_id=1, name=f"Co {uid()}")
    db.add(company)
    db.flush()
    head = person(db, w.partner_role, "Head of A")
    db.add_all([BusinessUnitCompany(business_unit_id=w.bu_a.id, company_id=company.id),
                BusinessUnitLocationHead(business_unit_id=w.bu_a.id, company_id=company.id, head_user_id=head.UserID)])
    worker = Employee(tenant_id=1, first_name="Sam", last_name=uid(), email=f"{uid()}@x.com", bu_id=w.bu_a.id,
                      joining_date=date(2025, 1, 1))
    db.add(worker)
    db.flush()
    call = schedule_alignment_call(db, w.job_a, worker)
    assert call.partner_user_id == w.partner_a.UserID
    assert call.bu_head_user_id == head.UserID


def test_partner_success_agent_coaches_any_partner_against_the_goals_screen(db, w):
    from app.services.fiscal_year_service import current_fy
    from app.services.partner_success_agent_service import PartnerSuccessAgent

    run = lambda user_id: asyncio.run(PartnerSuccessAgent.thursday_ceo_prep(  # noqa: E731
        tenant_id=1, partner_user_id=user_id, db=db))
    with pytest.raises(ValueError, match="not the partner"):
        run(w.org_user.UserID)
    with pytest.raises(ValueError, match="No FY"):
        run(w.partner_a.UserID)

    db.add(GoalTarget(tenant_id=1, year=current_fy(db, 1), level="BU", entity_id=f"co:{w.bu_a.id}",
                      metric="revenue", target=1_200_000))
    db.commit()
    report = run(w.partner_a.UserID)
    assert report["partner_user_id"] == w.partner_a.UserID
    assert report["forecast"]["target_usd"] == 1_200_000
    assert w.partner_a.UserName in report["todays_message"]


def test_partner_dashboard_route_has_no_person_in_it(w, db):
    api = ApiClient(db)
    try:
        assert api.get(w.partner_a, "/api/v1/dashboards/partner").status_code == 200
        assert api.get(w.partner_a, "/api/v1/dashboards/troy-partner").status_code == 404
    finally:
        api.close()


def test_no_person_names_in_application_code():
    """Names of people belong in the users table. The one allowed hit is the legacy column
    name of DemandAlignmentCall.partner_user_id (production tables are never renamed)."""
    root = pathlib.Path(__file__).resolve().parents[2]
    names = re.compile(r"troy|curtis", re.IGNORECASE)
    hits = []
    for folder, suffixes in ((root / "backend" / "app", {".py"}), (root / "frontend" / "src", {".js", ".jsx"})):
        for path in folder.rglob("*"):
            if path.suffix in suffixes and "node_modules" not in path.parts:
                for number, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                    if names.search(line) and 'Column("curtis_user_id"' not in line:
                        hits.append(f"{path.relative_to(root)}:{number}: {line.strip()}")
    assert hits == []
