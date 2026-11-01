"""Who an expense is on, and one event per conference (CEO 2026-10-31).

"if the purpose is conference ... ask which client is this expense on" -- every expense says
whether it is internal, on one client, or split across clients (the split totals 100%), with
clients only from the person's tenant and business units; the P&L carries each client's part.
"when we give 1 conference name ... all team members use same or similar details to have the
record built into 1 event" -- conferences are shared events, matched across spellings, and the
team's spend rolls up to one event per client and per person."""
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.expense import ExpenseEvent, ExpenseRecord
from app.services import expense_event_service as events
from app.services import expense_service as expenses
from app.services.expense_service import ExpenseValidationError
from tests.scope_fixtures import ApiClient, ids, person, two_bu_world, uid

ON = date(2026, 10, 5)
SEPT_OCT = (date(2026, 9, 1), date(2026, 10, 31))


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
    world.seller_a = person(db, world.partner_role, "Seller A", business_unit_id=world.bu_a.id)
    db.commit()
    return world


@pytest.fixture
def api(db):
    client = ApiClient(db)
    yield client
    client.close()


def conference(db, user, name=None):
    event, _ = events.find_or_create_event(db, tenant_id=1, name=name or f"Conf {uid()} 2026",
                                           created_by_user_id=user.UserID)
    db.commit()
    return event


def log(db, user, cents=10_000, purpose="CONFERENCE", event=None, **kw):
    return expenses.log_expense(db, logged_by_user=user, purpose=purpose, expense_category="MEALS",
                                amount_usd_cents=cents, expense_date=ON, receipt_ref="r",
                                event_id=event.id if event else None, **kw)


# --- who the spend is on --------------------------------------------------------------------

def test_conference_spend_must_say_who_it_is_on(db, w):
    event = conference(db, w.seller_a)
    with pytest.raises(ExpenseValidationError, match="must say who it is on"):
        log(db, w.seller_a, event=event)
    alone = log(db, w.seller_a, event=event, spend_for="INTERNAL")
    assert alone.spend_for == "INTERNAL" and alone.client_id is None and alone.client_shares == []
    assert alone.conference_name == event.name


def test_one_client_carries_the_whole_amount(db, w):
    e = log(db, w.seller_a, event=conference(db, w.seller_a), spend_for="CLIENT", client_id=w.client_a.id)
    assert e.client_id == w.client_a.id
    assert [(s.client_id, s.share_bps, s.amount_usd_cents) for s in e.client_shares] == [(w.client_a.id, 10000, 10_000)]


def test_split_by_percent_totals_exactly_and_must_be_100(db, w):
    event = conference(db, w.org_user)
    e = log(db, w.org_user, cents=10_001, event=event, spend_for="SPLIT", client_splits=[
        {"client_id": w.client_a.id, "percent": 33.33}, {"client_id": w.client_b.id, "percent": 33.33},
        {"client_id": w.prospect.id, "percent": 33.34}])
    assert e.client_id is None
    assert sum(s.amount_usd_cents for s in e.client_shares) == 10_001
    assert sum(s.share_bps for s in e.client_shares) == 10000
    with pytest.raises(ExpenseValidationError, match="100%"):
        log(db, w.org_user, event=event, spend_for="SPLIT", client_splits=[
            {"client_id": w.client_a.id, "percent": 60}, {"client_id": w.client_b.id, "percent": 30}])


def test_split_by_amount_must_total_the_expense(db, w):
    event = conference(db, w.org_user)
    e = log(db, w.org_user, cents=9_000, event=event, spend_for="SPLIT", client_splits=[
        {"client_id": w.client_a.id, "amount_usd_cents": 6_000},
        {"client_id": w.client_b.id, "amount_usd_cents": 3_000}])
    assert {s.client_id: (s.amount_usd_cents, s.share_bps) for s in e.client_shares} == {
        w.client_a.id: (6_000, 6666), w.client_b.id: (3_000, 3334)}
    for bad in ([{"client_id": w.client_a.id, "amount_usd_cents": 9_000}],  # one line is not a split
                [{"client_id": w.client_a.id, "amount_usd_cents": 5_000},
                 {"client_id": w.client_b.id, "amount_usd_cents": 3_000}],  # short of the total
                [{"client_id": w.client_a.id, "amount_usd_cents": 4_500},
                 {"client_id": w.client_a.id, "amount_usd_cents": 4_500}],  # same client twice
                [{"client_id": w.client_a.id, "percent": 50},
                 {"client_id": w.client_b.id, "amount_usd_cents": 4_500}]):  # mixed modes
        with pytest.raises(ExpenseValidationError):
            log(db, w.org_user, cents=9_000, event=event, spend_for="SPLIT", client_splits=bad)


def test_purpose_rules(db, w):
    with pytest.raises(ExpenseValidationError, match="pick the client"):
        log(db, w.seller_a, purpose="CLIENT_CURRENT", spend_for="INTERNAL")
    with pytest.raises(ExpenseValidationError, match="internal"):
        log(db, w.seller_a, purpose="INVESTMENT", investment_label="x", spend_for="CLIENT", client_id=w.client_a.id)
    with pytest.raises(ExpenseValidationError, match="event"):
        log(db, w.seller_a, spend_for="INTERNAL")  # a conference without its event
    with pytest.raises(ExpenseValidationError, match="Only a conference"):
        log(db, w.seller_a, purpose="OTHER", event=conference(db, w.seller_a))
    client_meal = log(db, w.seller_a, purpose="CLIENT_CURRENT", client_id=w.client_a.id)
    assert client_meal.spend_for == "CLIENT"  # naming the client says who it is on
    assert log(db, w.seller_a, purpose="OTHER", spend_for="INTERNAL").spend_for == "INTERNAL"


def test_every_expense_must_say_client_or_personal(db, w):
    """CEO 2026-10-31: "on every expense we need to identify which client it is for or if it is
    for personal use" -- nothing is defaulted to internal."""
    for purpose, extra in (("OTHER", {}), ("CLIENT_CURRENT", {}), ("CLIENT_PROSPECT", {}),
                           ("INVESTMENT", {"investment_label": "x"})):
        with pytest.raises(ExpenseValidationError, match="must say who it is on"):
            log(db, w.seller_a, purpose=purpose, **extra)
    with pytest.raises(ExpenseValidationError, match="must say who it is on"):
        log(db, w.seller_a, event=conference(db, w.seller_a))
    assert log(db, w.seller_a, purpose="INVESTMENT", investment_label="x", spend_for="INTERNAL").spend_for == "INTERNAL"
    assert log(db, w.seller_a, purpose="OTHER", spend_for="CLIENT", client_id=w.client_a.id).client_id == w.client_a.id


def test_clients_come_from_the_persons_tenant_and_business_units(db, w):
    from app.models.client import Client

    event = conference(db, w.seller_a)
    with pytest.raises(ExpenseValidationError, match="not found"):  # another BU's client
        log(db, w.seller_a, event=event, spend_for="CLIENT", client_id=w.client_b.id)
    with pytest.raises(ExpenseValidationError, match="not found"):
        log(db, w.seller_a, event=event, spend_for="SPLIT", client_splits=[
            {"client_id": w.client_a.id, "percent": 50}, {"client_id": w.client_b.id, "percent": 50}])
    other_tenant = Client(tenant_id=None, company_name=f"Not this tenant {uid()}")
    db.add(other_tenant)
    db.flush()
    with pytest.raises(ExpenseValidationError, match="not found"):
        log(db, w.org_user, event=event, spend_for="CLIENT", client_id=other_tenant.id)
    # a prospect not yet in any BU is open to everyone
    assert log(db, w.seller_a, event=event, spend_for="SPLIT", client_splits=[
        {"client_id": w.client_a.id, "percent": 50}, {"client_id": w.prospect.id, "percent": 50}]).spend_for == "SPLIT"


def test_attribution_is_corrected_before_the_decision_and_locked_after(db, w):
    e = log(db, w.seller_a, event=conference(db, w.seller_a), spend_for="INTERNAL")
    e = expenses.update_attribution(db, e, w.seller_a, spend_for="CLIENT", client_id=w.client_a.id)
    assert e.client_id == w.client_a.id and len(e.client_shares) == 1
    e = expenses.update_attribution(db, e, w.org_user, spend_for="SPLIT", client_splits=[
        {"client_id": w.client_a.id, "percent": 25}, {"client_id": w.client_b.id, "percent": 75}])
    assert e.client_id is None and sorted(s.share_bps for s in e.client_shares) == [2500, 7500]
    expenses.approve_manager_step(db, e, approved_by=w.org_user.UserID)
    with pytest.raises(PermissionError):
        expenses.update_attribution(db, e, w.seller_a, spend_for="INTERNAL")


def test_an_expense_that_does_not_say_who_it_is_on_is_not_approved(db, w):
    e = log(db, w.seller_a, purpose="OTHER", spend_for="INTERNAL")
    e.spend_for = None  # an old row the backfill has not reached
    db.flush()
    with pytest.raises(ExpenseValidationError, match="who the spend is on"):
        expenses.approve_manager_step(db, e, approved_by=w.org_user.UserID)


# --- one event per conference ---------------------------------------------------------------

def test_spellings_of_one_conference_are_one_event(db, w):
    first, created = events.find_or_create_event(db, tenant_id=1, name=f"NAMIC{uid()} 2026")
    assert created
    base = first.name.split(" ")[0]
    for spelling in (f"{base.lower()}-2026", f"  {base.upper()}   2026 ", f"{base}, 2026"):
        same, created = events.find_or_create_event(db, tenant_id=1, name=spelling)
        assert same.id == first.id and not created
    next_year, created = events.find_or_create_event(db, tenant_id=1, name=f"{base} 2027")
    assert created and next_year.id != first.id
    assert events.event_key("NAMIC 2026") == events.event_key("Namic-2026") == ("namic", 2026)


def test_a_near_duplicate_is_refused_until_confirmed(db, w):
    base = f"Guidewire Connections {uid()}"
    original, _ = events.find_or_create_event(db, tenant_id=1, name=f"{base} 2026")
    with pytest.raises(events.NearDuplicateEventError) as exc:
        events.find_or_create_event(db, tenant_id=1, name=f"{base} Conf 2026")
    assert [m.id for m in exc.value.matches] == [original.id]
    different, created = events.find_or_create_event(db, tenant_id=1, name=f"{base} Conf 2026", confirm_new=True)
    assert created and different.id != original.id


def test_typeahead_finds_the_event_from_a_partial_or_different_spelling(db, w):
    tag = uid()
    event, _ = events.find_or_create_event(db, tenant_id=1, name=f"Insurtech{tag} Connect 2026",
                                           start_date=date(2026, 6, 1), location="Las Vegas")
    for query in (f"insurtech{tag}", f"InsurTech{tag}-Connect", f"insurtech{tag} connect 2026"):
        found = [e.id for e, _ in events.search_events(db, 1, query)]
        assert found and found[0] == event.id, query
    assert event.id not in [e.id for e, _ in events.search_events(db, 1, f"insurtech{tag}", year=2025)]


def test_merging_moves_the_teams_expenses_to_one_event(db, w):
    tag = uid()
    a, _ = events.find_or_create_event(db, tenant_id=1, name=f"Summit{tag} 2026")
    b, _ = events.find_or_create_event(db, tenant_id=1, name=f"Summit{tag} East 2026", confirm_new=True)
    e1 = log(db, w.seller_a, event=a, spend_for="INTERNAL")
    e2 = log(db, w.org_user, event=b, spend_for="INTERNAL")
    assert events.merge_events(db, b, a) == 1
    db.refresh(e2)
    assert e1.event_id == e2.event_id == a.id and e2.conference_name == a.name
    assert events.live_event(db, b).id == a.id
    assert b.id not in [e.id for e, _ in events.search_events(db, 1, f"summit{tag}")]


def test_the_backfill_turns_free_text_conferences_into_shared_events(db, w):
    from app.core.db_contract import _expense_attribution_and_events

    tag = uid()
    legacy = [ExpenseRecord(tenant_id=1, logged_by_user_id=w.seller_a.UserID, purpose="CONFERENCE",
                            conference_name=name, expense_category="MEALS", amount_usd_cents=100,
                            receipt_ref="r", expense_date=ON)
              for name in (f"Namic{tag} 2026", f"NAMIC{tag}-2026", f"namic{tag}")]
    client_meal = ExpenseRecord(tenant_id=1, logged_by_user_id=w.seller_a.UserID, purpose="CLIENT_CURRENT",
                                client_id=w.client_a.id, expense_category="MEALS", amount_usd_cents=700,
                                receipt_ref="r", expense_date=ON)
    db.add_all(legacy + [client_meal])
    db.flush()
    _expense_attribution_and_events(db)
    assert len({e.event_id for e in legacy}) == 1 and legacy[0].event_id  # the year-less one used the date's year
    assert {e.spend_for for e in legacy} == {"INTERNAL"}
    assert client_meal.spend_for == "CLIENT"
    assert [(s.client_id, s.amount_usd_cents) for s in client_meal.client_shares] == [(w.client_a.id, 700)]


# --- the P&L and the event rollup carry each client's part -------------------------------------

def test_pnl_puts_each_client_part_in_its_business_unit(db, w):
    from app.services.revenue_chain_service import _expenses

    event = conference(db, w.org_user)
    split = log(db, w.org_user, cents=10_000, event=event, spend_for="SPLIT", client_splits=[
        {"client_id": w.client_a.id, "percent": 70}, {"client_id": w.client_b.id, "percent": 30}])
    pending = log(db, w.org_user, cents=500, event=event, spend_for="CLIENT", client_id=w.client_b.id)
    rejected = log(db, w.org_user, cents=999, event=event, spend_for="CLIENT", client_id=w.client_a.id)
    expenses.approve_manager_step(db, split, approved_by=w.partner_a.UserID)
    expenses.reject_manager_step(db, rejected, rejected_by=w.partner_a.UserID)
    units = {w.bu_a.id: w.bu_a, w.bu_b.id: w.bu_b}
    rows, pending_total = _expenses(db, *SEPT_OCT, 1, units, {w.bu_a.id, w.bu_b.id})
    ours = {r["key"]: r["amount"] for r in rows if r["key"][2] in (w.client_a.id, w.client_b.id)}
    assert ours == {(w.partner_a.UserID, w.bu_a.id, w.client_a.id): 7_000,
                    (w.partner_b.UserID, w.bu_b.id, w.client_b.id): 3_000}
    assert pending_total >= pending.amount_usd_cents
    only_b, _ = _expenses(db, *SEPT_OCT, 1, units, {w.bu_b.id})
    assert sum(r["amount"] for r in only_b if r["key"][2] == w.client_b.id) == 3_000


def test_investment_position_counts_only_the_clients_part(db, w):
    event = conference(db, w.org_user)
    log(db, w.org_user, cents=10_000, event=event, spend_for="SPLIT", client_splits=[
        {"client_id": w.client_a.id, "percent": 40}, {"client_id": w.client_b.id, "percent": 60}])
    rejected = log(db, w.org_user, cents=5_000, purpose="CLIENT_CURRENT", client_id=w.client_a.id)
    expenses.reject_manager_step(db, rejected, rejected_by=w.partner_a.UserID)
    position = expenses.get_client_investment_position(db, w.client_a.id)
    assert position["total_expense_usd_cents"] == 4_000 and position["expense_count"] == 1


def test_event_rollup_totals_per_client_and_per_person(db, w):
    event = conference(db, w.org_user)
    log(db, w.seller_a, cents=1_000, event=event, spend_for="INTERNAL")
    log(db, w.seller_a, cents=2_000, event=event, spend_for="CLIENT", client_id=w.client_a.id)
    log(db, w.org_user, cents=4_000, event=event, spend_for="SPLIT", client_splits=[
        {"client_id": w.client_a.id, "percent": 50}, {"client_id": w.client_b.id, "percent": 50}])
    records = db.query(ExpenseRecord).filter(ExpenseRecord.event_id == event.id).all()
    summary = events.event_rollup(db, event, records)
    assert summary["total_usd_cents"] == 7_000 and summary["expense_count"] == 3
    assert {r["client_id"]: r["amount_usd_cents"] for r in summary["by_client"]} == {
        None: 1_000, w.client_a.id: 4_000, w.client_b.id: 2_000}
    assert {r["user_id"]: r["amount_usd_cents"] for r in summary["by_person"]} == {
        w.seller_a.UserID: 3_000, w.org_user.UserID: 4_000}


# --- API --------------------------------------------------------------------------------------

def test_api_pick_or_add_event_then_log_split_and_see_it_scoped(db, w, api):
    tag = uid()
    made = api.post(w.seller_a, "/api/v1/expense-events", json={"name": f"Namic{tag} 2026", "location": "Austin"})
    assert made.status_code == 200 and made.json()["created"] is True
    again = api.post(w.org_user, "/api/v1/expense-events", json={"name": f"NAMIC{tag}-2026"})
    assert again.json()["id"] == made.json()["id"] and again.json()["created"] is False
    near = api.post(w.org_user, "/api/v1/expense-events", json={"name": f"Namic{tag} Annual 2026"})
    assert near.status_code == 409 and near.json()["detail"]["matches"][0]["id"] == made.json()["id"]
    found = api.get(w.seller_a, "/api/v1/expense-events", params={"q": f"namic{tag[:4]}"})
    assert made.json()["id"] in ids(found.json())

    body = {"purpose": "CONFERENCE", "expense_category": "MEALS", "amount_usd_cents": 8_000,
            "expense_date": ON.isoformat(), "receipt_ref": "r", "event_id": made.json()["id"]}
    assert api.post(w.seller_a, "/api/v1/expenses", json=body).status_code == 400  # who is it on?
    other_bu = {**body, "spend_for": "SPLIT", "client_splits": [
        {"client_id": w.client_a.id, "percent": 50}, {"client_id": w.client_b.id, "percent": 50}]}
    assert api.post(w.seller_a, "/api/v1/expenses", json=other_bu).status_code == 400
    split = api.post(w.org_user, "/api/v1/expenses", json=other_bu)
    assert split.status_code == 201 and len(split.json()["client_shares"]) == 2
    # a split is visible to every BU one of its clients is in, and filters by either client
    assert split.json()["id"] in ids(api.get(w.partner_b, "/api/v1/expenses").json())
    assert split.json()["id"] in ids(api.get(w.partner_a, "/api/v1/expenses",
                                             params={"client_id": w.client_a.id}).json())
    summary = api.get(w.org_user, f"/api/v1/expense-events/{made.json()['id']}/summary")
    assert summary.status_code == 200 and summary.json()["total_usd_cents"] == 8_000


def test_api_attribution_edit_follows_the_same_rules(db, w, api):
    event = conference(db, w.seller_a)
    e = log(db, w.seller_a, event=event, spend_for="INTERNAL")
    path = f"/api/v1/expenses/{e.id}/attribution"
    assert api.patch(w.seller_a, path, json={"spend_for": "CLIENT", "client_id": w.client_b.id}).status_code == 400
    ok = api.patch(w.seller_a, path, json={"spend_for": "CLIENT", "client_id": w.client_a.id})
    assert ok.status_code == 200 and ok.json()["client_id"] == w.client_a.id
    assert api.patch(w.partner_b, path, json={"spend_for": "INTERNAL"}).status_code == 404


def test_guidewire_connections_client_meals_and_attendee_spend_land_in_the_right_company(db, w):
    """CEO 2026-11-01: "we went to a conference called Guidewire connections we had 2 types of
    expenses 1, where we took the client to lunch/dinner or other thing is when the attendees ate
    vs travel ... ask if it is client or personal then it has to come into P&L". The client dinner
    is the client's (its BU and contracting company); the attendee's own meal and flight count in
    the company the attendee works for that day -- never the "Group" catch-all."""
    from app.models.employee import Employee
    from app.models.location import Location
    from app.services.revenue_chain_service import _company_pnl, _expenses

    bx_us, bx_in = Location(tenant_id=1, name=f"BX-US {uid()}"), Location(tenant_id=1, name=f"BX-IN {uid()}")
    db.add_all([bx_us, bx_in])
    db.flush()
    w.client_a.contracting_company_id = bx_us.id
    db.add(Employee(first_name="Seller", last_name="A", email=f"{uid()}@emp.test", wros_user_id=w.seller_a.UserID,
                    tenant_id=1, bu_id=w.bu_a.id, company_id=bx_in.id, joining_date=date(2025, 1, 1),
                    status="ACTIVE"))
    db.commit()
    event = conference(db, w.seller_a, name=f"Guidewire Connections {uid()} 2026")
    dinner = log(db, w.seller_a, cents=30_000, event=event, spend_for="CLIENT", client_id=w.client_a.id)
    own_meal = log(db, w.seller_a, cents=4_000, event=event, spend_for="INTERNAL")
    flight = expenses.log_expense(db, logged_by_user=w.seller_a, purpose="CONFERENCE", expense_category="TRAVEL",
                                  travel_type="AIRFARE", amount_usd_cents=50_000, expense_date=ON, receipt_ref="r",
                                  event_id=event.id, spend_for="INTERNAL")
    for expense in (dinner, own_meal, flight):
        expenses.approve_manager_step(db, expense, approved_by=w.partner_a.UserID)
    db.commit()

    rows, _ = _expenses(db, *SEPT_OCT, 1, {w.bu_a.id: w.bu_a, w.bu_b.id: w.bu_b}, {w.bu_a.id})
    ours = [r for r in rows if r["company_id"] in (bx_us.id, bx_in.id)]
    assert sorted((r["key"][2] or "", r["company_id"], r["amount"]) for r in ours) == sorted([
        (w.client_a.id, bx_us.id, 30_000), ("", bx_in.id, 4_000), ("", bx_in.id, 50_000)])
    by_company = {c["key"]: c["expense_cost_usd_cents"] for c in _company_pnl(db, [], {}, ours, *SEPT_OCT, 1)}
    assert by_company[bx_us.id] == 30_000 and by_company[bx_in.id] == 54_000
    assert None not in by_company  # nothing of this conference fell into "Group"
