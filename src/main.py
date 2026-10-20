"""Application entry point for running the Telegram bot in local polling mode."""

import logging
import sys

from src.config import ConfigError, load_settings
from src.logging_config import setup_logging
from src.telegram_bot.bot import build_bot_app

logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point for local development and polling mode."""
    setup_logging()

    try:
        settings = load_settings()
    except ConfigError as err:
        logger.error("Startup aborted due to configuration error: %s", err)
        sys.exit(1)

    logger.info("Configuration validated successfully. Starting bot in polling mode...")
    app = build_bot_app(settings)
    app.run_polling()


if __name__ == "__main__":
    main()
