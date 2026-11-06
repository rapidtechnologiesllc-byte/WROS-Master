"""Expense receipts: attach, read, check, decide (CEO 2026-10-13: "validation if the receipt is
accurate and approved or needing human interference").

An expense can have several receipts (CEO 2026-11-06). Upload stores each file under
UPLOAD_DIR/expense-receipts/<tenant>/. Each is read for total, currency, date and merchant, by rule first
(app.services.expense_receipt_reader: production has no working AI key), by the vision model only if rules
can't and a key works. Together they are checked against the entry:
  MATCHED     same currency (USD), their totals add up to the entry within
              EXPENSE_RECEIPT_AMOUNT_TOLERANCE_PCT (min $1), each dated within
              EXPENSE_RECEIPT_DATE_TOLERANCE_DAYS of the entry's dates -> the manager step is approved
              by the system; Finance still approves payment
  MISMATCH    any of those differ -> stays with the manager, with the reasons
  UNREADABLE  the receipt could not be read -> stays with the manager
Finance's payment approval and "mark paid" are unchanged: money never moves without Finance.
"""
import base64
import json
import logging
import os
import re
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence, Tuple

import requests
from sqlalchemy.orm import Session

from app.models.expense import ExpenseReceipt, ExpenseRecord

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}
GEMINI_MODEL_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
READ_TIMEOUT_SECONDS = 25
SYSTEM_APPROVER = None  # manager_approved_by stays empty; receipt_check_detail records the system decision

PROMPT = ("You read expense receipts. Return ONLY JSON: {\"total\": number or null, \"currency\": "
          "\"ISO 4217 code\" or null, \"date\": \"YYYY-MM-DD\" or null, \"merchant\": string or null, "
          "\"is_receipt\": true|false}. total is the final amount paid including tax and tip.")


class ReceiptError(Exception):
    """The upload itself is not acceptable (type, size, state)."""


def receipt_dir(tenant_id) -> str:
    from app.core.config import settings
    path = os.path.join(settings.UPLOAD_DIR, "expense-receipts", str(tenant_id))
    os.makedirs(path, exist_ok=True)
    return path


def validate(content_type: str, data: bytes) -> None:
    from app.core.config import settings

    if content_type not in ALLOWED_TYPES:
        raise ReceiptError(f"Receipt must be a JPG, PNG, WEBP image or a PDF (got {content_type or 'unknown'})")
    if not data:
        raise ReceiptError("The receipt file is empty")
    if len(data) > settings.EXPENSE_RECEIPT_MAX_BYTES:
        raise ReceiptError(f"Receipt is larger than {settings.EXPENSE_RECEIPT_MAX_BYTES // (1024 * 1024)} MB")


def store(expense: ExpenseRecord, receipt_id: str, content_type: str, data: bytes) -> str:
    validate(content_type, data)
    path = os.path.join(receipt_dir(expense.tenant_id), f"{receipt_id}{ALLOWED_TYPES[content_type]}")
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def read_receipt(data: bytes, content_type: str) -> Dict:
    """What the receipt says: by rule when that finds a total and a date, else by the vision model,
    else whatever the rules found. Raises RuntimeError when nothing can be read."""
    from app.services.expense_receipt_reader import read_by_rules

    by_rules, why = None, None
    try:
        by_rules = read_by_rules(data, content_type)
    except RuntimeError as exc:
        why = exc
    if by_rules and by_rules.get("total") is not None and by_rules.get("date"):
        return by_rules
    try:
        return {**_read_by_ai(data, content_type), "read_by": "ai"}
    except RuntimeError as exc:
        logger.info(f"[ExpenseReceipt] the vision model did not read it either: {exc}")
    if by_rules:
        return by_rules
    raise RuntimeError(str(why or "it could not be read"))


def _read_by_ai(data: bytes, content_type: str) -> Dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    response = requests.post(f"{GEMINI_MODEL_URL}?key={api_key}", timeout=READ_TIMEOUT_SECONDS, json={
        "contents": [{"parts": [{"text": PROMPT},
                                {"inline_data": {"mime_type": content_type,
                                                 "data": base64.b64encode(data).decode()}}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    })
    if response.status_code != 200:
        raise RuntimeError(f"Receipt reader returned HTTP {response.status_code}")
    try:
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        match = re.search(r"\{.*\}", text, re.S)
        return json.loads(match.group(0) if match else text)
    except (KeyError, IndexError, ValueError, AttributeError) as exc:
        raise RuntimeError(f"Receipt reader returned an unreadable answer: {exc}") from exc


def _reading(receipt: ExpenseReceipt) -> Optional[Dict]:
    if not receipt.reading:
        return None
    try:
        return json.loads(receipt.reading)
    except ValueError:
        logger.warning(f"[ExpenseReceipt] receipt {receipt.id}: stored reading is not JSON")
        return None


def _parsed_date(text) -> Optional[date]:
    try:
        return datetime.strptime(str(text), "%Y-%m-%d").date() if text else None
    except ValueError:
        return None


def compare(expense: ExpenseRecord, receipts: Sequence[ExpenseReceipt]) -> Tuple[str, List[str]]:
    """(MATCHED | MISMATCH | UNREADABLE, reasons) for all the expense's receipts together."""
    from app.core.config import settings

    entered = expense.amount_usd_cents / 100
    many = len(receipts) > 1
    named = lambda receipt, text: f"{receipt.file_name or 'A receipt'}: {text}" if many else text  # noqa: E731
    unreadable, reasons, total, totals_known, every_amount = [], [], 0.0, True, []
    tolerance_days = settings.EXPENSE_RECEIPT_DATE_TOLERANCE_DAYS
    first, last = expense.expense_date, expense.expense_end_date or expense.expense_date
    for receipt in receipts:
        reading = _reading(receipt)
        if receipt.read_error and not reading:
            unreadable.append(named(receipt, receipt.read_error))
            continue
        if not reading or reading.get("is_receipt") is False:
            unreadable.append(named(receipt, "The file doesn't look like a receipt"))
            continue
        every_amount += reading.get("amounts") or []
        currency = (reading.get("currency") or "").upper()
        if currency and currency != "USD":
            reasons.append(named(receipt, f"Receipt is in {currency}; the entry is in USD - check the conversion"))
        if reading.get("total") is None:
            totals_known = False
        else:
            total += float(reading["total"])
        seen = [d for d in (_parsed_date(t) for t in [reading.get("date"), *(reading.get("dates") or [])]) if d]
        in_range = any((d - first).days >= -tolerance_days and (d - last).days <= tolerance_days for d in seen)
        if not seen:
            reasons.append(named(receipt, "No date could be read from the receipt"))
        elif not in_range:
            wanted = f"{first} to {last}" if first != last else str(first)
            reasons.append(named(receipt, f"Receipt date {seen[0]} vs entered {wanted}"))
    if unreadable:
        return "UNREADABLE", unreadable + reasons
    if not totals_known:
        on_it = any(abs(float(a) - entered) < 0.005 for a in every_amount)
        if not on_it and not many:
            return "UNREADABLE", ["No total could be read from the receipt"]
        if on_it:
            reasons.insert(0, f"The amount {entered:.2f} is on the document, but nothing marks it as the total paid")
        else:
            reasons.insert(0, "No total could be read from one of the receipts")
        return "MISMATCH", reasons
    tolerance = max(1.0, entered * settings.EXPENSE_RECEIPT_AMOUNT_TOLERANCE_PCT / 100)
    if abs(total - entered) > tolerance:
        also = any(abs(float(a) - entered) < 0.005 for a in every_amount)
        reasons.insert(0, f"Receipt{'s' if many else ''} total{'' if many else ''} {total:.2f} vs entered {entered:.2f}"
                       + (f" ({entered:.2f} also appears on the document)" if also else ""))
    return ("MISMATCH", reasons) if reasons else ("MATCHED", [])


def recheck(db: Session, expense: ExpenseRecord, *, auto_approve: bool = True) -> None:
    """Check all the expense's receipts against what it says now, from what was already read (no second
    read), and approve the manager step when they match. Doesn't commit."""
    from app.services.expense_service import _close_open_tasks, attribution_gaps

    db.flush()
    db.expire(expense, ["receipts"])
    receipts = list(expense.receipts)
    if not receipts:
        expense.receipt_file_path, expense.receipt_content_type = None, None
        expense.receipt_check_status, expense.receipt_check_detail = "NOT_ATTACHED", None
        return
    expense.receipt_file_path = receipts[0].file_path
    expense.receipt_content_type = receipts[0].content_type
    status, reasons = compare(expense, receipts)
    readings = [_reading(r) for r in receipts]
    expense.receipt_check_status = status
    expense.receipt_check_detail = json.dumps({
        "receipt": readings[0], "reasons": reasons, "checked_at": datetime.utcnow().isoformat(timespec="seconds"),
        "entered_usd": expense.amount_usd_cents / 100,
        "receipts": [{"id": r.id, "file_name": r.file_name, "error": r.read_error,
                      **{k: (reading or {}).get(k) for k in ("merchant", "total", "currency", "date", "read_by")}}
                     for r, reading in zip(receipts, readings)],
    })
    gaps = attribution_gaps(expense)
    if status != "MATCHED" or expense.manager_approval_status != "PENDING":
        logger.info(f"[ExpenseReceipt] {expense.id}: {status} ({'; '.join(reasons)})")
    elif gaps:  # the receipts are fine, but who it is on is not settled yet
        logger.info(f"[ExpenseReceipt] {expense.id}: receipts match, manager reviews (missing {'; '.join(gaps)})")
    elif auto_approve:
        expense.manager_approval_status = "APPROVED"
        expense.manager_approved_by = SYSTEM_APPROVER
        expense.manager_approved_at = datetime.utcnow()
        _close_open_tasks(db, expense)
        logger.info(f"[ExpenseReceipt] {expense.id}: receipts match - manager step approved automatically")
    db.add(expense)


def read_into(receipt: ExpenseReceipt, data: bytes, content_type: str) -> None:
    try:
        receipt.reading, receipt.read_error = json.dumps(read_receipt(data, content_type)), None
    except RuntimeError as exc:
        logger.warning(f"[ExpenseReceipt] {receipt.expense_id}: could not read receipt: {exc}")
        receipt.reading, receipt.read_error = None, f"The receipt couldn't be read automatically ({exc})"


def _ensure_changeable(expense: ExpenseRecord) -> None:
    if expense.payment_status != "PENDING":
        raise ReceiptError("Finance has approved this expense; its receipts can't be changed")


def attach_receipts(db: Session, expense: ExpenseRecord, files: Sequence[Tuple[str, str, bytes]], *, user=None,
                    check: bool = True) -> ExpenseRecord:
    """Store and read each file, then check them all. All the files are refused if any can't be
    accepted. Receipts added after the manager decided send it back to them."""
    from uuid import uuid4

    from app.core.config import settings
    from app.services.expense_service import record_edit, return_to_manager

    _ensure_changeable(expense)
    if not files:
        raise ReceiptError("Attach at least one receipt")
    if len(expense.receipts) + len(files) > settings.EXPENSE_RECEIPT_MAX_FILES:
        raise ReceiptError(f"An expense can have at most {settings.EXPENSE_RECEIPT_MAX_FILES} receipts")
    for _, content_type, data in files:
        validate(content_type, data)
    for filename, content_type, data in files:
        receipt = ExpenseReceipt(id=str(uuid4()), expense_id=expense.id, file_name=(filename or "receipt")[:300],
                                 content_type=content_type)
        receipt.file_path = store(expense, receipt.id, content_type, data)
        read_into(receipt, data, content_type)
        db.add(receipt)
    if not expense.receipt_ref:
        expense.receipt_ref = (files[0][0] or "receipt")[:300]
    if expense.receipt_check_status != "NOT_ATTACHED":
        record_edit(db, expense, user, f"Added {', '.join((f[0] or 'receipt') for f in files)}")
    if check and expense.manager_approval_status != "PENDING":
        return_to_manager(db, expense, note="Receipts were added after the decision.")
    if check:
        recheck(db, expense)
    db.commit()
    db.refresh(expense)
    return expense


def attach_and_check(db: Session, expense: ExpenseRecord, filename: str, content_type: str, data: bytes) -> ExpenseRecord:
    return attach_receipts(db, expense, [(filename, content_type, data)])


def remove_receipt(db: Session, expense: ExpenseRecord, receipt_id: str, *, user=None) -> ExpenseRecord:
    from app.services.expense_service import record_edit, return_to_manager

    _ensure_changeable(expense)
    receipt = next((r for r in expense.receipts if r.id == receipt_id), None)
    if receipt is None:
        raise ReceiptError("Receipt not found")
    if len(expense.receipts) == 1:
        raise ReceiptError("Every expense needs a receipt: add the right one first, then remove this one")
    path, name = receipt.file_path, receipt.file_name
    expense.receipts.remove(receipt)
    record_edit(db, expense, user, f"Removed {name or 'a receipt'}")
    if expense.manager_approval_status != "PENDING":
        return_to_manager(db, expense, note=f"Receipt {name or ''} was removed after the decision.")
    recheck(db, expense)
    db.commit()
    db.refresh(expense)
    try:
        os.remove(path)
    except OSError as exc:  # the record is already right; a leftover file harms nothing
        logger.warning(f"[ExpenseReceipt] could not delete {path}: {exc}")
    return expense
