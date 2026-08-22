"""
HRMS-0118 -- the virus-scan gate. Proves the Development & Review
Standard's own named example is actually fixed: `is_virus_scanned`/
`virus_scan_result` get set for real on every upload, and viewing is
blocked unless the result is explicitly "clean" (fail closed, not
fail open -- the opposite posture from HRMS-1101's router, and
deliberately so per the Standard's cross-cutting rule).
"""
import pytest

from app.models.document import CandidateDocument
from app.services.virus_scan_service import (
    VirusScanUnavailable,
    document_is_accessible,
    scan_document_content,
)

def _make_document(**overrides):
    defaults = dict(
        candidate_id="C-1", document_type="resume", original_filename="resume.pdf",
        stored_filename="resume_stored.pdf", file_size=1024, file_extension=".pdf",
        uploaded_by="C-1",
    )
    defaults.update(overrides)
    return CandidateDocument(**defaults)

def test_default_unconfigured_scanner_records_error_not_clean():
    document = _make_document()
    scan_document_content(document, b"file bytes")
    assert document.is_virus_scanned is True
    assert document.virus_scan_result == "error"

def test_default_unconfigured_scanner_raises_when_called_directly():
    from app.services.virus_scan_service import _scan_unconfigured
    with pytest.raises(VirusScanUnavailable):
        _scan_unconfigured(b"file bytes")

def test_clean_result_from_real_scanner_is_recorded():
    document = _make_document()
    scan_document_content(document, b"file bytes", scanner_client=lambda content: "clean")
    assert document.virus_scan_result == "clean"
    assert document.is_virus_scanned is True

def test_infected_result_from_real_scanner_is_recorded():
    document = _make_document()
    scan_document_content(document, b"file bytes", scanner_client=lambda content: "infected")
    assert document.virus_scan_result == "infected"

def test_scanner_returning_unknown_value_is_recorded_as_error():
    document = _make_document()
    scan_document_content(document, b"file bytes", scanner_client=lambda content: "definitely_safe_trust_me")
    assert document.virus_scan_result == "error"

def test_scanner_raising_is_recorded_as_error_not_left_unset():
    def broken_scanner(content):
        raise RuntimeError("vendor API timeout")

    document = _make_document()
    scan_document_content(document, b"file bytes", scanner_client=broken_scanner)
    assert document.is_virus_scanned is True
    assert document.virus_scan_result == "error"

def test_scanner_receives_the_actual_file_bytes():
    seen = {}

    def recording_scanner(content):
        seen["content"] = content
        return "clean"

    document = _make_document()
    scan_document_content(document, b"specific file content", scanner_client=recording_scanner)
    assert seen["content"] == b"specific file content"

# ---------------------------------------------------------------------------
# document_is_accessible -- fail closed
# ---------------------------------------------------------------------------

def test_not_accessible_before_any_scan_has_run():
    document = _make_document()
    assert document_is_accessible(document) is False

def test_not_accessible_when_infected():
    document = _make_document(is_virus_scanned=True, virus_scan_result="infected")
    assert document_is_accessible(document) is False

def test_not_accessible_when_scan_errored():
    document = _make_document(is_virus_scanned=True, virus_scan_result="error")
    assert document_is_accessible(document) is False

def test_accessible_only_when_explicitly_clean():
    document = _make_document(is_virus_scanned=True, virus_scan_result="clean")
    assert document_is_accessible(document) is True
