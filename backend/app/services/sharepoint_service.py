"""
SharePoint Service
==================
Thin wrapper around the Microsoft Graph REST API for SharePoint Drive operations.
Uses the application-level service-account token (AZURE_* credentials) already
configured in app/core/graph_auth.py — no user sign-in required.
import logging
"""

import io
import os
from typing import Optional
from urllib.parse import quote

import requests

from app.core.graph_auth import get_graph_token
from app.core.logging import logger


# ---------------------------------------------------------------------------
# Config (read once at import time, same pattern as the rest of the codebase)
# ---------------------------------------------------------------------------
SITE_ID = os.getenv("SHAREPOINT_SITE_ID", "")
DRIVE_ID = os.getenv("SHAREPOINT_DRIVE_ID", "")
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers() -> dict:
    """Return Auth + JSON headers for every Graph request."""
    return {
        "Authorization": f"Bearer {get_graph_token()}",
        "Accept": "application/json",
    }


def _drive_path_url(path: str) -> str:
    """
    Build the Graph API URL for a path inside the configured SharePoint drive.

    The drive root is already the document library root (e.g. "HRMS Documents"),
    so paths should be relative to that root:
        "templates/Internship Offer letter.docx"   ✓
        "HRMS Documents/templates/..."             ✗ (double-prefix)

    Spaces and special characters in the path are percent-encoded;
    forward slashes (segment separators) are kept as-is.
    """
    encoded = quote(path, safe="/")
    return f"{_GRAPH_BASE}/sites/{SITE_ID}/drives/{DRIVE_ID}/root:/{encoded}"


def _get_item_id(path: str) -> Optional[str]:
    """
    Resolve the Graph driveItem ID for a given path.
    Returns None if the item is not found.
    """
    meta_url = f"{_drive_path_url(path)}:"
    resp = requests.get(meta_url, headers=_headers(), timeout=30)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("id")


def _create_or_get_sharing_link(item_id: str, scope: str = "organization") -> Optional[str]:
    """
    Create (or return an existing) non-expiring sharing link for a driveItem.

    Uses Microsoft Graph POST /drives/{driveId}/items/{itemId}/createLink.
    If a link with the same type+scope already exists, Graph returns it unchanged.

    Args:
        item_id: The Graph driveItem ID.
        scope:   "organization" — only org members can open the link (recommended).
                 "anonymous"   — anyone with the link can open it (public files only).

    Returns:
        The sharing webUrl (a permanent link), or None on failure.
    """
    url = f"{_GRAPH_BASE}/drives/{DRIVE_ID}/items/{item_id}/createLink"
    payload = {
        "type": "view",      # read-only
        "scope": scope,      # "organization" or "anonymous"
        # No expirationDateTime → link never expires (unless org policy enforces one)
    }
    headers = _headers()
    headers["Content-Type"] = "application/json"

    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code in (200, 201):
        link = resp.json().get("link", {})
        web_url = link.get("webUrl")
        logger.info(f"SharePoint createLink — {scope} view link: {web_url}")
        return web_url
    else:
        try:
            err = resp.json().get("error", {}).get("message", resp.text)
        except Exception:
            err = resp.text
        logger.warning(f"SharePoint createLink failed (status={resp.status_code}): {err}")
        raise ValueError("Operation failed")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def download_file(path: str) -> bytes:
    """
    Download a file from SharePoint and return its raw bytes.

    Uses the authenticated Graph /content endpoint — this is always valid as long
    as the app credentials are valid, unlike @microsoft.graph.downloadUrl which
    expires within ~1 day.

    Args:
        path: SharePoint-relative path, e.g.
              "HRMS Documents/templates/Internship Offer letter.docx"

    Returns:
        File content as bytes.

    Raises:
        HTTPException / requests.HTTPError on failure.
    """
    if not SITE_ID or not DRIVE_ID:
        raise RuntimeError(
            "SHAREPOINT_SITE_ID and SHAREPOINT_DRIVE_ID must be set in .env"
        )

    # Use the Graph /content endpoint with the app's auth token — never expires
    content_url = f"{_drive_path_url(path)}:/content"
    logger.info(f"SharePoint download — fetching content for: {path}")
    resp = requests.get(
        content_url,
        headers=_headers(),
        allow_redirects=True,
        timeout=60,
    )
    resp.raise_for_status()

    logger.info(
        f"SharePoint download — success ({len(resp.content)} bytes): {path}"
    )
    return resp.content


def upload_file(path: str, content: bytes, content_type: str = "application/octet-stream") -> str:
    """
    Upload a file to SharePoint (creates or overwrites).

    Args:
        path: SharePoint-relative destination path, e.g.
              "HRMS Documents/generated-offers/CAND001/offer_42.docx"
        content: Raw bytes to upload.
        content_type: MIME type (default application/octet-stream).

    Returns:
        Web URL of the uploaded file (str).

    Raises:
        HTTPError on failure.
    """
    if not SITE_ID or not DRIVE_ID:
        raise RuntimeError(
            "SHAREPOINT_SITE_ID and SHAREPOINT_DRIVE_ID must be set in .env"
        )

    upload_url = f"{_drive_path_url(path)}:/content"
    headers = _headers()
    headers["Content-Type"] = content_type

    logger.info(f"SharePoint upload — uploading {len(content)} bytes to: {path}")
    resp = requests.put(upload_url, headers=headers, data=content, timeout=120)
    resp.raise_for_status()

    web_url: str = resp.json().get("webUrl", "")
    logger.info(f"SharePoint upload — success: {web_url}")
    return web_url


def get_file_download_link(path: str) -> Optional[str]:
    """
    Return a **non-expiring** sharing link for a SharePoint file.

    Strategy:
      1. Resolve the driveItem ID from the file path.
      2. Call POST /createLink (type=view, scope=organization) to get a
         permanent sharing link. Graph returns the same link on repeated
         calls — it does NOT create duplicates.

    The returned `webUrl` opens the file in the browser (SharePoint viewer).
    Anyone inside the organisation can use the link without signing in to
    the app — the link itself handles authentication via SharePoint.

    Falls back to None if the file doesn't exist or the call fails.

    Args:
        path:  Drive-relative file path.
        scope: "organization" (default, internal-only) or "anonymous" (public).

    Returns:
        A permanent sharing webUrl, or None.
    """
    try:
        meta_url = f"{_drive_path_url(path)}:"
        resp = requests.get(meta_url, headers=_headers(), timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("@microsoft.graph.downloadUrl")

    except Exception as exc:
       logger.error(f"Error: {str(exc)}", exc_info=True)
        logger.warning(f"SharePoint get_file_download_link failed for {path}: {exc}")
        raise ValueError("Operation failed")


def list_folder(folder_path: str) -> list[dict]:
    """
    List all items (files & sub-folders) inside a SharePoint drive folder.

    Args:
        folder_path: Drive-relative folder path, e.g. "templates"

    Returns:
        List of dicts, each containing:
          name, type (file/folder), size, web_url, download_url,
          created_at, modified_at, mime_type
    """
    encoded = quote(folder_path, safe="/")
    children_url = (
        f"{_GRAPH_BASE}/sites/{SITE_ID}/drives/{DRIVE_ID}"
        f"/root:/{encoded}:/children"
        f"?$select=name,file,folder,size,webUrl,createdDateTime,lastModifiedDateTime"
        f"&$orderby=name"
    )

    logger.info(f"SharePoint list_folder — listing: {folder_path!r}")
    resp = requests.get(children_url, headers=_headers(), timeout=30)

    if resp.status_code == 404:
        raise FileNotFoundError(
            f"Folder not found in SharePoint: {folder_path!r}\n"
            f"Check SHAREPOINT_TEMPLATE_FOLDER in .env and the drive ID."
        )
    resp.raise_for_status()

    items = []
    for item in resp.json().get("value", []):
        is_file   = "file" in item
        is_folder = "folder" in item

        download_url = None
        if is_file:
            download_url = item.get("@microsoft.graph.downloadUrl")

        items.append({
            "name":        item.get("name"),
            "type":        "file" if is_file else ("folder" if is_folder else "unknown"),
            "size_bytes":  item.get("size"),
            "mime_type":   item.get("file", {}).get("mimeType") if is_file else None,
            "web_url":     item.get("webUrl"),
            "download_url": download_url,
            "created_at":  item.get("createdDateTime"),
            "modified_at": item.get("lastModifiedDateTime"),
        })

    logger.info(f"SharePoint list_folder — found {len(items)} items in {folder_path!r}")
    return items
