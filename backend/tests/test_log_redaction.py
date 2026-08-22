"""
Proves HRMS-0117 / Phase 1 B1: known secret patterns are redacted
before a log record is emitted, and setup_logging() actually wires the
redaction filter in (not just available-but-unused).
"""
import logging

from app.core.log_redaction import redact, RedactingFilter
from app.core.logging import setup_logging

def test_redacts_password_in_connection_string():
    text = "connecting to mssql+pyodbc://sa:Sup3rSecret!@46.224.149.7/onboard2"
    out = redact(text)
    assert "Sup3rSecret!" not in out
    assert "sa:***REDACTED***@" in out

def test_redacts_pem_private_key_block():
    text = (
        "loaded key: -----BEGIN PRIVATE KEY-----\n"
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ==\n"
        "-----END PRIVATE KEY-----\ndone"
    )
    out = redact(text)
    assert "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQ==" not in out
    assert "***REDACTED***" in out

def test_redacts_named_secret_like_values():
    text = 'CLIENT_SECRET=testSecretValueThatShouldBeRedacted should not appear'
    out = redact(text)
    assert "testSecretValueThatShouldBeRedacted" not in out

def test_setup_logging_wires_redaction_filter_by_default():
    logger = setup_logging(log_to_file=False, log_to_console=False)
    assert any(isinstance(f, RedactingFilter) for f in logger.filters)

def test_end_to_end_secret_never_reaches_a_handler(capsys):
    logger = setup_logging(log_to_file=False, log_to_console=True)
    logger.error("DB connect failed: mssql+pyodbc://sa:Sup3rSecret!@46.224.149.7/onboard2")
    captured = capsys.readouterr()
    assert "Sup3rSecret!" not in captured.out
    assert "Sup3rSecret!" not in captured.err
