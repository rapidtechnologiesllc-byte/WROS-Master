"""Masked production copy (CEO 2026-11-27): every email inside free text and JSON is masked, and the leak check that
guards the copy finds nothing left. The first production run stopped on employee import rows where one address
ended another ("b@x.com" inside "ab@x.com"): a plain replace half-rewrote the longer one."""
import json
import re
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prodcopy_mask as mask  # noqa: E402

DOMAINS = ["blitzenx.com"]


def _mask(db, value: str) -> str:
    db.execute(text(mask.MASK_EMAILS_FUNCTION))
    return db.execute(text("SELECT pg_temp.mask_emails(:v, :d)"), {"v": value, "d": DOMAINS}).scalar()


def _leaks(db, value: str) -> bool:
    return db.execute(text("SELECT regexp_replace(:v, :masked, '', 'g') ~ :email"),
                      {"v": value, "masked": mask.MASKED_ANYWHERE, "email": mask.EMAIL_VALUE.pattern}).scalar()


def test_an_address_that_ends_another_is_masked_whole(db):
    out = _mask(db, "ab@acme.com, b@acme.com and again ab@acme.com")
    assert "acme" not in out and "ab@" not in out
    assert not _leaks(db, out)
    first, second, third = re.findall(r"u[0-9a-f]{12}@[a-z.]+", out)
    assert first == third and first != second  # the same address always masks the same way


def test_emails_inside_json_rows_are_masked_and_stay_json(db):
    rows = [{"email": "jane.doe@acme.com", "manager": "e.doe@acme.com"},
            {"email": "doe@acme.com", "work": "ops@blitzenx.com"}]
    out = _mask(db, json.dumps(rows))
    parsed = json.loads(out)
    assert parsed[1]["work"].endswith("@blitzenx.com")  # our own domain is kept, the person is not
    assert all(r["email"].endswith("@example.invalid") for r in parsed)
    assert not _leaks(db, out)


def test_already_masked_addresses_are_left_alone(db):
    once = _mask(db, "x@acme.com")
    assert _mask(db, once) == once
