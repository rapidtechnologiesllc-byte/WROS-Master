"""Panel vs Flash calibration: Flash's job match score against the panel's decision."""
import os
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET", "test-secret-0123456789abcdef0123456789abcdef")

from app.services import interview_calibration_service as cal  # noqa: E402


def fb(rec, tech=None):
    return SimpleNamespace(recommendation=rec, technical_score=tech)


def test_panel_majority_decides_and_ties_are_undecided():
    assert cal._panel_view([fb("Hire", 8), fb("Hire", 6), fb("Reject", 3)])["verdict"] == "advance"
    assert cal._panel_view([fb("Reject"), fb("Reject"), fb("Hire")])["verdict"] == "reject"
    assert cal._panel_view([fb("Hire"), fb("Reject")])["verdict"] == "undecided"
    assert cal._panel_view([])["verdict"] is None
    assert cal._panel_view([fb("Hire", 8), fb("Hire", 6)])["avg_technical_score"] == 7.0


def test_summary_counts_agreement_and_both_kinds_of_miss():
    rows = [
        {"agree": True, "flash_verdict": "advance"},
        {"agree": False, "flash_verdict": "advance"},   # Flash too optimistic
        {"agree": False, "flash_verdict": "reject"},    # Flash too strict
        {"agree": None, "flash_verdict": None},          # no Flash score: not compared
    ]
    with patch.object(cal, "compare_interview", side_effect=rows):
        summary = cal.calibration_summary(None, [object()] * 4, 60)
    assert summary["compared"] == 3 and summary["agreed"] == 1 and summary["agreement_pct"] == 33.3
    assert summary["flash_too_optimistic"] == 1 and summary["flash_too_strict"] == 1
    assert len(summary["disagreements"]) == 2
