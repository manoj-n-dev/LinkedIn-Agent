"""Telegram command handlers for research, briefings, and trends (FR-008, FR-010)."""

import logging

from sqlalchemy.orm import Session, sessionmaker
from telegram import Update
from telegram.ext import ContextTypes

from src.config import Settings
from src.db.session import create_db_engine, get_session_factory
from src.services.briefing_service import BriefingService
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
async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /report — fetch legal sources and generate daily briefing."""
    if not update.effective_message:
        return

    await update.effective_message.reply_text(
        "🔍 Gathering research and preparing your daily briefing..."
    )

    settings: Settings = context.bot_data["settings"]

    with _get_db(context) as session:
        service = BriefingService(
            db=session,
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
        _, formatted_msg = await service.generate_daily_briefing()

        # Split message if it exceeds Telegram's 4096 character limit
        if len(formatted_msg) > 4000:
            chunks = [formatted_msg[i : i + 4000] for i in range(0, len(formatted_msg), 4000)]
            for chunk in chunks:
                await update.effective_message.reply_text(chunk)
        else:
            await update.effective_message.reply_text(formatted_msg)


@owner_only
async def trends_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /trends — quick scan of fresh items from Hacker News and RSS."""
    if not update.effective_message:
        return

    await update.effective_message.reply_text(
        "📡 Scanning Hacker News and RSS feeds for new stories..."
    )

    settings: Settings = context.bot_data["settings"]

    with _get_db(context) as session:
        service = BriefingService(
            db=session,
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
        items = await service.collect_fresh_items(max_items=5)

        if not items:
            await update.effective_message.reply_text(
                "No unread items found in your configured feeds right now."
            )
            return

        lines = ["📡 Fresh Stories Scan (HN & RSS):\n"]
        for idx, itm in enumerate(items, start=1):
            lines.append(f"{idx}. {itm.title} ({itm.source_name})\n   🔗 {itm.url}\n")
        lines.append("To write about any of these: /draft <your take>")

        await update.effective_message.reply_text("\n".join(lines))
