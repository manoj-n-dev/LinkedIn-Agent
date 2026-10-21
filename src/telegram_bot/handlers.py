"""Telegram command handlers (FR-001, FR-002, FR-031, SEC-001, SEC-002)."""

from telegram import Update
from telegram.ext import ContextTypes

from src.config import Settings
from src.telegram_bot.auth import owner_only


def get_ist_greeting(display_name: str) -> str:
    """Return friendly, natural time-of-day greeting in IST."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    try:
        ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        hour = ist_now.hour
    except Exception:
        hour = 12

    name = f" {display_name}" if display_name else ""
    if 5 <= hour < 12:
        return f"Good morning{name}! ☀️"
    elif 12 <= hour < 17:
        return f"Good afternoon{name}! ⛅"
    else:
        return f"Good evening{name}! 🌙"


def build_start_message(settings: Settings) -> str:
    """Format welcome message according to docs/04 section 4.1 with IST greeting."""
    greeting = f"Hi {settings.owner_display_name}." if settings.owner_display_name else "Hi."
    ist_greet = get_ist_greeting(settings.owner_display_name)
    return (
        f"{greeting} I am your private LinkedIn helper.\n"
        f"🌟 {ist_greet}\n"
        "I write drafts and briefings. I never post, like, comment or message\n"
        "by myself. You always decide.\n"
        "Type /help to see what I can do."
    )


def build_help_message() -> str:
    """Format command list according to docs/04 section 2."""
    return (
        "Commands:\n"
        "/start - Welcome and quick tour\n"
        "/help - Command list\n"
        "/status - State of everything\n"
        "/report - Latest daily briefing (or regenerate)\n"
        "/trends - Topic scan from news, RSS, Hacker News\n"
        "/draft <idea> - New post draft\n"
        "/image <code> - Generate cover graphic for draft\n"
        "/comment - Comment drafts for text you paste\n"
        "/connections - Connection-note drafts and networking ideas\n"
        "/schedule - Schedule an approved draft\n"
        "/approve - Fallback to approve by draft code\n"
        "/reject - Fallback to reject by draft code\n"
        "/history - Recent items\n"
        "/settings - Change settings\n"
        "/pause - Stop all external actions\n"
        "/resume - Start again\n"
        "/connect - Link LinkedIn (sign-in)\n"
        "/cancel - Cancel the current step"
    )


@owner_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command (owner only)."""
    if not update.effective_message:
        return
    settings: Settings = context.bot_data.get("settings")  # type: ignore[assignment]
    text = build_start_message(settings)
    await update.effective_message.reply_text(text)


@owner_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command (owner only)."""
    if not update.effective_message:
        return
    text = build_help_message()
    await update.effective_message.reply_text(text)
