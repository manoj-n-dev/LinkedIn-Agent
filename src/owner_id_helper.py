"""Owner ID setup helper (FR-029).

A local command that displays the numeric Telegram user ID of whoever sends a
message to the deployer's bot, so it can be copied into OWNER_TELEGRAM_ID.
Stores nothing and never makes that sender the owner automatically.
"""

import asyncio
import os
import sys

from telegram import Bot, Update

from src.config import PLACEHOLDER_MARKER


def extract_sender_info(update: Update) -> dict[str, str | int] | None:
    """Extract sender details from a Telegram update without storing anything."""
    user = update.effective_user
    if not user:
        return None
    return {
        "user_id": user.id,
        "first_name": user.first_name or "",
        "username": user.username or "None",
    }


def format_owner_id_output(sender_info: dict[str, str | int]) -> str:
    """Format the terminal display instructions."""
    return (
        "\n========================================\n"
        "TELEGRAM MESSAGE RECEIVED\n"
        f"Sender: {sender_info['first_name']} (@{sender_info['username']})\n"
        f"Numeric User ID: {sender_info['user_id']}\n\n"
        "Copy this number into your .env file:\n"
        f"OWNER_TELEGRAM_ID={sender_info['user_id']}\n"
        "========================================\n"
    )


async def run_id_helper(bot_token: str) -> None:
    """Poll for the first update and print the user ID."""
    bot = Bot(token=bot_token)
    print("Owner ID Helper is waiting for a message...")
    print("Send any message (e.g. 'hello') to your Telegram bot now.")

    offset = None
    while True:
        updates = await bot.get_updates(offset=offset, timeout=10)
        for update in updates:
            sender_info = extract_sender_info(update)
            if sender_info:
                print(format_owner_id_output(sender_info))
                return
            if update.update_id:
                offset = update.update_id + 1
        await asyncio.sleep(1)


def main() -> None:
    """Entry point for running the helper from terminal."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token or bot_token == PLACEHOLDER_MARKER:  # noqa: S105
        bot_token = input("Enter your TELEGRAM_BOT_TOKEN from @BotFather: ").strip()

    if not bot_token or bot_token == PLACEHOLDER_MARKER:  # noqa: S105
        print("Error: Valid TELEGRAM_BOT_TOKEN is required to run this helper.")
        sys.exit(1)

    try:
        asyncio.run(run_id_helper(bot_token))
    except KeyboardInterrupt:
        print("\nHelper cancelled.")


if __name__ == "__main__":
    main()
