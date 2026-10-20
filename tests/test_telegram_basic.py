"""Tests for basic Telegram bot handlers (FR-002, FR-031)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import Settings
from src.telegram.handlers import help_command, start_command
from telegram import Chat, Message, Update, User


@pytest.fixture
def fake_settings():
    """Create sample settings for test."""
    return Settings(
        telegram_bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456",
        owner_telegram_id=123456789,
        owner_display_name="Founder",
        database_url="sqlite:///test.db",
        groq_api_key="fake-groq-key",
        groq_model="llama-3.3-70b-versatile",
    )


def create_mock_update_and_context(fake_settings: Settings, text: str = "/start"):
    """Helper to construct mock Telegram Update and Context objects."""
    user = User(id=123456789, first_name="Owner", is_bot=False)
    chat = Chat(id=123456789, type=Chat.PRIVATE)

    message = MagicMock(spec=Message)
    message.from_user = user
    message.chat = chat
    message.text = text
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_message = message
    update.effective_user = user
    update.effective_chat = chat

    context = MagicMock()
    context.bot_data = {"settings": fake_settings}

    return update, context, message.reply_text


@pytest.mark.asyncio
async def test_start_command_with_display_name(fake_settings):
    """FR-002, FR-031: /start greeting contains display name and welcome tour."""
    update, context, reply_mock = create_mock_update_and_context(fake_settings, "/start")

    await start_command(update, context)

    reply_mock.assert_awaited_once()
    reply_text = reply_mock.call_args[0][0]
    assert "Hi Founder." in reply_text
    assert "I am your private LinkedIn helper" in reply_text
    assert "Type /help to see what I can do" in reply_text


@pytest.mark.asyncio
async def test_start_command_without_display_name(fake_settings):
    """FR-031: /start greeting works without display name."""
    settings_no_name = fake_settings._replace(owner_display_name="")
    update, context, reply_mock = create_mock_update_and_context(settings_no_name, "/start")

    await start_command(update, context)

    reply_mock.assert_awaited_once()
    reply_text = reply_mock.call_args[0][0]
    assert reply_text.startswith("Hi. I am your private LinkedIn helper")


@pytest.mark.asyncio
async def test_help_command(fake_settings):
    """FR-002: /help returns plain English command list."""
    update, context, reply_mock = create_mock_update_and_context(fake_settings, "/help")

    await help_command(update, context)

    reply_mock.assert_awaited_once()
    reply_text = reply_mock.call_args[0][0]
    assert "/start - Welcome" in reply_text
    assert "/draft <idea>" in reply_text
    assert "/status" in reply_text
    assert "/comment" in reply_text
    assert "/connections" in reply_text
    assert "/pause" in reply_text
    assert "/resume" in reply_text
