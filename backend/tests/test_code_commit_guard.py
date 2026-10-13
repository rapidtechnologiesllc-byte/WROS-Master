"""Automated git commits are off unless a person turns them on for that checkout, so a run
on the production server can never commit into it (CEO 2026-10-12)."""
import pytest

from app.services.autonomous_sdlc_service import AutonomousSDLCError, _deploy_changes


def test_commits_refused_by_default(monkeypatch):
    monkeypatch.delenv("ALLOW_CODE_COMMITS", raising=False)
    with pytest.raises(AutonomousSDLCError, match="disabled"):
        _deploy_changes({"fixes_applied": 1})


def test_nothing_to_commit_needs_no_permission(monkeypatch):
    monkeypatch.delenv("ALLOW_CODE_COMMITS", raising=False)
    assert _deploy_changes({"fixes_applied": 0})["deployed"] is False
