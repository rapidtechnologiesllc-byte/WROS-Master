"""Users and the org chart (CEO 2026-10-12): every user can be placed in the organization
from the user form -- on create and on edit -- and reporting may cross companies.

The scenario: AXION operates in BX-US and BX-IN. Its partner sits in BX-US; the BX-IN
BU head reports to that partner across companies, and sees AXION's work (scope is by
business unit, never by location)."""
import pytest
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnitCompany, BusinessUnitLocationHead
from app.models.location import Location
from app.models.org_structure import OrgNode
from app.services.org_structure_service import create_org_node
from tests.scope_fixtures import ApiClient, ids, person, two_bu_world, uid


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
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


@pytest.fixture
def firm(db):
    """BU A ("AXION") in two companies; its partner seated in BX-US under a CEO seat."""
    w = two_bu_world(db)
    us, india = Location(tenant_id=1, name=f"BX-US-{uid()}"), Location(tenant_id=1, name=f"BX-IN-{uid()}")
    db.add_all([us, india])
    db.flush()
    db.add_all([BusinessUnitCompany(tenant_id=1, business_unit_id=w.bu_a.id, company_id=us.id),
                BusinessUnitCompany(tenant_id=1, business_unit_id=w.bu_a.id, company_id=india.id)])
    ceo = db.query(OrgNode).filter(OrgNode.tenant_id == 1, OrgNode.hierarchy_level == 17,
                                   OrgNode.active.is_(True)).first() \
        or create_org_node(db, tenant_id=1, name="CEO seat", hierarchy_level=17, specialization="General")
    partner_seat = create_org_node(db, tenant_id=1, name=w.partner_a.UserName, hierarchy_level=16,
                                   specialization="General", parent_id=ceo.id, company_id=us.id)
    w.partner_a.org_node_id = partner_seat.id
    db.commit()
    w.us, w.india, w.partner_seat = us, india, partner_seat
    return w


def seat_of(db, user):
    db.expire_all()
    return db.query(OrgNode).filter(OrgNode.id == user.org_node_id).first()


def test_existing_user_without_a_seat_is_connected_from_the_edit_form(db, api, firm):
    head = person(db, firm.partner_role, "India head", business_unit_id=firm.bu_a.id)
    db.commit()
    assert head.org_node_id is None
    listed = {u["user_id"]: u for u in api.get(firm.org_user, "/api/v1/hr/users/all").json()["users"]}
    assert listed[head.UserID]["org_node_id"] is None  # shown as not connected

    response = api.put(firm.org_user, f"/api/v1/hr/users/{head.UserID}", json={
        "hierarchy_level": 15, "specialization": "General",
        "parent_node_id": firm.partner_seat.id, "location_id": firm.india.id})
    assert response.status_code == 200, response.text
    seat = seat_of(db, head)
    assert seat.parent_id == firm.partner_seat.id          # reports to the BX-US partner
    assert seat.company_id == firm.india.id                # while seated in BX-IN
    assert response.json()["org_node_id"] == seat.id

    detail = api.get(firm.org_user, f"/api/v1/hr/users/{head.UserID}").json()
    assert detail["reports_to"] == firm.partner_a.UserName and detail["hierarchy_level"] == 15


def test_india_head_reporting_to_us_partner_sees_the_bu_not_another_bu(db, api, firm):
    head = person(db, firm.partner_role, "India head")
    db.add(BusinessUnitLocationHead(tenant_id=1, business_unit_id=firm.bu_a.id, company_id=firm.india.id,
                                    head_user_id=head.UserID))
    db.commit()
    api.put(firm.org_user, f"/api/v1/hr/users/{head.UserID}", json={
        "hierarchy_level": 15, "specialization": "General",
        "parent_node_id": firm.partner_seat.id, "location_id": firm.india.id})
    clients = ids(api.get(head, "/api/v1/clients").json())
    assert firm.client_a.id in clients and firm.client_b.id not in clients


def test_level_gap_rule_applies_across_companies(db, api, firm):
    """An AVP (13) cannot report straight to a partner (16): at most two levels up."""
    avp = person(db, firm.partner_role, "AVP")
    db.commit()
    response = api.put(firm.org_user, f"/api/v1/hr/users/{avp.UserID}", json={
        "hierarchy_level": 13, "specialization": "General",
        "parent_node_id": firm.partner_seat.id, "location_id": firm.india.id})
    assert response.status_code == 422 and "cannot report to" in response.json()["detail"]
    assert seat_of(db, avp) is None


def test_no_one_reports_to_themselves_or_their_own_report(db, api, firm):
    head = person(db, firm.partner_role, "India head")
    db.commit()
    api.put(firm.org_user, f"/api/v1/hr/users/{head.UserID}", json={
        "hierarchy_level": 15, "specialization": "General", "parent_node_id": firm.partner_seat.id})
    # the partner may not be moved under someone who reports to them
    response = api.put(firm.org_user, f"/api/v1/hr/users/{firm.partner_a.UserID}", json={
        "hierarchy_level": 16, "specialization": "General", "parent_node_id": seat_of(db, head).id})
    assert response.status_code == 422


def test_seat_moves_without_creating_a_second_one(db, api, firm):
    head = person(db, firm.partner_role, "India head")
    db.commit()
    api.put(firm.org_user, f"/api/v1/hr/users/{head.UserID}", json={
        "hierarchy_level": 15, "specialization": "General", "parent_node_id": firm.partner_seat.id,
        "location_id": firm.india.id})
    first = seat_of(db, head).id
    api.put(firm.org_user, f"/api/v1/hr/users/{head.UserID}", json={"location_id": firm.us.id})
    seat = seat_of(db, head)
    assert seat.id == first and seat.company_id == firm.us.id and seat.parent_id == firm.partner_seat.id


# ── Backward compatibility with today's screens and production data (impact review) ──────

def test_editing_a_legacy_user_without_a_seat_does_not_force_placement(db, api, firm):
    """Production admins have free-text titles and no seat; the form always sends
    department_id. A name or department edit must just save."""
    admin = person(db, firm.org_role, "Legacy admin")
    admin.job_title = "Head of Everything"
    db.commit()
    response = api.put(firm.org_user, f"/api/v1/hr/users/{admin.UserID}",
                       json={"user_name": "Renamed admin", "department_id": "", "job_title": "Head of Everything"})
    assert response.status_code == 200, response.text
    assert seat_of(db, admin) is None


def test_unchanged_seat_is_not_revalidated_on_a_name_edit(db, api, firm):
    """A seat that predates today's rules (here: a two-level gap) survives a plain edit."""
    avp = person(db, firm.partner_role, "Legacy AVP")
    seat = create_org_node(db, tenant_id=1, name="Legacy AVP", hierarchy_level=15, specialization="General",
                           parent_id=firm.partner_seat.id)
    seat.hierarchy_level = 13  # set directly, as old data was
    avp.org_node_id = seat.id
    db.commit()
    response = api.put(firm.org_user, f"/api/v1/hr/users/{avp.UserID}", json={
        "user_name": "Legacy AVP (renamed)", "hierarchy_level": 13,
        "parent_node_id": firm.partner_seat.id, "location_id": None})
    assert response.status_code == 200, response.text
    assert seat_of(db, avp).hierarchy_level == 13


def test_department_change_follows_onto_the_seat_without_moving_it(db, api, firm):
    from app.models.org_structure import Department

    head = person(db, firm.partner_role, "India head")
    db.commit()
    api.put(firm.org_user, f"/api/v1/hr/users/{head.UserID}", json={
        "hierarchy_level": 15, "parent_node_id": firm.partner_seat.id, "location_id": firm.india.id})
    finance = Department(id=f"D-{uid()}", tenant_id=1, name=f"Accounts Payable {uid()}")
    db.add(finance)
    db.commit()
    response = api.put(firm.org_user, f"/api/v1/hr/users/{head.UserID}", json={"department_id": finance.id})
    assert response.status_code == 200, response.text
    seat = seat_of(db, head)
    assert seat.department_id == finance.id and seat.specialization == "Finance"
    assert seat.parent_id == firm.partner_seat.id


def test_an_empty_boss_seat_keeps_a_hand_set_manager(db, firm):
    from datetime import date

    from app.models.employee import Employee
    from app.services.org_structure_service import place_user_in_org

    worker = person(db, firm.partner_role, "Worker")
    boss_seat = create_org_node(db, tenant_id=1, name="Vacant", hierarchy_level=15, specialization="General",
                                parent_id=firm.partner_seat.id)
    employee = Employee(tenant_id=1, first_name="W", last_name=uid(), email=f"{uid()}@x.com",
                        joining_date=date(2025, 1, 1), wros_user_id=worker.UserID,
                        reporting_manager_user_id=firm.partner_a.UserID)
    db.add(employee)
    db.flush()
    place_user_in_org(db, worker, hierarchy_level=14, specialization=None, parent_id=boss_seat.id)
    db.flush()
    assert employee.reporting_manager_user_id == firm.partner_a.UserID


def test_role_rename_carries_only_exact_holders(db, api, firm):
    from app.models.org_structure import OrgRole

    role = OrgRole(tenant_id=1, name=f"Lead_{uid()}", hierarchy_level=6)
    db.add(role)
    holder, other = person(db, firm.partner_role, "Holder"), person(db, firm.partner_role, "Other")
    holder.job_title = role.name
    other.job_title = role.name.replace("_", "X")  # ilike would treat "_" as a wildcard
    db.commit()
    response = api.put(firm.org_user, f"/api/v1/org/roles/{role.id}", json={"name": f"Team Lead {uid()}"})
    assert response.status_code == 200, response.text
    db.expire_all()
    assert holder.job_title == response.json()["name"] and other.job_title != response.json()["name"]


def test_role_names_fit_the_job_title_column(db, api, firm):
    response = api.post(firm.org_user, "/api/v1/org/roles", json={"name": "x" * 151, "hierarchy_level": 5})
    assert response.status_code == 422
