"""
import logging
S-216/HRMS-0118 -- Shared Activity Timeline & File Attachment Framework.

upload_file() is BR-0118-01's one sanctioned file-attachment path for
any entity type. Real SharePoint storage (see app.models.file_upload's
module docstring for why -- this codebase's real, already-proven
backend, not the spec's assumed-but-unprovisioned S3), organized by
entity_type/entity_id rather than app.services.document_service's
candidate-only folder layout, so this doesn't try to force-fit through
a method that hardcodes "candidate_id" as its only entity concept.

Same Microsoft Graph upload mechanics as document_service.upload_to_sharepoint
(simple PUT under 4MB, resumable session at/above it) -- proven,
copied rather than awkwardly wrapped through a candidate-specific method.
"""
import logging
import hashlib
import os
from datetime import datetime
from typing import Callable, Optional

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.graph_auth import get_graph_token
from app.core.logging import logger
from app.models.file_upload import FileUpload

SHAREPOINT_SITE_ID = os.getenv("SHAREPOINT_SITE_ID", "")
SHAREPOINT_DRIVE_ID = os.getenv("SHAREPOINT_DRIVE_ID", "")
SHAREPOINT_BASE_FOLDER = os.getenv("SHAREPOINT_BASE_FOLDER", "CandidateDocuments")
ATTACHMENTS_FOLDER = "SharedAttachments"

logger = logging.getLogger(__name__)

class VirusScanUnavailable(Exception):
    """Same contract as app.services.virus_scan_service.VirusScanUnavailable
    -- no AV scanning service is provisioned in this codebase yet."""


def _scan_unconfigured(file_content: bytes) -> str:
    raise VirusScanUnavailable("No virus-scanning service is provisioned in this codebase yet.")


def _generate_unique_filename(original_filename: str, entity_id: str) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    file_ext = os.path.splitext(original_filename)[1]
    file_hash = hashlib.md5(f"{entity_id}{timestamp}{original_filename}".encode()).hexdigest()[:8]
    return f"{timestamp}_{file_hash}{file_ext}"


def _upload_to_sharepoint(access_token: str, entity_type: str, entity_id: str, file_content: bytes, unique_filename: str) -> dict:
    folder_path = f"{SHAREPOINT_BASE_FOLDER}/{ATTACHMENTS_FOLDER}/{entity_type}/{entity_id}"
    try:
        if len(file_content) < 4 * 1024 * 1024:
            upload_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_SITE_ID}/drives/{SHAREPOINT_DRIVE_ID}/root:/{folder_path}/{unique_filename}:/content"
            response = requests.put(
                upload_url, headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/octet-stream"},
                data=file_content, timeout=60,
            )
            response.raise_for_status()
            return response.json()
        session_url = f"https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_SITE_ID}/drives/{SHAREPOINT_DRIVE_ID}/root:/{folder_path}/{unique_filename}:/createUploadSession"
        session_response = requests.post(session_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
        session_response.raise_for_status()
        upload_url = session_response.json()["uploadUrl"]
        response = requests.put(
            upload_url, headers={"Content-Length": str(len(file_content))}, data=file_content, timeout=120,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"[FileUpload] SharePoint upload timeout for {unique_filename}")
        raise HTTPException(status_code=504, detail="Upload timeout. Please try again.")
    except requests.exceptions.HTTPError as exc:
        logger.error(f"[FileUpload] SharePoint upload failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to upload to SharePoint: {exc}")


def upload_file(
    db: Session,
    *,
    tenant_id: Optional[int],
    entity_type: str,
    entity_id: str,
    file_content: bytes,
    original_filename: str,
    file_category: str = "GENERIC",
    uploaded_by: Optional[str] = None,
    graph_token_fn: Optional[Callable[[], str]] = None,
    scanner_client: Optional[Callable[[bytes], str]] = None,
) -> FileUpload:
    """
    BR-0118-02/AC-2/AC-3: the row is created with scan_status=PENDING,
    scanned immediately after upload, and only ever flips to CLEAN on an
    explicit clean result -- any exception (including the default
    unconfigured scanner) or unrecognized result lands on QUARANTINED,
    never auto-approved.
    """
    unique_filename = _generate_unique_filename(original_filename, entity_id)
    token_fn = graph_token_fn or get_graph_token
    access_token = token_fn()
    sharepoint_data = _upload_to_sharepoint(access_token, entity_type, entity_id, file_content, unique_filename)

    file_upload = FileUpload(
        tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
        file_category=file_category, original_filename=original_filename, unique_filename=unique_filename,
        file_size=len(file_content), file_extension=os.path.splitext(original_filename)[1].lower(),
        sharepoint_url=sharepoint_data.get("webUrl"), scan_status="PENDING", uploaded_by=uploaded_by,
    )
    db.add(file_upload)
    db.flush()

    scanner = scanner_client or _scan_unconfigured
    try:
        result = scanner(file_content)
    except Exception as exc:
        logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"[FileUpload] Scan failed for file_upload {file_upload.id}: {exc}")
        result = "error"
    file_upload.scan_status = "CLEAN" if result == "clean" else "QUARANTINED"
    db.add(file_upload)

    from app.services.activity_timeline_service import write_timeline_entry
    write_timeline_entry(
        db, tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
        actor_id=uploaded_by, actor_type="USER" if uploaded_by else "SYSTEM",
        action="FILE_UPLOADED", description=f"Uploaded {original_filename} ({file_category})",
    )
    return file_upload


def get_file_access_url(db: Session, file_upload_id: int) -> Optional[str]:
    """BR-0118-02: the access gate. Only CLEAN issues a URL -- PENDING and
    QUARANTINED both return None, never a URL."""
    file_upload = db.query(FileUpload).filter(FileUpload.id == file_upload_id).first()
    if file_upload is None or file_upload.scan_status != "CLEAN":
        return None
    return file_upload.sharepoint_url


def list_files_for_entity(db: Session, entity_type: str, entity_id: str, *, tenant_id: Optional[int] = None):
    query = db.query(FileUpload).filter(FileUpload.entity_type == entity_type, FileUpload.entity_id == entity_id)
    if tenant_id is not None:
        query = query.filter(FileUpload.tenant_id == tenant_id)
    return query.order_by(FileUpload.created_at.desc()).all()
