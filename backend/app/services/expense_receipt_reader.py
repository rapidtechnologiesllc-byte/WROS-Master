"""Reads a receipt without any AI service (production has no working AI key, so this comes first):
the text of a PDF, or OCR of a photo or scanned PDF, then the total, date, currency and merchant by
rule. Raises RuntimeError when nothing can be read; the receipt then waits for a person."""
import logging
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime
from io import BytesIO
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

OCR_TIMEOUT_SECONDS = 25
OCR_MAX_PAGES = 3
AMOUNT = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+\.\d{2}|\d+\.\d{2})(?![\d])")
# strongest first: the line that says what was actually paid
TOTAL_LABELS = (r"grand\s+total", r"total\s+(?:paid|charged|amount|due)", r"amount\s+(?:paid|charged|due)",
                r"(?:balance|payment)\s+(?:due|amount)", r"(?<!sub)(?<!sub[\s-])\btotal\b")
MONTHS = {name: i + 1 for i, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}
ISO_DATE = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
SLASH_DATE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2}|\d{2})\b")
WORD_DATE = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})\b")
DAY_FIRST_DATE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[\s-]+([A-Za-z]{3,9})\.?,?[\s-]+(20\d{2})\b")


def _ocr_image(path: str) -> str:
    if not shutil.which("tesseract"):
        raise RuntimeError("the OCR reader is not installed on this server")
    done = subprocess.run(["tesseract", path, "stdout"], capture_output=True, timeout=OCR_TIMEOUT_SECONDS, check=False)
    if done.returncode != 0:
        raise RuntimeError(f"the OCR reader failed: {done.stderr.decode(errors='replace')[:120]}")
    return done.stdout.decode(errors="replace")


def _pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
    except Exception as exc:  # pypdf raises many types on a damaged file: it is simply not readable as text
        logger.warning(f"[ReceiptReader] PDF text extraction failed: {exc}")
        return ""


def _ocr_pdf(data: bytes) -> str:
    if not shutil.which("pdftoppm"):
        raise RuntimeError("this PDF has no text and the page reader is not installed on this server")
    with tempfile.TemporaryDirectory() as folder:
        source = os.path.join(folder, "receipt.pdf")
        with open(source, "wb") as handle:
            handle.write(data)
        subprocess.run(["pdftoppm", "-r", "200", "-png", "-l", str(OCR_MAX_PAGES), source, os.path.join(folder, "page")],
                       capture_output=True, timeout=OCR_TIMEOUT_SECONDS, check=True)
        pages = sorted(name for name in os.listdir(folder) if name.endswith(".png"))
        return "\n".join(_ocr_image(os.path.join(folder, name)) for name in pages)


def text_of(data: bytes, content_type: str) -> str:
    if content_type == "application/pdf":
        text = _pdf_text(data)
        return text if text.strip() else _ocr_pdf(data)
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(content_type, ".img")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
        handle.write(data)
    try:
        return _ocr_image(handle.name)
    finally:
        os.unlink(handle.name)


def _money(text: str) -> float:
    return float(text.replace(",", ""))


def _labelled_total(lines: List[str]) -> Optional[float]:
    """The amount on (or just under) the strongest "total" line; the last such line wins, as a
    receipt ends with its final figure."""
    for label in TOTAL_LABELS:
        pattern = re.compile(label, re.I)
        found = None
        for index, line in enumerate(lines):
            if not pattern.search(line):
                continue
            amounts = AMOUNT.findall(line) or (AMOUNT.findall(lines[index + 1]) if index + 1 < len(lines) else [])
            if amounts:
                found = _money(amounts[-1])
        if found is not None:
            return found
    return None


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def dates_in(text: str) -> List[date]:
    """Every date on the document, in order. 03/04/2026 is read month first (US receipts) unless the
    first number can't be a month."""
    found = []
    for match in re.finditer("|".join(p.pattern for p in (ISO_DATE, SLASH_DATE, WORD_DATE, DAY_FIRST_DATE)), text):
        piece = match.group(0)
        parsed = None
        if ISO_DATE.fullmatch(piece):
            year, month, day = ISO_DATE.fullmatch(piece).groups()
            parsed = _safe_date(int(year), int(month), int(day))
        elif SLASH_DATE.fullmatch(piece):
            first, second, year = SLASH_DATE.fullmatch(piece).groups()
            year = int(year) + (2000 if len(year) == 2 else 0)
            month, day = (int(second), int(first)) if int(first) > 12 else (int(first), int(second))
            parsed = _safe_date(year, month, day)
        elif WORD_DATE.fullmatch(piece):
            name, day, year = WORD_DATE.fullmatch(piece).groups()
            month = MONTHS.get(name[:3].lower())
            parsed = _safe_date(int(year), month, int(day)) if month else None
        elif DAY_FIRST_DATE.fullmatch(piece):
            day, name, year = DAY_FIRST_DATE.fullmatch(piece).groups()
            month = MONTHS.get(name[:3].lower())
            parsed = _safe_date(int(year), month, int(day)) if month else None
        if parsed and parsed not in found:
            found.append(parsed)
    return found


def _currency(text: str) -> Optional[str]:
    if "₹" in text or re.search(r"\b(?:INR|Rs\.?)\b", text):
        return "INR"
    if "€" in text or re.search(r"\bEUR\b", text):
        return "EUR"
    if "£" in text or re.search(r"\bGBP\b", text):
        return "GBP"
    if "$" in text or re.search(r"\bUSD\b", text):
        return "USD"
    return None


def parse(text: str) -> Dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    amounts = sorted({_money(a) for a in AMOUNT.findall(text)})
    found_dates = dates_in(text)
    merchant = next((line for line in lines if re.search(r"[A-Za-z]{3}", line)), None)
    return {
        "total": _labelled_total(lines), "currency": _currency(text),
        "date": found_dates[0].isoformat() if found_dates else None,
        "merchant": merchant[:80] if merchant else None, "is_receipt": bool(amounts),
        "amounts": amounts, "dates": [d.isoformat() for d in found_dates], "read_by": "rules",
        "read_at": datetime.utcnow().isoformat(timespec="seconds"),
    }


def read_by_rules(data: bytes, content_type: str) -> Dict:
    try:
        text = text_of(data, content_type)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"the receipt reader failed: {exc}") from exc
    if not text.strip():
        raise RuntimeError("no text could be found on it")
    return parse(text)
