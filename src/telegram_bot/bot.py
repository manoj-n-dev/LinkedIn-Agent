"""Telegram Bot Application factory."""

from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application, ApplicationBuilder, CommandHandler

from src.config import Settings
from src.telegram_bot.draft_handlers import (
    comment_command,
    draft_command,
    drafts_command,
    note_command,
    revise_command,
)
from src.telegram_bot.handlers import help_command, start_command
from src.telegram_bot.research_handlers import report_command, trends_command


def build_bot_app(
    settings: Settings,
    session_factory: sessionmaker[Session] | None = None,
) -> Application:
    """Build and configure the Telegram Application.

    Args:
        settings: Application settings.
        session_factory: Optional database session factory.

    Returns:
        Application: Configured python-telegram-bot application.
    """
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    app.bot_data["settings"] = settings
    if session_factory is not None:
        app.bot_data["db_session_factory"] = session_factory

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("draft", draft_command))
    app.add_handler(CommandHandler("comment", comment_command))
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("revise", revise_command))
    app.add_handler(CommandHandler("drafts", drafts_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("trends", trends_command))

    return app
