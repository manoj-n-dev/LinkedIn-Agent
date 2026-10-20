"""Tests for configuration loader (FR-028, T-CFG-01, T-CFG-02)."""

import pytest

from src.config import ConfigError, load_settings


def test_empty_environment_raises_config_error(monkeypatch):
    """T-CFG-01: Empty environment -> startup stops, prints setting NAMES only (FR-028)."""
    # Empty environment
    monkeypatch.setattr("os.environ", {})

    with pytest.raises(ConfigError) as exc_info:
        load_settings()

    error_message = str(exc_info.value)
    expected_names = [
        "TELEGRAM_BOT_TOKEN",
        "OWNER_TELEGRAM_ID",
        "DATABASE_URL",
        "GROQ_API_KEY",
        "GROQ_MODEL",
    ]
    for name in expected_names:
        assert name in error_message

    # Ensure no values are in the error message
    assert "None" not in error_message


def test_env_example_copied_unchanged_raises_config_error(monkeypatch):
    """T-CFG-02: .env.example copied unchanged -> startup stops (FR-028)."""
    placeholder_env = {
        "TELEGRAM_BOT_TOKEN": "REPLACE_ME",
        "TELEGRAM_WEBHOOK_SECRET": "REPLACE_ME",
        "OWNER_TELEGRAM_ID": "REPLACE_ME",
        "DATABASE_URL": "REPLACE_ME",
        "GROQ_API_KEY": "REPLACE_ME",
        "GROQ_MODEL": "REPLACE_ME",
    }

    with pytest.raises(ConfigError) as exc_info:
        load_settings(env=placeholder_env)

    error_message = str(exc_info.value)
    # All placeholder keys must be flagged
    assert "TELEGRAM_BOT_TOKEN" in error_message
    assert "OWNER_TELEGRAM_ID" in error_message
    assert "DATABASE_URL" in error_message
    assert "GROQ_API_KEY" in error_message
    assert "GROQ_MODEL" in error_message


def test_invalid_owner_id_reported():
    """Non-numeric OWNER_TELEGRAM_ID must be flagged."""
    env = {
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456",
        "OWNER_TELEGRAM_ID": "not-a-number",
        "DATABASE_URL": "sqlite:///test.db",
        "GROQ_API_KEY": "fake-groq-key-test",
        "GROQ_MODEL": "llama-3.3-70b-versatile",
    }

    with pytest.raises(ConfigError) as exc_info:
        load_settings(env=env)

    assert "OWNER_TELEGRAM_ID" in str(exc_info.value)
    assert "not-a-number" not in str(exc_info.value)


def test_valid_configuration_loads_successfully():
    """Valid fake configuration loads cleanly."""
    valid_env = {
        "TELEGRAM_BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456",
        "OWNER_TELEGRAM_ID": "987654321",
        "OWNER_DISPLAY_NAME": "Founder",
        "DATABASE_URL": "sqlite:///test.db",
        "GROQ_API_KEY": "fake-groq-key-test",
        "GROQ_MODEL": "llama-3.3-70b-versatile",
        "TIMEZONE": "Asia/Kolkata",
        "PUBLISHING_ENABLED": "false",
        "KILL_SWITCH": "false",
    }

    settings = load_settings(env=valid_env)
    assert settings.telegram_bot_token == "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456"
    assert settings.owner_telegram_id == 987654321
    assert settings.owner_display_name == "Founder"
    assert settings.timezone == "Asia/Kolkata"
    assert settings.publishing_enabled is False
    assert settings.kill_switch is False
