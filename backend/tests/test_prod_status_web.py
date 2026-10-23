"""prod_status.py web checks: the site is whatever FRONTEND_BASE_URL says, never a hardcoded host,
and an unset FRONTEND_BASE_URL (the localhost default) is reported as a failure."""
import importlib.util
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "prod_status.py"


@pytest.fixture
def prod_status(monkeypatch):
    spec = importlib.util.spec_from_file_location("prod_status_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    monkeypatch.setattr(module, "sh", lambda label, cmd, timeout=15: calls.append((label, cmd)))
    return module, calls


def test_checks_the_configured_site_and_its_domain(prod_status):
    module, calls = prod_status
    module.web_status("https://portal.example.org/")
    commands = " ".join(cmd for _, cmd in calls)
    assert "portal.example.org" in commands and "whois example.org" in commands
    assert "blitzenx" not in commands


def test_localhost_default_is_reported_and_nothing_is_probed(prod_status, capsys):
    module, calls = prod_status
    module.web_status("http://localhost:3000")
    assert calls == []
    assert "[FAIL] FRONTEND_BASE_URL is not set" in capsys.readouterr().out


def test_a_url_without_a_host_fails_loudly(prod_status):
    module, _ = prod_status
    with pytest.raises(ValueError):
        module.web_status("not-a-url")
