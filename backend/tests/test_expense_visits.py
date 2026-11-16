"""CEO 2026-11-14: one visit or event groups its spend; every receipt becomes its own line, described by its person;
My Expenses shows the visit as one row that opens to add, remove, edit and see each line."""
import json

import pytest

from app.core.config import settings
from app.models.expense import ExpenseRecord, ExpenseVisit, ExpenseVisitDraft
from app.models.task import Task
from app.services.expense_receipt_service import ReceiptError
from app.services.expense_service import ExpenseValidationError
from app.services import expense_visit_service as visits
from tests.test_expense_review_and_pnl import EXPENSES, PNG, _logger, api, db, reads, w  # noqa: F401

VISITS = f"{EXPENSES}/visits"


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))


def _visit(db, w, user, **kw):
    fields = {"name": "Seattle - client visit", "purpose": "CLIENT_CURRENT", "spend_for": "CLIENT",
              "client_id": w.client_a.id, **kw}
    return visits.create_visit(db, user, **fields)


def _with_receipts(db, visit, *readings):
    with reads(*readings):
        return visits.add_receipts(db, visit, [(f"r{i}.png", "image/png", PNG) for i in range(len(readings))])


def _describe(db, visit, draft, user, cents=5_000, what="Taxi to client", on="2026-09-10"):
    from datetime import date

    with reads({"total": cents / 100, "date": on}):
        return visits.submit_draft(db, visit, draft, user, description=what, expense_category="TRAVEL",
                                   travel_type="GROUND_TRANSPORT", amount_usd_cents=cents,
                                   expense_date=date.fromisoformat(on))


def test_each_receipt_waits_for_its_description_filled_in_from_the_receipt(db, w):
    user = _logger(db, w, manager=w.partner_a)
    visit = _visit(db, w, user)
    drafts = _with_receipts(db, visit, {"total": 42.5, "date": "2026-09-10", "merchant": "Cab Co"},
                            {"total": 300.0, "date": "2026-09-11"}, {"total": None})
    assert len(drafts) == 3
    first = visits.draft_prefill(drafts[0])
    assert first["amount_usd_cents"] == 4250 and first["expense_date"] == "2026-09-10" and first["merchant"] == "Cab Co"
    assert visits.draft_prefill(drafts[2])["amount_usd_cents"] is None
    # waiting receipts are no expense yet: nothing in the P&L, nothing with the manager
    assert db.query(ExpenseRecord).filter(ExpenseRecord.visit_id == visit.id).count() == 0
    assert visits.visit_detail(visit)["status"] == "NEEDS_DETAILS"


def test_a_described_receipt_becomes_its_own_line_with_the_visits_client(db, w):
    user = _logger(db, w, manager=w.partner_a)
    visit = _visit(db, w, user)
    drafts = _with_receipts(db, visit, {"total": 50.0, "date": "2026-09-10"}, {"total": 120.0, "date": "2026-09-11"})
    taxi = _describe(db, visit, drafts[0], user)
    hotel = _describe(db, visit, drafts[1], user, cents=12_000, what="Hotel", on="2026-09-11")
    for line in (taxi, hotel):
        assert line.visit_id == visit.id and line.trip_label == visit.name
        assert line.client_id == w.client_a.id and line.spend_for == "CLIENT"
        assert [r.file_name for r in line.receipts] and line.receipt_check_status == "MATCHED"
    assert taxi.description == "Taxi to client" and hotel.amount_usd_cents == 12_000
    db.refresh(visit)
    detail = visits.visit_detail(visit)
    assert detail["total_usd_cents"] == 17_000 and len(detail["lines"]) == 2 and detail["drafts"] == []
    assert db.query(ExpenseVisitDraft).count() == 0


def test_a_split_visit_splits_every_line_the_same_way(db, w):
    user = _logger(db, w)
    visit = visits.create_visit(db, user, name="Two-client trip", purpose="OTHER", spend_for="SPLIT",
                                client_splits=[{"client_id": w.client_a.id, "percent": 60},
                                               {"client_id": w.client_b.id, "percent": 40}])
    line = _describe(db, visit, _with_receipts(db, visit, {"total": 100.0})[0], user, cents=10_000)
    assert sorted(s.share_bps for s in line.client_shares) == [4000, 6000]


def test_a_visit_split_by_amount_is_refused(db, w):
    user = _logger(db, w)
    with pytest.raises(ExpenseValidationError, match="percent"):
        visits.create_visit(db, user, name="x", purpose="OTHER", spend_for="SPLIT",
                            client_splits=[{"client_id": w.client_a.id, "amount_usd_cents": 1},
                                           {"client_id": w.client_b.id, "amount_usd_cents": 1}])


def test_a_receipt_needs_its_description(db, w):
    user = _logger(db, w)
    visit = _visit(db, w, user)
    draft = _with_receipts(db, visit, {"total": 10.0})[0]
    with pytest.raises(ExpenseValidationError, match="what this receipt was for"):
        _describe(db, visit, draft, user, what="  ")
    assert db.query(ExpenseVisitDraft).count() == 1


def test_a_bad_file_refuses_the_whole_batch(db, w):
    user = _logger(db, w)
    visit = _visit(db, w, user)
    with pytest.raises(ReceiptError):
        visits.add_receipts(db, visit, [("a.png", "image/png", PNG), ("b.exe", "application/x-msdownload", b"MZ")])
    assert db.query(ExpenseVisitDraft).count() == 0


def test_a_line_can_be_removed_until_finance_approves_it(db, w):
    user = _logger(db, w, manager=w.partner_a)
    visit = _visit(db, w, user)
    line = _describe(db, visit, _with_receipts(db, visit, {"total": 99.0})[0], user, cents=7_000)
    line_id = line.id
    assert db.query(Task).filter(Task.expense_id == line_id).count() >= 1
    visits.remove_line(db, line, user)
    assert db.get(ExpenseRecord, line_id) is None
    assert db.query(Task).filter(Task.expense_id == line_id, Task.status != "COMPLETED").count() == 0
    approved = _describe(db, visit, _with_receipts(db, visit, {"total": 50.0})[0], user)
    approved.payment_status = "APPROVED"
    db.commit()
    with pytest.raises(ExpenseValidationError, match="Finance has approved"):
        visits.remove_line(db, approved, user)


def test_renaming_the_visit_renames_its_lines(db, w):
    user = _logger(db, w)
    visit = _visit(db, w, user)
    line = _describe(db, visit, _with_receipts(db, visit, {"total": 50.0})[0], user)
    visits.update_visit(db, visit, name="Seattle - Goldenbear - Sep 2026")
    db.refresh(line)
    assert line.trip_label == "Seattle - Goldenbear - Sep 2026"


def test_lines_already_logged_under_one_trip_label_become_one_visit(db, w):
    from app.services.expense_service import log_expense
    from datetime import date

    user = _logger(db, w)
    other = _logger(db, w)
    for person, label, day in ((user, "NAMIC trip", 10), (user, "namic trip ", 11), (other, "NAMIC trip", 10),
                               (user, None, 12)):
        log_expense(db, logged_by_user=person, purpose="OTHER", spend_for="INTERNAL", expense_category="TRAVEL",
                    amount_usd_cents=1_000, expense_date=date(2026, 9, day), receipt_ref="r", trip_label=label)
    assert visits.group_existing_trips(db) == 3
    mine = db.query(ExpenseVisit).filter(ExpenseVisit.owner_user_id == user.UserID).all()
    assert len(mine) == 1 and len(mine[0].lines) == 2 and str(mine[0].end_date) == "2026-09-11"
    assert db.query(ExpenseVisit).filter(ExpenseVisit.owner_user_id == other.UserID).count() == 1


# ---- the endpoints
def test_the_visit_screen_flow_over_the_api(db, w, api):
    user = _logger(db, w, manager=w.partner_a)
    created = api.post(user, VISITS, json={"name": "Chicago visit", "purpose": "CLIENT_CURRENT",
                                           "spend_for": "CLIENT", "client_id": w.client_a.id})
    assert created.status_code == 201, created.text
    visit_id = created.json()["id"]
    with reads({"total": 25.0, "date": "2026-09-10"}, {"total": 80.0, "date": "2026-09-10"}):
        added = api.post(user, f"{VISITS}/{visit_id}/receipts",
                         files=[("files", ("a.png", PNG, "image/png")), ("files", ("b.png", PNG, "image/png"))])
    assert added.status_code == 200, added.text
    drafts = added.json()
    assert [d["amount_usd_cents"] for d in drafts] == [2500, 8000]
    with reads({"total": 25.0, "date": "2026-09-10"}):
        line = api.post(user, f"{VISITS}/{visit_id}/drafts/{drafts[0]['id']}",
                        json={"description": "Lunch with client", "expense_category": "MEALS",
                              "amount_usd_cents": 2500, "expense_date": "2026-09-10"})
    assert line.status_code == 200, line.text
    assert line.json()["visit_name"] == "Chicago visit"
    assert api.delete(user, f"{VISITS}/{visit_id}/drafts/{drafts[1]['id']}").status_code == 200
    detail = api.get(user, f"{VISITS}/{visit_id}").json()
    assert detail["total_usd_cents"] == 2500 and len(detail["lines"]) == 1 and detail["drafts"] == []
    mine = api.get(user, f"{EXPENSES}/mine").json()["expenses"]
    assert [(e["visit_id"], e["visit_name"]) for e in mine] == [(visit_id, "Chicago visit")]
    assert api.delete(user, f"{EXPENSES}/{line.json()['id']}").status_code == 204
    assert api.get(user, f"{VISITS}/{visit_id}").json()["lines"] == []


def test_someone_elses_visit_is_not_found(db, w, api):
    user = _logger(db, w)
    visit = _visit(db, w, user)
    stranger = _logger(db, w)
    assert api.get(stranger, f"{VISITS}/{visit.id}").status_code == 404
    with reads({"total": 1.0}):
        assert api.post(stranger, f"{VISITS}/{visit.id}/receipts",
                        files=[("files", ("a.png", PNG, "image/png"))]).status_code == 404
