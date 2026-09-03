"""
HRMS-0118's scan gate -- the Development & Review Standard's own named
example of a schema field that implies a rule without the enforcement
behind it: `CandidateDocument.is_virus_scanned` defaults to False and,
before this module, nothing anywhere in this codebase ever set it or
import logging
checked it before serving a file back to a browser.

Two pieces, matching this codebase's established pattern for
un-provisioned external services (WhatsApp/SMS's injectable
channel-sender, default "not configured" stub that raises rather than
silently no-op'ing):

  scan_document_content()  -- the real scan step, called once per
                               upload right after the SharePoint upload
                               + metadata save. No AV scanning vendor
                               is provisioned in this codebase (no API
                               credentials exist for one) -- the
                               default client raises
                               VirusScanUnavailable, exactly like
                               notification_service.ChannelNotConfigured.
  document_is_accessible()  -- the actual access gate. Per the
                               Development & Review Standard's
                               cross-cutting rule ("Compliance/security
                               gates -- dedup, R-01, virus scan -- fail
                               CLOSED, block the action if the check
                               can't be confirmed"), this is the
                               opposite posture from HRMS-1101's
                               fail-open router: anything other than an
                               explicit "clean" result blocks viewing,
                               including "no scan has run yet" and "the
                               scanner errored" -- both read as
                               virus_scan_result=None or "error", never
                               silently treated as safe.
"""
import logging
from typing import Callable, Optional

from app.models.document import CandidateDocument

VIRUS_SCAN_RESULTS = ("clean", "infected", "error")

logger = logging.getLogger(__name__)

class VirusScanUnavailable(Exception):
    """Raised by the default scanner client -- no AV scanning service is
    provisioned in this codebase yet."""


def _scan_unconfigured(file_content: bytes) -> str:
    raise VirusScanUnavailable("No virus-scanning service is provisioned in this codebase yet.")


def scan_document_content(
    document: CandidateDocument,
    file_content: bytes,
    *,
    scanner_client: Optional[Callable[[bytes], str]] = None,
) -> CandidateDocument:
    """
    Stamps the scan outcome onto `document` -- the caller commits (same
    "function mutates state, caller owns the transaction" convention as
    app.core.audit.write_audit_log()). A real scanner_client(file_content)
    must return one of VIRUS_SCAN_RESULTS; anything else it returns, or
    any exception it raises (including the default unconfigured stub),
    is recorded as "error" -- never silently upgraded to "clean".
    """
    client = scanner_client or _scan_unconfigured
    try:
        result = client(file_content)
        if result not in VIRUS_SCAN_RESULTS:
            result = "error"
    except Exception:
        result = "error"

    document.is_virus_scanned = True
    document.virus_scan_result = result
    return document


def document_is_accessible(document: CandidateDocument) -> bool:
    """The access gate -- fail closed. Only an explicit "clean" result
    unlocks viewing; unset (None), "error", and "infected" all block."""
    return document.virus_scan_result == "clean"
