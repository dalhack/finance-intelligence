import hashlib
import json
import logging
import re
from datetime import UTC, datetime

# Regex patterns for sensitive data redaction
UUID_PATTERN = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
PATH_PATTERN = re.compile(r"(?:/[a-zA-Z0-9_\.\-]+)+|(?:[a-zA-Z]:\\[a-zA-Z0-9_\.\-\\]+)")
URL_PATTERN = re.compile(r"postgres(?:ql)?(?:\+[a-zA-Z0-9_]+)?://[^\s]+")
SQL_PATTERN = re.compile(r"(?:SELECT|INSERT|UPDATE|DELETE|ALTER|DROP|CREATE)\s+[^\n;]+", re.IGNORECASE)


def redact_sensitive_text(text: str) -> str:
    if not text:
        return ""
    text = URL_PATTERN.sub("[REDACTED_URL]", text)
    text = UUID_PATTERN.sub("[REDACTED_UUID]", text)
    text = PATH_PATTERN.sub("[REDACTED_PATH]", text)
    text = SQL_PATTERN.sub("[REDACTED_SQL]", text)
    return text


class PseudonymizingFormatter(logging.Formatter):
    def __init__(self, salt: str = "dev-salt"):
        super().__init__()
        self.salt = salt

    def pseudonymize(self, raw_val: str) -> str:
        if not raw_val:
            return ""
        return hashlib.sha256(f"{self.salt}:{raw_val}".encode()).hexdigest()[:16]

    def format(self, record: logging.LogRecord) -> str:
        raw_msg = record.getMessage()
        safe_msg = redact_sensitive_text(raw_msg)

        exc_text = None
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
            exc_text = redact_sensitive_text(exc_text)

        log_payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", "api"),
            "environment": getattr(record, "environment", "development"),
            "request_id": getattr(record, "request_id", None),
            "correlation_id": getattr(record, "correlation_id", None),
            "user_hash": self.pseudonymize(getattr(record, "raw_user_id", "")),
            "org_hash": self.pseudonymize(getattr(record, "raw_org_id", "")),
            "event": safe_msg,
        }
        if exc_text:
            log_payload["exception"] = exc_text

        return json.dumps(log_payload)


def setup_logging(salt: str = "dev-salt") -> logging.Logger:
    logger = logging.getLogger("finance_intelligence")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(PseudonymizingFormatter(salt=salt))
    logger.addHandler(handler)
    return logger
