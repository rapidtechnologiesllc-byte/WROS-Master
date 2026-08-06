"""
Avinash, 2026-08-05: "when Troy adds a new client he earns a $10K
incentive after MSA is signed and first revenue invoice... this is not
applicable to Curtis... when we add more sales people in the future we
need to also check if they are eligible." Proves the rule is genuinely
data-driven -- Curtis stays ineligible for NEW_LOGO_BONUS purely
because he has no rule row, no special-case code anywhere.

Throwaway SQLite -- never the real database.
"""
import os
import tempfile
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.client import Client
from app.models.invoice import Invoice
from app.models.project import Project
from app.models.rbac import BusinessUnit
from app.models.tenant import Tenant
from app.models.user import Users
from app.services.partner_incentive_service import check_new_logo_incentive, create_incentive_rule


@pytest.fixture()
def db_session():
    fd, db_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        os.remove(db_path)


@pytest.fixture()
def world(db_session):
    tenant = Tenant(name="BlitzenX")
    db_session.add(tenant)
    db_session.commit()

    axion = BusinessUnit(name="Axion")
    prism = BusinessUnit(name="PRISM")
    db_session.add_all([axion, prism])
    db_session.commit()

    troy = Users(UserID="troy", UserRole="Partner", UserEmail="troy@blitzenx.com", UserPassword="h", tenant_id=tenant.id, business_unit_id=axion.id)
    curtis = Users(UserID="curtis", UserRole="Partner", UserEmail="curtis@blitzenx.com", UserPassword="h", tenant_id=tenant.id, business_unit_id=prism.id)
    db_session.add_all([troy, curtis])
    db_session.commit()

    create_incentive_rule(
        db_session, partner_user_id="troy", incentive_type="NEW_LOGO_BONUS",
        amount_usd_cents=1000000, trigger_description="MSA signed AND first revenue invoice",
    )
    # Curtis deliberately gets no NEW_LOGO_BONUS rule -- his mechanism
    # (revenue share) is structurally different, per Avinash directly.

    return {"tenant": tenant, "axion": axion, "prism": prism, "troy": troy, "curtis": curtis}


def _make_client(db, name, bu_id, *, contract_start_date=None):
    client = Client(company_name=name, business_unit_id=bu_id, status="ACTIVE", contract_start_date=contract_start_date)
    db.add(client)
    db.commit()
    return client


def _make_invoice(db, client):
    project = Project(client_id=client.id, name=f"{client.company_name} Engagement", status="ACTIVE", billing_type="TIME_AND_MATERIALS")
    db.add(project)
    db.commit()
    invoice = Invoice(
        client_id=client.id, project_id=project.id, status="SENT", total_usd_cents=50000,
        billing_period_start=date(2026, 8, 1), billing_period_end=date(2026, 8, 31),
    )
    db.add(invoice)
    db.commit()
    return invoice


def test_no_incentive_without_msa_signed(db_session, world):
    builders = _make_client(db_session, "Builders", world["axion"].id, contract_start_date=None)
    _make_invoice(db_session, builders)

    event = check_new_logo_incentive(db_session, builders)
    assert event is None


def test_no_incentive_without_invoice(db_session, world):
    builders = _make_client(db_session, "Builders", world["axion"].id, contract_start_date=date(2026, 7, 1))
    event = check_new_logo_incentive(db_session, builders)
    assert event is None


def test_troy_earns_new_logo_incentive(db_session, world):
    builders = _make_client(db_session, "Builders", world["axion"].id, contract_start_date=date(2026, 7, 1))
    _make_invoice(db_session, builders)

    event = check_new_logo_incentive(db_session, builders)

    assert event is not None
    assert event.partner_user_id == "troy"
    assert event.amount_usd_cents == 1000000
    assert event.status == "PENDING"


def test_curtis_never_eligible_for_new_logo_no_rule_exists(db_session, world):
    """The real proof of Avinash's rule: Curtis's client goes through
    the exact same MSA+invoice conditions as Troy's and still produces
    nothing, purely because he has no NEW_LOGO_BONUS rule row."""
    alfa = _make_client(db_session, "Alfa Insurance", world["prism"].id, contract_start_date=date(2026, 7, 1))
    _make_invoice(db_session, alfa)

    event = check_new_logo_incentive(db_session, alfa)
    assert event is None


def test_idempotent_never_double_pays(db_session, world):
    builders = _make_client(db_session, "Builders", world["axion"].id, contract_start_date=date(2026, 7, 1))
    _make_invoice(db_session, builders)

    first = check_new_logo_incentive(db_session, builders)
    second = check_new_logo_incentive(db_session, builders)

    assert first.id == second.id


def test_idempotency_enforced_at_db_level_not_just_application_check(db_session, world):
    """The real race this closes: two concurrent callers both pass the
    "does an event already exist" check before either has committed,
    and both try to insert. Proven directly by bypassing the
    check-then-insert order and inserting a second row by hand -- the
    UNIQUE constraint on (rule_id, client_id) must reject it, not the
    application logic (which can't protect against this by construction)."""
    from sqlalchemy.exc import IntegrityError
    from app.models.partner_incentive import PartnerIncentiveEvent, PartnerIncentiveRule

    builders = _make_client(db_session, "Builders", world["axion"].id, contract_start_date=date(2026, 7, 1))
    _make_invoice(db_session, builders)
    first = check_new_logo_incentive(db_session, builders)

    rule = db_session.query(PartnerIncentiveRule).filter(PartnerIncentiveRule.partner_user_id == "troy").first()
    duplicate = PartnerIncentiveEvent(
        rule_id=rule.id, partner_user_id="troy", client_id=builders.id, amount_usd_cents=1000000,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # First event is untouched.
    assert db_session.query(PartnerIncentiveEvent).filter(PartnerIncentiveEvent.client_id == builders.id).count() == 1


def test_future_sales_hire_becomes_eligible_by_getting_a_rule(db_session, world):
    """Avinash: "when we add more sales people in the future we need to
    also check if they are eligible... and the amount and mechanism."
    A brand-new AXION salesperson with their own rule earns their own
    configured amount -- nothing hardcoded to Troy specifically."""
    new_hire = Users(UserID="newsales", UserRole="Partner", UserEmail="newsales@blitzenx.com", UserPassword="h", tenant_id=world["tenant"].id, business_unit_id=world["prism"].id)
    db_session.add(new_hire)
    db_session.commit()
    # Reassign PRISM's resolved Partner to the new hire for this test by
    # removing Curtis's Partner role -- simplest way to prove BU-based
    # resolution without adding a second BU.
    world["curtis"].UserRole = "BU Head"
    db_session.add(world["curtis"])
    db_session.commit()

    create_incentive_rule(
        db_session, partner_user_id="newsales", incentive_type="NEW_LOGO_BONUS",
        amount_usd_cents=500000, trigger_description="MSA signed AND first revenue invoice",
    )

    goldenbear = _make_client(db_session, "Goldenbear", world["prism"].id, contract_start_date=date(2026, 8, 1))
    _make_invoice(db_session, goldenbear)

    event = check_new_logo_incentive(db_session, goldenbear)

    assert event is not None
    assert event.partner_user_id == "newsales"
    assert event.amount_usd_cents == 500000
