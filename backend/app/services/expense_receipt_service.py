"""Expense receipts: attach, read, check, decide (CEO 2026-10-13: "validation if the receipt is
accurate and approved or needing human interference").

Upload stores the file under UPLOAD_DIR/expense-receipts/<tenant>/. The receipt is read by the
vision model (Gemini) for total, currency, date and merchant, then checked against the entry:
  MATCHED     same currency (USD), total within EXPENSE_RECEIPT_AMOUNT_TOLERANCE_PCT (min $1),
              date within EXPENSE_RECEIPT_DATE_TOLERANCE_DAYS -> the manager step is approved by
              the system; Finance still approves payment
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
from typing import Dict, Optional, Tuple

import requests
from sqlalchemy.orm import Session

from app.models.expense import ExpenseRecord

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


def store(expense: ExpenseRecord, content_type: str, data: bytes) -> str:
    from app.core.config import settings

    if content_type not in ALLOWED_TYPES:
        raise ReceiptError(f"Receipt must be a JPG, PNG, WEBP image or a PDF (got {content_type or 'unknown'})")
    if not data:
        raise ReceiptError("The receipt file is empty")
    if len(data) > settings.EXPENSE_RECEIPT_MAX_BYTES:
        raise ReceiptError(f"Receipt is larger than {settings.EXPENSE_RECEIPT_MAX_BYTES // (1024 * 1024)} MB")
    path = os.path.join(receipt_dir(expense.tenant_id), f"{expense.id}{ALLOWED_TYPES[content_type]}")
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def read_receipt(data: bytes, content_type: str) -> Dict:
    """What the receipt says. Raises RuntimeError when it can't be read."""
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


def compare(expense: ExpenseRecord, receipt: Dict) -> Tuple[str, list]:
    """(MATCHED | MISMATCH | UNREADABLE, reasons)."""
    from app.core.config import settings

    if not receipt or receipt.get("is_receipt") is False:
        return "UNREADABLE", ["The file doesn't look like a receipt"]
    reasons = []
    total, currency = receipt.get("total"), (receipt.get("currency") or "").upper()
    if total is None:
        return "UNREADABLE", ["No total could be read from the receipt"]
    if currency and currency != "USD":
        reasons.append(f"Receipt is in {currency}; the entry is in USD - check the conversion")
    entered = expense.amount_usd_cents / 100
    tolerance = max(1.0, entered * settings.EXPENSE_RECEIPT_AMOUNT_TOLERANCE_PCT / 100)
    if abs(float(total) - entered) > tolerance:
        reasons.append(f"Receipt total {float(total):.2f} vs entered {entered:.2f}")
    receipt_date: Optional[date] = None
    try:
        receipt_date = datetime.strptime(str(receipt.get("date")), "%Y-%m-%d").date() if receipt.get("date") else None
    except ValueError:
        receipt_date = None
    if receipt_date is None:
        reasons.append("No date could be read from the receipt")
    elif abs((receipt_date - expense.expense_date).days) > settings.EXPENSE_RECEIPT_DATE_TOLERANCE_DAYS:
        reasons.append(f"Receipt date {receipt_date} vs entered {expense.expense_date}")
    return ("MISMATCH", reasons) if reasons else ("MATCHED", [])


def attach_and_check(db: Session, expense: ExpenseRecord, filename: str, content_type: str, data: bytes) -> ExpenseRecord:
    """Store the receipt, read and check it, and approve the manager step when it matches."""
    from app.services.expense_service import _close_open_tasks

    if expense.manager_approval_status != "PENDING":
        raise ReceiptError(f"The expense is already {expense.manager_approval_status.lower()}; "
                           "its receipt can't be replaced")
    expense.receipt_file_path = store(expense, content_type, data)
    expense.receipt_content_type = content_type
    if not expense.receipt_ref:
        expense.receipt_ref = (filename or "receipt")[:300]
    try:
        receipt = read_receipt(data, content_type)
        status, reasons = compare(expense, receipt)
    except RuntimeError as exc:
        logger.warning(f"[ExpenseReceipt] {expense.id}: could not read receipt: {exc}")
        receipt, status, reasons = None, "UNREADABLE", [f"The receipt couldn't be read automatically ({exc})"]
    expense.receipt_check_status = status
    expense.receipt_check_detail = json.dumps({"receipt": receipt, "reasons": reasons,
                                               "checked_at": datetime.utcnow().isoformat(timespec="seconds")})
    if status == "MATCHED":
        expense.manager_approval_status = "APPROVED"
        expense.manager_approved_by = SYSTEM_APPROVER
        expense.manager_approved_at = datetime.utcnow()
        _close_open_tasks(db, expense)
        logger.info(f"[ExpenseReceipt] {expense.id}: receipt matches - manager step approved automatically")
    else:
        logger.info(f"[ExpenseReceipt] {expense.id}: {status} - manager reviews ({'; '.join(reasons)})")
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense
