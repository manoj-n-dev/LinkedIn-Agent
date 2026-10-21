"""Logging configuration with secret redaction filter (SEC-017, NFR-006).

Redacts bot tokens, API keys, private keys, and passwords from all log records.
"""

import logging
import re

# Patterns matching tokens and API keys
SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{25,}\b"),  # Telegram bot token
    re.compile(r"gsk_[A-Za-z0-9]{16,}"),  # Groq API key
    re.compile(r"AIza[0-9A-Za-z-_]{16,}"),  # Google API key
    re.compile(
        r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC )?PRIVATE KEY-----"
    ),
    re.compile(
        r"(token|secret|password|key)\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{8,})['\"]?",
        re.IGNORECASE,
    ),
]

REDACTED_TEXT = "[REDACTED]"


class RedactingFilter(logging.Filter):
    """Logging filter that scrubs sensitive patterns from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in SENSITIVE_PATTERNS:
            message = pattern.sub(REDACTED_TEXT, message)

        record.msg = message
        record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with the RedactingFilter."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
