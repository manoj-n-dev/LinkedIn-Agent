"""Owner-only authorization module (FR-001, SEC-001, SEC-002).

Guarantees the bot only responds to the owner configured in OWNER_TELEGRAM_ID.
Strangers receive NO reply, preventing information disclosure or probing.
"""

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from src.config import Settings

logger = logging.getLogger(__name__)

HandlerFunc = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]


def is_owner(update: Update, settings: Settings) -> bool:
    """Verify if the update originated from the designated owner."""
    user = update.effective_user
    if not user:
        return False
    return user.id == settings.owner_telegram_id


def owner_only(handler: HandlerFunc) -> HandlerFunc:
    """Decorator to enforce owner-only access on commands and callbacks.

    Any update originating from a non-owner ID is dropped immediately
    with NO reply and NO error message sent back to Telegram.
    """

    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        settings: Settings | None = context.bot_data.get("settings")
        if not settings:
            logger.error("Security violation: Settings missing from bot_data.")
            return None

        if not is_owner(update, settings):
            user_id = update.effective_user.id if update.effective_user else "unknown"
            logger.warning("Dropped unauthorized update from user_id=%s", user_id)
            # Silent drop: no reply, no callback answer to strangers (SEC-001, FR-001)
            return None

        return await handler(update, context)

    return wrapper
