"""Telegram Bot Application factory."""

from telegram.ext import Application, ApplicationBuilder, CommandHandler

from src.config import Settings
from src.telegram_bot.handlers import help_command, start_command


def build_bot_app(settings: Settings) -> Application:
    """Build and configure the Telegram Application.

    Args:
        settings: Application settings.

    Returns:
        Application: Configured python-telegram-bot application.
    """
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    app.bot_data["settings"] = settings

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    return app
