"""Tests for Owner ID Helper (FR-029)."""

from unittest.mock import MagicMock

from telegram import Update, User

from src.owner_id_helper import extract_sender_info, format_owner_id_output


def test_extract_sender_info_from_valid_user():
    """Verify sender information is cleanly extracted."""
    user = User(id=555666777, first_name="Alice", username="alice_dev", is_bot=False)
    update = MagicMock(spec=Update)
    update.effective_user = user

    info = extract_sender_info(update)
    assert info is not None
    assert info["user_id"] == 555666777
    assert info["first_name"] == "Alice"
    assert info["username"] == "alice_dev"


def test_extract_sender_info_empty_when_no_user():
    """Verify None is returned when update has no user."""
    update = MagicMock(spec=Update)
    update.effective_user = None

    info = extract_sender_info(update)
    assert info is None


def test_format_owner_id_output():
    """Verify output contains clear instructions and user ID."""
    info = {"user_id": 999888777, "first_name": "Bob", "username": "bob_build"}
    formatted = format_owner_id_output(info)

    assert "999888777" in formatted
    assert "OWNER_TELEGRAM_ID=999888777" in formatted
    assert "Bob" in formatted
