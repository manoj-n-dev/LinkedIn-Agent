"""Configuration module implementing FR-028 (bring-your-own-keys).

Rejects missing or placeholder values (such as REPLACE_ME) at startup,
and reports ONLY the names of bad settings, never values.
"""

import os
from typing import NamedTuple

REQUIRED_SETTINGS: tuple[str, ...] = (
    "TELEGRAM_BOT_TOKEN",
    "OWNER_TELEGRAM_ID",
    "DATABASE_URL",
    "GROQ_API_KEY",
    "GROQ_MODEL",
)

PLACEHOLDER_MARKER = "REPLACE_ME"


class ConfigError(Exception):
    """Raised when environment settings are missing, placeholder, or invalid."""

    def __init__(self, bad_setting_names: list[str]):
        self.bad_setting_names = sorted(bad_setting_names)
        names_str = ", ".join(self.bad_setting_names)
        super().__init__(f"Configuration error: Invalid or placeholder settings: {names_str}")


class Settings(NamedTuple):
    """Immutable application settings container."""

    telegram_bot_token: str
    owner_telegram_id: int
    database_url: str
    groq_api_key: str
    groq_model: str
    telegram_webhook_secret: str = ""
    owner_display_name: str = ""
    timezone: str = "Asia/Kolkata"
    gemini_api_key: str = ""
    token_encryption_key: str = ""
    linkedin_client_id: str = ""
    linkedin_client_secret: str = ""
    linkedin_redirect_url: str = ""
    publishing_enabled: bool = False
    kill_switch: bool = False


def _is_invalid_or_placeholder(value: str | None) -> bool:
    """Check if value is missing, empty, or contains placeholder text."""
    if value is None:
        return True
    stripped = value.strip()
    return not stripped or PLACEHOLDER_MARKER in stripped


def load_settings(env: dict[str, str] | None = None) -> Settings:
    """Load and validate settings from environment variables.

    Args:
        env: Optional dictionary for testing; defaults to os.environ.

    Returns:
        Settings: Validated settings tuple.

    Raises:
        ConfigError: When any required setting is missing, empty, or a placeholder.
    """
    source = os.environ if env is None else env
    bad_settings: list[str] = []

    for key in REQUIRED_SETTINGS:
        val = source.get(key)
        if _is_invalid_or_placeholder(val):
            bad_settings.append(key)

    # Validate OWNER_TELEGRAM_ID is numeric if provided
    owner_id_raw = source.get("OWNER_TELEGRAM_ID")
    owner_telegram_id = 0
    if "OWNER_TELEGRAM_ID" not in bad_settings and owner_id_raw is not None:
        try:
            owner_telegram_id = int(owner_id_raw.strip())
        except ValueError:
            bad_settings.append("OWNER_TELEGRAM_ID")

    if bad_settings:
        # Never include values in the error message
        raise ConfigError(bad_settings)

    # Parse boolean flags safely
    pub_enabled = source.get("PUBLISHING_ENABLED", "false").strip().lower() == "true"
    kill_sw = source.get("KILL_SWITCH", "false").strip().lower() == "true"

    return Settings(
        telegram_bot_token=source["TELEGRAM_BOT_TOKEN"].strip(),
        owner_telegram_id=owner_telegram_id,
        database_url=source["DATABASE_URL"].strip(),
        groq_api_key=source["GROQ_API_KEY"].strip(),
        groq_model=source["GROQ_MODEL"].strip(),
        telegram_webhook_secret=source.get("TELEGRAM_WEBHOOK_SECRET", "").strip(),
        owner_display_name=source.get("OWNER_DISPLAY_NAME", "").strip(),
        timezone=source.get("TIMEZONE", "Asia/Kolkata").strip() or "Asia/Kolkata",
        gemini_api_key=source.get("GEMINI_API_KEY", "").strip(),
        token_encryption_key=source.get("TOKEN_ENCRYPTION_KEY", "").strip(),
        linkedin_client_id=source.get("LINKEDIN_CLIENT_ID", "").strip(),
        linkedin_client_secret=source.get("LINKEDIN_CLIENT_SECRET", "").strip(),
        linkedin_redirect_url=source.get("LINKEDIN_REDIRECT_URL", "").strip(),
        publishing_enabled=pub_enabled,
        kill_switch=kill_sw,
    )
