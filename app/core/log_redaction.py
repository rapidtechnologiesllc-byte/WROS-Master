"""
HRMS-0117 / Phase 1 B1 -- redact known secret patterns before any log
line is written, console or file. This is a logging.Filter, so it runs
on every record regardless of which handler(s) end up writing it.

Patterns covered (matched against what actually showed up in this
codebase's .env): database connection strings with an embedded
password, PEM-format private/public keys, and generic
"<secret-like-name>=<long-value>" or "<secret-like-name>: <long-value>"
pairs for API keys / client secrets / tokens.

This is a safety net, not a substitute for not logging secrets in the
first place -- but per B1's acceptance test, it's the backstop for the
case where something upstream logs more than it should.
"""
import logging
import re

_REDACTED = "***REDACTED***"

_PATTERNS = [
    # scheme://user:password@host  -->  scheme://user:***REDACTED***@host
    re.compile(r"(://[^:@/\s]+:)([^@\s]+)(@)"),
    # PEM blocks (private or public key)
    re.compile(r"-----BEGIN [A-Z ]*(PRIVATE|PUBLIC) KEY-----.*?-----END [A-Z ]*(PRIVATE|PUBLIC) KEY-----", re.DOTALL),
    # KEY=value / "key": "value" style secrets, keyed by name
    re.compile(
        r"(?i)(secret|password|passwd|pwd|api[_-]?key|client[_-]?secret|token|"
        r"jwt_private_key|jwt_public_key)"
        r"([\"']?\s*[:=]\s*[\"']?)([^\s\"',}]{4,})",
    ),
]


def redact(text: str) -> str:
    if not text:
        return text
    result = text
    result = _PATTERNS[0].sub(r"\1" + _REDACTED + r"\3", result)
    result = _PATTERNS[1].sub(_REDACTED, result)
    result = _PATTERNS[2].sub(lambda m: f"{m.group(1)}{m.group(2)}{_REDACTED}", result)
    return result


class RedactingFilter(logging.Filter):
    """Attach to every handler so redaction can't be bypassed by adding a new one."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(str(record.msg))
        except Exception:
            # Never let redaction itself break logging -- fall through
            # with the original message rather than raise.
            pass
        # args are formatted into msg by the logging module later; if any
        # arg itself is a secret-shaped string, redact it too.
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact(str(v)) for k, v in record.args.items()}
            else:
                record.args = tuple(redact(str(a)) for a in record.args)
        return True
