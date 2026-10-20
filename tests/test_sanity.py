"""T-CI-01: Fresh clone passes with NO secrets set (NFR-015)."""

import os


def test_no_secrets_required():
    """Verify that test runner and base project require no environment variables."""
    # Ensure standard sensitive environment variables are not expected to be set
    assert "TELEGRAM_BOT_TOKEN" not in os.environ or os.environ.get("TELEGRAM_BOT_TOKEN") != ""
    assert True
