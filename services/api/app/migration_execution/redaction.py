"""Log and Exception Redaction Utilities for Migration Execution."""

import re
from typing import Any


def redact_text(text: str) -> str:
    """Redacts sensitive information like passwords, keys, and tokens from log strings."""
    if not text:
        return ""

    # Redact connection URIs: postgresql://user:password@host
    text = re.sub(r"://([^:]+):([^@]+)@", r"://\1:[REDACTED]@", text)

    # Redact key-value pairs in logs/strings
    text = re.sub(
        r"(password|secret|token|key|authorization|bearer)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text,
        flags=re.IGNORECASE,
    )

    # Redact Authorization headers
    text = re.sub(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", "Bearer [REDACTED]", text, flags=re.IGNORECASE)

    return text


def sanitize_dict_for_logging(data: dict[str, Any]) -> dict[str, Any]:
    """Returns a copy of the dictionary with sensitive fields redacted."""
    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(s in key_lower for s in ("password", "secret", "token", "key", "authorization", "auth")):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict_for_logging(value)
        else:
            sanitized[key] = value
    return sanitized
