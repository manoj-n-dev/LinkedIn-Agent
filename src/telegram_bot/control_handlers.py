"""Emergency controls and status command handlers (FR-027)."""

import logging

from sqlalchemy.orm import Session, sessionmaker
from telegram import Update
from telegram.ext import ContextTypes

from src.config import Settings
from src.db.session import create_db_engine, get_session_factory
from src.services.approval_service import ApprovalService
from src.telegram_bot.auth import owner_only

logger = logging.getLogger(__name__)


def _get_db(context: ContextTypes.DEFAULT_TYPE) -> Session:
    """Retrieve or initialize database session from bot_data."""
    factory: sessionmaker[Session] | None = context.bot_data.get("db_session_factory")
    if factory is None:
        settings: Settings = context.bot_data["settings"]
        engine = create_db_engine(settings.database_url)
        factory = get_session_factory(engine)
        context.bot_data["db_session_factory"] = factory
    return factory()


@owner_only
async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /pause — emergency stop for all external actions (FR-027)."""
    if not update.effective_message:
        return

    settings: Settings = context.bot_data["settings"]
    with _get_db(context) as session:
        service = ApprovalService(session)
        service.pause_bot(settings.owner_telegram_id)

    await update.effective_message.reply_text(
        "⏸️ Bot has been paused.\n"
        "All briefings, schedulers, and publish actions are stopped.\n"
        "Type /resume when you're ready to restart."
    )


@owner_only
async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /resume — restart external operations (FR-027)."""
    if not update.effective_message:
        return

    settings: Settings = context.bot_data["settings"]
    with _get_db(context) as session:
        service = ApprovalService(session)
        service.resume_bot(settings.owner_telegram_id)

    await update.effective_message.reply_text(
        "▶️ Bot resumed.\nNormal operations and scheduled briefings are active again."
    )


@owner_only
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status — state of everything."""
    if not update.effective_message:
        return

    settings: Settings = context.bot_data["settings"]
    with _get_db(context) as session:
        service = ApprovalService(session)
        msg = service.get_status_overview(
            owner_telegram_id=settings.owner_telegram_id,
        )

    from src.telegram_bot.handlers import get_ist_greeting

    greeting = get_ist_greeting(settings.owner_display_name)
    full_msg = f"{greeting}\n\n{msg}"
    await update.effective_message.reply_text(full_msg)
