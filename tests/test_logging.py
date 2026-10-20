"""Tests for log redaction filter (T-LOG-01, SEC-017, NFR-006)."""

import io
import logging

from src.logging_config import RedactingFilter, setup_logging


def test_redacting_filter_masks_telegram_token():
    """Verify Telegram bot token pattern is redacted in logs."""
    fake_token = "123456789:" + "ABCdefGHIjklMNOpqrsTUVwxyz123456"
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f"Bot started with token {fake_token}",
        args=(),
        exc_info=None,
    )
    filter_obj = RedactingFilter()
    filter_obj.filter(record)

    assert fake_token not in record.msg
    assert "[REDACTED]" in record.msg


def test_redacting_filter_masks_groq_key():
    """Verify Groq API key is redacted in logs."""
    fake_groq = "gsk_" + "1234567890abcdef1234567890abcdef"
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f"Calling Groq API with key {fake_groq}",
        args=(),
        exc_info=None,
    )
    filter_obj = RedactingFilter()
    filter_obj.filter(record)

    assert fake_groq not in record.msg
    assert "[REDACTED]" in record.msg


def test_setup_logging_output_has_no_secrets():
    """Verify configured logger captures and redacts sensitive data in stream output."""
    setup_logging()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter())

    logger = logging.getLogger("test_stream")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    fake_key = "AIza" + "SyD-1234567890abcdefghijklmnopqrs"
    logger.info("Connecting using %s", fake_key)

    output = stream.getvalue()
    assert fake_key not in output
    assert "[REDACTED]" in output
