"""Partner per BU, BU head per BU per company (CEO 2026-10-12). Test personas are roles,
not people:

  ceo           heads NEXUS in BX-US and BX-IN
  partner       partner of AXION (every company) and head of AXION in BX-US
  india_head    heads AXION in BX-IN only

Visibility is by business unit, never by location: anyone who partners a BU or heads it
in any company sees all of it. Per-company heads route approvals (head_for_client)."""
import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.core.revenue_visibility_scope import apply_revenue_bu_scope_to_client_query
from app.core.visibility import get_user_bu_ids
from app.models.bank_reconciliation import BankTransaction
from app.models.business_unit import BusinessUnit, BusinessUnitCompany, BusinessUnitLocationHead
from app.models.client import Client
from app.models.cost_rate_config import CostRateConfig
from app.models.invoice import Invoice
from app.models.location import Location
from app.models.project import Project
from app.models.role_template import RoleTemplate
from app.models.tenant import Tenant
from app.models.user import Users
from app.services import bu_leadership
from app.services.financial_outlook_service import outlook

SEPT = (date(2026, 9, 1), date(2026, 9, 30))


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def db(test_db_engine):
    connection = test_db_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def _role(db, level, org=False):
    role = RoleTemplate(tenant_id=1, name=f"r-{_uid()}", display_name="R", hierarchy_level=level,
                        org_level_access=org, enabled=True)
    db.add(role)
    db.flush()
    return role


def _person(db, name, role, bu=None):
    user = Users(UserID=f"U-{_uid()}", UserName=name, UserEmail=f"{_uid()}@x.com", UserPassword="x",
                 UserRole="x", tenant_id=1, role_template_id=role.id, business_unit_id=bu.id if bu else None)
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def firm(db):
    if db.query(Tenant).filter_by(id=1).first() is None:
        db.add(Tenant(id=1, name="test-tenant"))
        db.flush()
    us, india = Location(tenant_id=1, name=f"BX-US-{_uid()}"), Location(tenant_id=1, name=f"BX-IN-{_uid()}")
    db.add_all([us, india])
    db.flush()
    partner_role, head_role, ceo_role = _role(db, 16), _role(db, 14), _role(db, 17)
    axion = BusinessUnit(name=f"AXION-{_uid()}", display_name="AXION")
    nexus = BusinessUnit(name=f"NEXUS-{_uid()}", display_name="NEXUS")
    db.add_all([axion, nexus])
    db.flush()
    for bu in (axion, nexus):
        for company in (us, india):
            db.add(BusinessUnitCompany(tenant_id=1, business_unit_id=bu.id, company_id=company.id))
        db.add(CostRateConfig(business_unit_id=bu.id, statutory_pct=0, overhead_pct=0))
    partner = _person(db, "Partner", partner_role, axion)
    india_head = _person(db, "India head", head_role, axion)
    ceo = _person(db, "CEO", ceo_role)
    axion.partner_user_id = partner.UserID
    db.flush()
    pick = lambda user_id: db.query(Users).filter_by(UserID=user_id).one()  # noqa: E731
    bu_leadership.set_location_heads(db, axion, 1, {us.id: partner.UserID, india.id: india_head.UserID}, pick)
    bu_leadership.set_location_heads(db, nexus, 1, {us.id: ceo.UserID, india.id: ceo.UserID}, pick)
    db.commit()
    return SimpleNamespace(us=us, india=india, axion=axion, nexus=nexus, partner=partner, india_head=india_head, ceo=ceo)


def test_scope_is_by_business_unit_not_location(db, firm):
    assert get_user_bu_ids(db, firm.partner) == {firm.axion.id}
    assert get_user_bu_ids(db, firm.india_head) == {firm.axion.id}  # heads AXION in one company: sees all AXION
    assert get_user_bu_ids(db, firm.ceo) == {firm.nexus.id}         # the CEO role here is not org-level


def test_head_can_only_be_set_where_the_bu_operates(db, firm):
    other = Location(tenant_id=1, name=f"BX-UK-{_uid()}")
    db.add(other)
    db.flush()
    with pytest.raises(ValueError, match="does not operate in"):
        bu_leadership.set_location_heads(db, firm.axion, 1, {other.id: firm.india_head.UserID}, lambda u: firm.india_head)
    bu_leadership.set_location_heads(db, firm.axion, 1, {firm.india.id: ""}, lambda u: None)  # "" clears
    assert bu_leadership.head_user_id(db, firm.axion.id, firm.india.id) is None


def test_job_routing_follows_the_clients_company(db, firm):
    us_client = Client(tenant_id=1, company_name=f"US co {_uid()}", business_unit_id=firm.axion.id,
                       contracting_company_id=firm.us.id)
    in_client = Client(tenant_id=1, company_name=f"IN co {_uid()}", business_unit_id=firm.axion.id,
                       contracting_company_id=firm.india.id)
    db.add_all([us_client, in_client])
    db.flush()
    assert bu_leadership.head_for_client(db, firm.axion.id, us_client.id) == firm.partner.UserID
    assert bu_leadership.head_for_client(db, firm.axion.id, in_client.id) == firm.india_head.UserID
    assert bu_leadership.head_for_client(db, firm.axion.id, None) is None  # two companies: never a guess


def test_revenue_and_clients_follow_the_business_unit(db, firm):
    other = BusinessUnit(name=f"OTHER-{_uid()}", display_name="OTHER")
    db.add(other)
    db.flush()
    clients = {}
    for key, bu, company, amount in (("us", firm.axion, firm.us, 500_000), ("in", firm.axion, firm.india, 200_000),
                                     ("other", other, firm.us, 900_000)):
        client = Client(tenant_id=1, company_name=f"C {_uid()}", business_unit_id=bu.id, contracting_company_id=company.id)
        db.add(client)
        db.flush()
        clients[key] = client
        project = Project(tenant_id=1, client_id=client.id, name=f"P {_uid()}", delivery_engine="CORE")
        db.add(project)
        db.flush()
        invoice = Invoice(tenant_id=1, client_id=client.id, project_id=project.id,
                          billing_period_start=SEPT[0], billing_period_end=SEPT[1],
                          currency="USD", total_usd_cents=amount, status="PAID")
        db.add(invoice)
        db.flush()
        db.add(BankTransaction(tenant_id=1, transaction_date=date(2026, 9, 20), amount_usd_cents=amount,
                               description="UTR", matched_invoice_id=invoice.id, reconciled=True))
    db.commit()
    report = outlook(db, start=SEPT[0], end=SEPT[1], today=date(2026, 9, 30),
                     business_unit_ids=get_user_bu_ids(db, firm.india_head))
    assert {r["key"] for r in report["by_business_unit"]} == {firm.axion.id}
    assert report["actual_revenue"] == 700_000  # all of AXION, both companies; never OTHER
    visible = {c.id for c in apply_revenue_bu_scope_to_client_query(db, db.query(Client), firm.india_head)}
    assert clients["us"].id in visible and clients["in"].id in visible and clients["other"].id not in visible


def test_old_single_head_is_carried_into_each_company_once(db, firm):
    prism = BusinessUnit(name=f"PRISM-{_uid()}", display_name="PRISM", manager_id=firm.india_head.UserID)
    lonely = BusinessUnit(name=f"SOLO-{_uid()}", display_name="SOLO", manager_id=firm.india_head.UserID)
    db.add_all([prism, lonely])
    db.flush()
    db.add(BusinessUnitCompany(tenant_id=1, business_unit_id=prism.id, company_id=firm.india.id))
    db.commit()
    bu_leadership.carry_over_single_heads(db)
    db.refresh(prism)
    db.refresh(lonely)
    assert bu_leadership.head_user_id(db, prism.id, firm.india.id) == firm.india_head.UserID
    assert prism.manager_id is None
    assert lonely.manager_id == firm.india_head.UserID  # no company to put the head in: kept, logged
    assert db.query(BusinessUnitLocationHead).filter_by(business_unit_id=lonely.id).count() == 0
