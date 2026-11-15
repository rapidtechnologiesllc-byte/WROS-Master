"""Large uploads, for every screen (CEO 2026-11-10: a consultant could not upload receipts; "it has to be application
wide"). The web server in front of HRMS refuses a request body over about 1 MB, before HRMS sees it. So the browser
(frontend/src/services/api/client.js, sendForm) sends an oversized form in pieces, then sends the original request
with an empty body and two headers, and this middleware puts the body back before any endpoint runs. Endpoints
don't change: they receive the same multipart form they always did, and keep their own type and size rules.

  POST /api/v1/uploads/parts?upload_id=<32 hex>&index=<i>&total=<n>   body: raw bytes of piece i
      Needs a valid sign-in (a user's or a candidate portal link's). Pieces are kept per sign-in, so nobody can
      use another person's upload.
  <the original request>  X-Upload-Body: <upload id>:<n>   X-Upload-Content-Type: multipart/form-data; boundary=..
      The pieces are joined in order, removed, and handed on as the request body. A missing piece -> 400.

Pieces wait under UPLOAD_DIR/_request_parts/ and anything older than LARGE_UPLOAD_KEEP_SECONDS is removed.
The whole body is capped at LARGE_UPLOAD_MAX_BYTES and at LARGE_UPLOAD_MAX_PARTS pieces.
"""
import hashlib
import json
import logging
import os
import re
import shutil
import time
from urllib.parse import parse_qs

from app.core.config import settings

logger = logging.getLogger(__name__)

PARTS_PATH = "/api/v1/uploads/parts"
BODY_HEADER = b"x-upload-body"
TYPE_HEADER = b"x-upload-content-type"
UPLOAD_ID = re.compile(r"^[0-9a-f]{32}$")


class UploadRefused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _root() -> str:
    return os.path.join(settings.UPLOAD_DIR, "_request_parts")


def _owner(headers: dict) -> str:
    """Who the pieces belong to: the signed-in person (a user or a portal candidate), not the token itself, which
    is renewed while a long upload runs. The token must be valid."""
    from app.core.security import verify_token

    auth = headers.get(b"authorization", b"").decode("latin-1")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    try:
        claims = verify_token(token)
    except ValueError:
        raise UploadRefused(401, "Sign in again to upload this file")
    if not claims.get("sub"):
        raise UploadRefused(401, "Sign in again to upload this file")
    who = f"{claims.get('type')}:{claims.get('tenant_id')}:{claims['sub']}"
    return hashlib.sha256(who.encode()).hexdigest()[:32]


def _folder(owner: str, upload_id: str) -> str:
    if not UPLOAD_ID.match(upload_id or ""):
        raise UploadRefused(400, "This upload has no valid id; send the file again")
    return os.path.join(_root(), owner, upload_id)


def _sweep() -> None:
    root = _root()
    if not os.path.isdir(root):
        return
    now = time.time()
    for owner in os.listdir(root):
        for upload in os.listdir(os.path.join(root, owner)):
            path = os.path.join(root, owner, upload)
            if now - os.path.getmtime(path) > settings.LARGE_UPLOAD_KEEP_SECONDS:
                shutil.rmtree(path, ignore_errors=True)


def _too_large() -> UploadRefused:
    return UploadRefused(413, f"The upload is larger than {settings.LARGE_UPLOAD_MAX_BYTES // (1024 * 1024)} MB")


def keep_part(headers: dict, query: str, data: bytes) -> dict:
    owner = _owner(headers)
    params = {k: v[0] for k, v in parse_qs(query).items()}
    try:
        index, total = int(params.get("index", "")), int(params.get("total", ""))
    except ValueError:
        raise UploadRefused(400, "This piece of the file has no position; send the file again")
    if not 1 <= total <= settings.LARGE_UPLOAD_MAX_PARTS or not 0 <= index < total:
        raise UploadRefused(400, "This piece of the file is out of range; send the file again")
    if not data:
        raise UploadRefused(400, "A piece of the file arrived empty; send the file again")
    folder = _folder(owner, params.get("upload_id", ""))
    _sweep()
    os.makedirs(folder, exist_ok=True)
    held = sum(os.path.getsize(os.path.join(folder, n)) for n in os.listdir(folder) if n != f"{index:04d}")
    if held + len(data) > settings.LARGE_UPLOAD_MAX_BYTES:
        shutil.rmtree(folder, ignore_errors=True)
        raise _too_large()
    with open(os.path.join(folder, f"{index:04d}"), "wb") as handle:
        handle.write(data)
    return {"received": index + 1, "total": total}


def take_body(headers: dict) -> bytes:
    """Join the pieces named by X-Upload-Body, remove them and return the body."""
    owner = _owner(headers)
    upload_id, _, total_text = headers.get(BODY_HEADER, b"").decode("latin-1").partition(":")
    folder = _folder(owner, upload_id.strip())
    try:
        total = int(total_text)
    except ValueError:
        raise UploadRefused(400, "The upload doesn't say how many pieces it has; send the file again")
    missing = [str(i + 1) for i in range(total) if not os.path.exists(os.path.join(folder, f"{i:04d}"))]
    if total < 1 or missing:
        shutil.rmtree(folder, ignore_errors=True)
        raise UploadRefused(400, f"Piece {', '.join(missing) or '?'} of {total} of the upload never arrived; "
                                 "send the file again")
    parts = []
    for i in range(total):
        with open(os.path.join(folder, f"{i:04d}"), "rb") as handle:
            parts.append(handle.read())
    shutil.rmtree(folder, ignore_errors=True)
    return b"".join(parts)


async def _read_body(receive, limit: int) -> bytes:
    chunks, size = [], 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            raise UploadRefused(400, "The upload was interrupted; send the file again")
        chunk = message.get("body", b"")
        size += len(chunk)
        if size > limit:
            raise _too_large()
        chunks.append(chunk)
        if not message.get("more_body"):
            return b"".join(chunks)


async def _respond(send, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


class LargeUploadMiddleware:
    """Pure ASGI, so the rebuilt body reaches FastAPI's form parsing untouched."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        try:
            if scope["path"] == PARTS_PATH and scope["method"] == "POST":
                data = await _read_body(receive, settings.LARGE_UPLOAD_MAX_BYTES)
                return await _respond(send, 200, keep_part(headers, scope.get("query_string", b"").decode(), data))
            if BODY_HEADER not in headers:
                return await self.app(scope, receive, send)
            content_type = headers.get(TYPE_HEADER, b"")
            if not content_type.startswith(b"multipart/form-data"):
                raise UploadRefused(400, "Only a form upload can be sent in pieces")
            body = take_body(headers)
        except UploadRefused as exc:
            logger.warning("[LargeUpload] %s %s refused: %s", scope.get("method"), scope.get("path"), exc.message)
            return await _respond(send, exc.status, {"detail": exc.message})
        kept = [(k, v) for k, v in scope["headers"]
                if k not in (b"content-type", b"content-length", BODY_HEADER, TYPE_HEADER)]
        scope = dict(scope, headers=kept + [(b"content-type", content_type),
                                            (b"content-length", str(len(body)).encode())])
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        logger.info("[LargeUpload] %s %s rebuilt a %d byte upload", scope["method"], scope["path"], len(body))
        return await self.app(scope, replay, send)
