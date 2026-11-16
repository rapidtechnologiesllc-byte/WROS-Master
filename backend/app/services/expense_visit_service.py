"""Expenses grouped by visit (CEO 2026-11-14): "I went to one event or client visit: everything related to that
visit should be grouped and individual itemized rows should be created for each receipt ... a single row item with
hyper link to click on it and add, remove, edit and see all the individual expense rows".

  create_visit    what every line shares: purpose, who carries it (internal / one client / a split in percent),
                  the conference, the dates and place
  add_receipts    each receipt waits as a draft (ExpenseVisitDraft), read for its amount, date and merchant; a draft
                  is in no P&L and with no manager
  submit_draft    its person describes it: it becomes its own expense line (log_expense), with the receipt
                  attached and checked, and from there goes to the manager like any expense
  remove_line     a line not yet approved by Finance can be taken off (its open tasks are closed)

A line keeps every rule of a single expense (expense_service, expense_receipt_service): approvals, receipt check,
edits, history and the P&L are per line.
"""
import json
import logging
import os
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.expense import SPEND_FOR, ExpenseRecord, ExpenseVisit, ExpenseVisitDraft
from app.models.user import Users
from app.services.expense_service import ExpenseValidationError

logger = logging.getLogger(__name__)

TRIAL_CENTS = 10_000  # checks a split's percentages without an amount


def _splits_json(client_splits: Optional[Sequence[dict]]) -> Optional[str]:
    if not client_splits:
        return None
    if any(s.get("percent") is None for s in client_splits):
        raise ExpenseValidationError("A visit splits its clients by percent, so every line splits the same way.")
    return json.dumps([{"client_id": str(s["client_id"]), "percent": float(s["percent"])} for s in client_splits])


def create_visit(db: Session, user: Users, *, name: str, purpose: str, spend_for: Optional[str],
                 client_id: Optional[str] = None, client_splits: Optional[Sequence[dict]] = None,
                 event_id: Optional[str] = None, investment_label: Optional[str] = None,
                 location: Optional[str] = None, start_date: Optional[date] = None,
                 end_date: Optional[date] = None) -> ExpenseVisit:
    """Raises ExpenseValidationError. Checked with the same rules as an expense, so every line will pass them."""
    from app.services.expense_service import _resolve_event, resolve_attribution

    name = (name or "").strip()
    if not name:
        raise ExpenseValidationError("Give the visit a name, e.g. Seattle - client visit - Nov 2026.")
    if purpose == "INVESTMENT" and not (investment_label or "").strip():
        raise ExpenseValidationError("purpose=INVESTMENT requires investment_label.")
    if start_date and end_date and end_date < start_date:
        raise ExpenseValidationError("The last date can't be before the first date.")
    splits = _splits_json(client_splits)
    event = _resolve_event(db, user, purpose, event_id)
    spend_for, client_id, _ = resolve_attribution(db, user, purpose=purpose, amount_usd_cents=TRIAL_CENTS,
                                                  spend_for=spend_for, client_id=client_id,
                                                  client_splits=client_splits)
    visit = ExpenseVisit(tenant_id=user.tenant_id, owner_user_id=user.UserID, name=name[:512], purpose=purpose,
                         spend_for=spend_for, client_id=client_id, client_splits=splits,
                         event_id=event.id if event else None,
                         investment_label=investment_label if purpose == "INVESTMENT" else None,
                         location=location, start_date=start_date, end_date=end_date)
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


def update_visit(db: Session, visit: ExpenseVisit, *, name: Optional[str] = None, location: Optional[str] = None,
                 start_date: Optional[date] = None, end_date: Optional[date] = None) -> ExpenseVisit:
    """Its name, place and dates. What each line costs, and who carries it, is changed on the line."""
    if name is not None:
        if not name.strip():
            raise ExpenseValidationError("A visit needs a name.")
        visit.name = name.strip()[:512]
        for line in visit.lines:
            line.trip_label = visit.name
    if location is not None:
        visit.location = location or None
    if start_date is not None or end_date is not None:
        first, last = start_date or visit.start_date, end_date or visit.end_date
        if first and last and last < first:
            raise ExpenseValidationError("The last date can't be before the first date.")
        visit.start_date, visit.end_date = first, last
    db.commit()
    db.refresh(visit)
    return visit


def _drafts_dir(visit: ExpenseVisit) -> str:
    from app.services.expense_receipt_service import receipt_dir

    path = os.path.join(receipt_dir(visit.tenant_id), "visit-drafts")
    os.makedirs(path, exist_ok=True)
    return path


def _reading_of(data: bytes, content_type: str) -> Tuple[Optional[str], Optional[str]]:
    from app.services.expense_receipt_service import read_receipt

    try:
        return json.dumps(read_receipt(data, content_type), default=str), None
    except RuntimeError as exc:  # unreadable is an answer: its person types the amount
        return None, str(exc)[:500]


def add_receipts(db: Session, visit: ExpenseVisit, files: Sequence[Tuple[str, str, bytes]]) -> List[ExpenseVisitDraft]:
    """Each receipt waits as a draft for its description. All are refused if any can't be accepted."""
    from app.core.config import settings
    from app.services.expense_receipt_service import ALLOWED_TYPES, ReceiptError, validate

    if not files:
        raise ReceiptError("Attach at least one receipt")
    if len(visit.drafts) + len(files) > settings.EXPENSE_RECEIPT_MAX_FILES:
        raise ReceiptError(f"A visit can hold at most {settings.EXPENSE_RECEIPT_MAX_FILES} receipts waiting at once")
    for _, content_type, data in files:
        validate(content_type, data)
    made = []
    for filename, content_type, data in files:
        draft = ExpenseVisitDraft(id=str(uuid4()), visit_id=visit.id, file_name=(filename or "receipt")[:300],
                                  content_type=content_type)
        draft.file_path = os.path.join(_drafts_dir(visit), f"{draft.id}{ALLOWED_TYPES[content_type]}")
        with open(draft.file_path, "wb") as handle:
            handle.write(data)
        draft.reading, draft.read_error = _reading_of(data, content_type)
        db.add(draft)
        made.append(draft)
    db.commit()
    return made


def draft_prefill(draft: ExpenseVisitDraft) -> Dict:
    """What the receipt says, to fill in the line: amount (USD only), date and merchant."""
    reading = json.loads(draft.reading) if draft.reading else {}
    total = reading.get("total")
    usd = (reading.get("currency") or "USD").upper() == "USD"
    return {"amount_usd_cents": int(round(float(total) * 100)) if total is not None and usd else None,
            "expense_date": reading.get("date"), "merchant": reading.get("merchant"),
            "currency": reading.get("currency")}


def _remove_file(path: Optional[str]) -> None:
    if path and os.path.exists(path):
        os.remove(path)


def submit_draft(db: Session, visit: ExpenseVisit, draft: ExpenseVisitDraft, user: Users, *, description: str,
                 expense_category: str, amount_usd_cents: int, expense_date: date,
                 travel_type: Optional[str] = None, expense_end_date: Optional[date] = None) -> ExpenseRecord:
    """The receipt becomes its own expense line, with the visit's purpose and who carries it. Raises
    ExpenseValidationError (nothing is created) or ReceiptError."""
    from app.services.expense_receipt_service import attach_receipts
    from app.services.expense_service import log_expense

    if not (description or "").strip():
        raise ExpenseValidationError("Say what this receipt was for.")
    with open(draft.file_path, "rb") as handle:
        data = handle.read()
    splits = json.loads(visit.client_splits) if visit.client_splits else None
    line = log_expense(
        db, logged_by_user=user, purpose=visit.purpose, expense_category=expense_category,
        amount_usd_cents=amount_usd_cents, expense_date=expense_date, expense_end_date=expense_end_date,
        receipt_ref=draft.file_name or "receipt", spend_for=visit.spend_for,
        client_id=visit.client_id if visit.spend_for == "CLIENT" else None, client_splits=splits,
        event_id=visit.event_id, investment_label=visit.investment_label,
        travel_type=travel_type if expense_category == "TRAVEL" else None, trip_label=visit.name,
        location=visit.location, description=description.strip(), visit_id=visit.id)
    attach_receipts(db, line, [(draft.file_name, draft.content_type, data)], user=user)
    path = draft.file_path
    db.delete(draft)
    db.commit()
    _remove_file(path)
    db.refresh(line)
    return line


def remove_draft(db: Session, draft: ExpenseVisitDraft) -> None:
    path = draft.file_path
    db.delete(draft)
    db.commit()
    _remove_file(path)


def can_remove_line(line: ExpenseRecord, user: Users) -> bool:
    """Its person, until Finance approves it for payment (the same rule as changing it)."""
    return user.UserID == line.logged_by_user_id and line.payment_status == "PENDING"


def remove_line(db: Session, line: ExpenseRecord, user: Users) -> None:
    """Takes an expense line off: its open tasks are closed and its receipts' files removed. Raises
    ExpenseValidationError once Finance has approved it."""
    from app.models.task import Task
    from app.services.expense_service import _close_open_tasks

    if not can_remove_line(line, user):
        raise ExpenseValidationError("Finance has approved this expense; it can't be removed.")
    _close_open_tasks(db, line)
    db.query(Task).filter(Task.expense_id == line.id).update({"expense_id": None}, synchronize_session=False)
    paths = [r.file_path for r in line.receipts] + [line.receipt_file_path]
    logger.info("[ExpenseVisit] %s removed expense %s ($%.2f)", user.UserID, line.id, line.amount_usd_cents / 100)
    db.delete(line)
    db.commit()
    for path in paths:
        _remove_file(path)


def visit_status(lines: Sequence[ExpenseRecord], drafts: Sequence) -> str:
    """One word for the whole visit, from its lines."""
    if drafts:
        return "NEEDS_DETAILS"
    if not lines:
        return "EMPTY"
    if any(l.manager_approval_status == "REJECTED" or l.payment_status == "REJECTED" for l in lines):
        return "SOME_REJECTED"
    if all(l.payment_status == "REIMBURSED" for l in lines):
        return "REIMBURSED"
    if any(l.manager_approval_status in (None, "PENDING") for l in lines):
        return "PENDING_MANAGER"
    if all(l.payment_status == "APPROVED" or l.payment_status == "REIMBURSED" for l in lines):
        return "APPROVED"
    return "FINANCE_REVIEW"


def visit_detail(visit: ExpenseVisit) -> Dict:
    lines = list(visit.lines)
    return {
        "id": visit.id, "name": visit.name, "purpose": visit.purpose, "spend_for": visit.spend_for,
        "client_id": visit.client_id, "client_name": visit.client.company_name if visit.client else None,
        "client_splits": json.loads(visit.client_splits) if visit.client_splits else [],
        "event_id": visit.event_id, "conference_name": visit.event.name if visit.event else None,
        "investment_label": visit.investment_label, "location": visit.location,
        "start_date": visit.start_date, "end_date": visit.end_date,
        "total_usd_cents": sum(l.amount_usd_cents for l in lines),
        "status": visit_status(lines, visit.drafts),
        "lines": lines,
        "drafts": [{"id": d.id, "file_name": d.file_name, "content_type": d.content_type,
                    "read_error": d.read_error, **draft_prefill(d)} for d in visit.drafts],
    }


def group_existing_trips(db: Session) -> int:
    """Lines logged before visits existed that share a trip label (same person, same label) become one visit."""
    from collections import defaultdict

    groups = defaultdict(list)
    for line in db.query(ExpenseRecord).filter(ExpenseRecord.visit_id.is_(None), ExpenseRecord.trip_label.isnot(None)):
        label = (line.trip_label or "").strip()
        if label:
            groups[(line.logged_by_user_id, label.lower())].append(line)
    for lines in groups.values():
        lines.sort(key=lambda l: l.expense_date)
        first = lines[0]
        alike = len({(l.spend_for, l.client_id, l.purpose) for l in lines}) == 1
        visit = ExpenseVisit(tenant_id=first.tenant_id, owner_user_id=first.logged_by_user_id,
                             name=first.trip_label.strip()[:512], purpose=first.purpose,
                             spend_for=first.spend_for if first.spend_for in SPEND_FOR else "INTERNAL",
                             client_id=first.client_id if alike else None, event_id=first.event_id,
                             investment_label=first.investment_label, location=first.location,
                             start_date=first.expense_date,
                             end_date=max((l.expense_end_date or l.expense_date) for l in lines))
        db.add(visit)
        db.flush()
        for line in lines:
            line.visit_id = visit.id
    db.flush()
    return sum(len(v) for v in groups.values())
