"""CEO 2026-11-10: uploads over the web server's ~1 MB request limit must work on every screen, not one. The
browser sends the form in pieces to /uploads/parts and the middleware rebuilds the request before the endpoint
(app.middleware.large_upload). Driven end to end through a real upload endpoint: expense receipts."""
import os
from uuid import uuid4

import pytest

from app.core.config import settings
from tests.test_expense_review_and_pnl import EXPENSES, _expense, _logger, api, db, reads, w  # noqa: F401

PARTS = "/api/v1/uploads/parts"
PDF = b"%PDF-1.4\n" + bytes(range(256)) * 9000  # about 2.3 MB
PIECE = 768 * 1024


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


def _multipart(fields, file_field, filename, data, content_type):
    boundary = uuid4().hex
    out = b""
    for name, value in fields.items():
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
    out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return out, f"multipart/form-data; boundary={boundary}"


def _send_pieces(api, user, body, upload_id, skip=()):
    total = -(-len(body) // PIECE)
    for index in range(total):
        if index in skip:
            continue
        response = api.client.post(f"{PARTS}?upload_id={upload_id}&index={index}&total={total}",
                            content=body[index * PIECE:(index + 1) * PIECE],
                            headers={**api.headers(user), "Content-Type": "application/octet-stream"})
        assert response.status_code == 200, response.text
    return total


def _rebuilt(api, user, path, upload_id, total, content_type):
    return api.client.post(path, headers={**api.headers(user), "X-Upload-Body": f"{upload_id}:{total}",
                                          "X-Upload-Content-Type": content_type})


def test_a_large_receipt_sent_in_pieces_is_attached_whole_and_checked(db, w, api):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user)
    body, content_type = _multipart({}, "files", "hotel.pdf", PDF, "application/pdf")
    upload_id = uuid4().hex
    total = _send_pieces(api, user, body, upload_id)
    assert total == 3
    with reads({"total": 123.45, "date": "2026-09-10"}):
        response = _rebuilt(api, user, f"{EXPENSES}/{expense.id}/receipts", upload_id, total, content_type)
    assert response.status_code == 200, response.text
    assert [r["file_name"] for r in response.json()["receipts"]] == ["hotel.pdf"]
    db.refresh(expense)
    assert open(expense.receipts[0].file_path, "rb").read() == PDF
    assert expense.receipt_check_status == "MATCHED"
    assert os.listdir(os.path.join(settings.UPLOAD_DIR, "_request_parts", os.listdir(
        os.path.join(settings.UPLOAD_DIR, "_request_parts"))[0])) == []  # the pieces are gone


def test_someone_else_cannot_use_your_pieces(db, w, api):
    user = _logger(db, w)
    other = _logger(db, w)
    expense = _expense(db, other)
    body, content_type = _multipart({}, "files", "hotel.pdf", PDF, "application/pdf")
    upload_id = uuid4().hex
    total = _send_pieces(api, user, body, upload_id)
    response = _rebuilt(api, other, f"{EXPENSES}/{expense.id}/receipts", upload_id, total, content_type)
    assert response.status_code == 400 and "never arrived" in response.json()["detail"]


def test_a_missing_piece_is_refused_and_nothing_is_attached(db, w, api):
    user = _logger(db, w)
    expense = _expense(db, user)
    body, content_type = _multipart({}, "files", "hotel.pdf", PDF, "application/pdf")
    upload_id = uuid4().hex
    total = _send_pieces(api, user, body, upload_id, skip={1})
    response = _rebuilt(api, user, f"{EXPENSES}/{expense.id}/receipts", upload_id, total, content_type)
    assert response.status_code == 400 and "Piece 2 of 3" in response.json()["detail"]
    db.refresh(expense)
    assert expense.receipts == []


def test_pieces_need_a_valid_sign_in(api):
    response = api.client.post(f"{PARTS}?upload_id={uuid4().hex}&index=0&total=1", content=b"x",
                               headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


def test_the_whole_upload_is_capped(db, w, api, monkeypatch):
    monkeypatch.setattr(settings, "LARGE_UPLOAD_MAX_BYTES", 1024 * 1024)
    user = _logger(db, w)
    upload_id = uuid4().hex
    url = f"{PARTS}?upload_id={upload_id}&total=3&index="
    headers = {**api.headers(user), "Content-Type": "application/octet-stream"}
    assert api.client.post(url + "0", content=PDF[:PIECE], headers=headers).status_code == 200
    assert api.client.post(url + "1", content=PDF[PIECE:2 * PIECE], headers=headers).status_code == 413


@pytest.mark.parametrize("params", ["upload_id=../../etc&index=0&total=1", "upload_id={id}&index=3&total=3",
                                   "upload_id={id}&index=0&total=999", "upload_id={id}"])
def test_a_bad_id_or_position_is_refused(db, w, api, params):
    user = _logger(db, w)
    response = api.client.post(PARTS + "?" + params.replace("{id}", uuid4().hex), content=b"x",
                               headers={**api.headers(user), "Content-Type": "application/octet-stream"})
    assert response.status_code == 400


def test_only_a_form_can_be_rebuilt(db, w, api):
    user = _logger(db, w)
    upload_id = uuid4().hex
    total = _send_pieces(api, user, b'{"a": 1}', upload_id)
    response = _rebuilt(api, user, f"{EXPENSES}", upload_id, total, "application/json")
    assert response.status_code == 400 and "form" in response.json()["detail"]


def test_a_small_upload_is_untouched(db, w, api):
    user = _logger(db, w, manager=w.partner_a)
    expense = _expense(db, user)
    with reads({"total": 123.45, "date": "2026-09-10"}):
        response = api.post(user, f"{EXPENSES}/{expense.id}/receipts",
                            files={"files": ("a.pdf", b"%PDF-1.4 small", "application/pdf")})
    assert response.status_code == 200 and len(response.json()["receipts"]) == 1
