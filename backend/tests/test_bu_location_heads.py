"""Partner per BU, BU head per BU per company (CEO 2026-10-12):

  Avinash  CEO, heads NEXUS in BX-US and BX-IN
  Troy     partner of AXION (both companies) and head of AXION in BX-US
  Hemant   head of AXION in BX-IN only
  Curtis   partner of PRISM; AGS Manian heads PRISM in BX-IN

A head sees and approves for their BU in their company only; a partner sees the BU
everywhere; a person's own-BU membership never widens a head's location scope."""
import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.core.revenue_visibility_scope import apply_revenue_bu_scope_to_client_query
from app.core.visibility import companies_in_scope, get_user_data_scope
from app.models.bank_reconciliation import BankTransaction
from app.models.business_unit import BusinessUnit, BusinessUnitCompany, BusinessUnitLocationHead
from app.models.client import Client
from app.models.cost_rate_config import CostRateConfig
from app.models.employee import Employee
from app.models.invoice import Invoice
from app.models.location import Location
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
    troy = _person(db, "Troy", partner_role, axion)
    hemant = _person(db, "Hemant", head_role, axion)   # member of AXION, heads it in BX-IN only
    avinash = _person(db, "Avinash", ceo_role)
    axion.partner_user_id = troy.UserID
    db.flush()
    pick = lambda user_id: db.query(Users).filter_by(UserID=user_id).one()  # noqa: E731
    bu_leadership.set_location_heads(db, axion, 1, {us.id: troy.UserID, india.id: hemant.UserID}, pick)
    bu_leadership.set_location_heads(db, nexus, 1, {us.id: avinash.UserID, india.id: avinash.UserID}, pick)
    db.commit()
    return SimpleNamespace(us=us, india=india, axion=axion, nexus=nexus, troy=troy, hemant=hemant, avinash=avinash)


def test_scope_partner_sees_whole_bu_head_sees_their_company_only(db, firm):
    assert get_user_data_scope(db, firm.troy) == {firm.axion.id: None}  # partner + US head = whole BU
    assert get_user_data_scope(db, firm.hemant) == {firm.axion.id: frozenset({firm.india.id})}
    assert companies_in_scope(db, firm.hemant, firm.axion.id) == frozenset({firm.india.id})
    assert companies_in_scope(db, firm.hemant, firm.nexus.id) == frozenset()
    assert get_user_data_scope(db, firm.avinash) == {firm.nexus.id: frozenset({firm.us.id, firm.india.id})}


def test_head_can_only_be_set_where_the_bu_operates(db, firm):
    other = Location(tenant_id=1, name=f"BX-UK-{_uid()}")
    db.add(other)
    db.flush()
    with pytest.raises(ValueError, match="does not operate in"):
        bu_leadership.set_location_heads(db, firm.axion, 1, {other.id: firm.hemant.UserID}, lambda u: firm.hemant)
    bu_leadership.set_location_heads(db, firm.axion, 1, {firm.india.id: ""}, lambda u: None)  # "" clears
    assert bu_leadership.head_user_id(db, firm.axion.id, firm.india.id) is None


def test_job_routing_follows_the_clients_company(db, firm):
    us_client = Client(tenant_id=1, company_name=f"US co {_uid()}", business_unit_id=firm.axion.id,
                       contracting_company_id=firm.us.id)
    in_client = Client(tenant_id=1, company_name=f"IN co {_uid()}", business_unit_id=firm.axion.id,
                       contracting_company_id=firm.india.id)
    db.add_all([us_client, in_client])
    db.flush()
    assert bu_leadership.head_for_client(db, firm.axion.id, us_client.id) == firm.troy.UserID
    assert bu_leadership.head_for_client(db, firm.axion.id, in_client.id) == firm.hemant.UserID
    assert bu_leadership.head_for_client(db, firm.axion.id, None) is None  # two companies: never a guess


def test_revenue_and_payroll_are_cut_by_company_for_a_head(db, firm):
    for company, amount in ((firm.us, 500_000), (firm.india, 200_000)):
        client = Client(tenant_id=1, company_name=f"C {_uid()}", business_unit_id=firm.axion.id,
                        contracting_company_id=company.id)
        db.add(client)
        db.flush()
        invoice = Invoice(tenant_id=1, client_id=client.id, billing_period_start=SEPT[0], billing_period_end=SEPT[1],
                          currency="USD", total_usd_cents=amount, status="PAID")
        db.add(invoice)
        db.flush()
        db.add(BankTransaction(tenant_id=1, transaction_date=date(2026, 9, 20), amount_usd_cents=amount,
                               description="UTR", matched_invoice_id=invoice.id, reconciled=True))
        db.add(Employee(tenant_id=1, first_name="E", last_name=_uid(), email=f"{_uid()}@x.com",
                        joining_date=date(2025, 1, 1), status="BENCH", bu_id=firm.axion.id, company_id=company.id,
                        base_salary_usd_cents=amount))
    db.commit()

    def axion(user):
        report = outlook(db, start=SEPT[0], end=SEPT[1], today=date(2026, 9, 30),
                         scope=get_user_data_scope(db, user))
        return next(r for r in report["by_business_unit"] if r["key"] == firm.axion.id)

    assert axion(firm.troy)["actual_revenue"] == 700_000
    assert axion(firm.hemant)["actual_revenue"] == 200_000
    assert axion(firm.hemant)["anticipated_bench_cost"] == 200_000


def test_revenue_client_list_is_cut_by_company_for_a_head(db, firm):
    us_client = Client(tenant_id=1, company_name=f"US {_uid()}", business_unit_id=firm.axion.id,
                       contracting_company_id=firm.us.id)
    in_client = Client(tenant_id=1, company_name=f"IN {_uid()}", business_unit_id=firm.axion.id,
                       contracting_company_id=firm.india.id)
    db.add_all([us_client, in_client])
    db.flush()
    visible = {c.id for c in apply_revenue_bu_scope_to_client_query(db, db.query(Client), firm.hemant)}
    assert in_client.id in visible and us_client.id not in visible


def test_old_single_head_is_carried_into_each_company_once(db, firm):
    prism = BusinessUnit(name=f"PRISM-{_uid()}", display_name="PRISM", manager_id=firm.hemant.UserID)
    lonely = BusinessUnit(name=f"SOLO-{_uid()}", display_name="SOLO", manager_id=firm.hemant.UserID)
    db.add_all([prism, lonely])
    db.flush()
    db.add(BusinessUnitCompany(tenant_id=1, business_unit_id=prism.id, company_id=firm.india.id))
    db.commit()
    bu_leadership.carry_over_single_heads(db)
    db.refresh(prism)
    db.refresh(lonely)
    assert bu_leadership.head_user_id(db, prism.id, firm.india.id) == firm.hemant.UserID
    assert prism.manager_id is None
    assert lonely.manager_id == firm.hemant.UserID  # no company to put the head in: kept, logged
    assert db.query(BusinessUnitLocationHead).filter_by(business_unit_id=lonely.id).count() == 0
