"""Tests for owner-only authentication (FR-001, SEC-001, SEC-002).

Mandatory tests:
- T-AUTH-01: Non-owner message -> no reply, no feature access (FR-001)
- T-AUTH-02: Non-owner button tap / callback -> ignored (FR-001, SEC-002)
- T-AUTH-03: Every handler rejects a non-owner (fuzz over all handlers) (SEC-002)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User

from src.config import Settings
from src.telegram_bot.auth import owner_only
from src.telegram_bot.handlers import help_command, start_command

OWNER_ID = 111111111
STRANGER_ID = 999999999


@pytest.fixture
def test_settings():
    """Settings with configured owner ID."""
    return Settings(
        telegram_bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456",
        owner_telegram_id=OWNER_ID,
        owner_display_name="Founder",
        database_url="sqlite:///test.db",
        groq_api_key="fake-groq-key",
        groq_model="llama-3.3-70b-versatile",
    )


def build_mock_update(user_id: int, is_callback: bool = False):
    """Create a mock update with specific user ID and type."""
    user = User(id=user_id, first_name="TestUser", is_bot=False)
    chat = Chat(id=user_id, type=Chat.PRIVATE)

    message = MagicMock(spec=Message)
    message.from_user = user
    message.chat = chat
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message

    if is_callback:
        query = MagicMock(spec=CallbackQuery)
        query.from_user = user
        query.data = "test_callback_data"
        query.answer = AsyncMock()
        query.message = message
        update.callback_query = query
    else:
        update.callback_query = None

    return update, message.reply_text


@pytest.mark.asyncio
async def test_auth_01_non_owner_message_gets_no_reply(test_settings):
    """T-AUTH-01: Non-owner message -> no reply, no feature access (FR-001)."""
    update, reply_mock = build_mock_update(user_id=STRANGER_ID, is_callback=False)
    context = MagicMock()
    context.bot_data = {"settings": test_settings}

    # Stranger invokes /start
    result = await start_command(update, context)

    # Must return None and send zero replies
    assert result is None
    reply_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_auth_02_non_owner_button_tap_ignored(test_settings):
    """T-AUTH-02: Non-owner button tap -> ignored (FR-001, SEC-002)."""
    update, reply_mock = build_mock_update(user_id=STRANGER_ID, is_callback=True)
    context = MagicMock()
    context.bot_data = {"settings": test_settings}

    # Dummy callback handler wrapped with owner_only
    @owner_only
    async def sample_callback_handler(upd: Update, ctx):
        await upd.callback_query.answer("Action executed")

    result = await sample_callback_handler(update, context)

    assert result is None
    # Ensure neither message nor callback query was answered
    update.callback_query.answer.assert_not_awaited()
    reply_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_auth_03_every_handler_rejects_non_owner(test_settings):
    """T-AUTH-03: Fuzz over all registered handlers with a non-owner ID (SEC-002)."""
    handlers_to_fuzz = [start_command, help_command]

    for handler in handlers_to_fuzz:
        update, reply_mock = build_mock_update(user_id=STRANGER_ID, is_callback=False)
        context = MagicMock()
        context.bot_data = {"settings": test_settings}

        result = await handler(update, context)
        assert result is None, f"Handler {handler.__name__} did not reject non-owner!"
        reply_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_owner_access_granted(test_settings):
    """Owner ID receives proper response."""
    update, reply_mock = build_mock_update(user_id=OWNER_ID, is_callback=False)
    context = MagicMock()
    context.bot_data = {"settings": test_settings}

    await start_command(update, context)

    reply_mock.assert_awaited_once()
    assert "Hi Founder." in reply_mock.call_args[0][0]
