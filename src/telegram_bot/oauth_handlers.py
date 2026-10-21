"""Telegram command handlers for LinkedIn OAuth connection and status (FR-018, FR-019, FR-020)."""

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config import Settings
from src.services.linkedin_oauth_service import LinkedInOAuthService
from src.telegram_bot.auth import owner_only

logger = logging.getLogger(__name__)


@owner_only
async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /connect to initiate LinkedIn OAuth 2.0 flow (FR-018, FR-020)."""
    settings: Settings = context.bot_data["settings"]
    session_factory = context.bot_data["db_session_factory"]

    # FR-020: Clean fallback to drafts-only mode when credentials are missing
    if (
        not settings.linkedin_client_id
        or not settings.linkedin_client_secret
        or not settings.token_encryption_key
    ):
        msg = (
            "⚠️ <b>LinkedIn Connection Not Configured</b>\n\n"
            "The bot is running in <b>drafts-only mode</b> (FR-020).\n"
            "Posts and briefings can be generated, reviewed, and approved inside Telegram, "
            "then published manually by copying the text.\n\n"
            "<b>To enable official LinkedIn publishing:</b>\n"
            "1. Set <code>LINKEDIN_CLIENT_ID</code> and <code>LINKEDIN_CLIENT_SECRET</code>\n"
            "2. Set <code>TOKEN_ENCRYPTION_KEY</code> (generate with Fernet.generate_key())\n"
            "3. Set <code>LINKEDIN_REDIRECT_URL</code>"
        )
        if update.effective_message:
            await update.effective_message.reply_text(msg, parse_mode=ParseMode.HTML)
        return

    redirect_uri = settings.linkedin_redirect_url or "https://localhost/callback"

    with session_factory() as session:
        service = LinkedInOAuthService(session, settings.token_encryption_key)
        try:
            url, _ = service.generate_authorization_url(
                settings.linkedin_client_id, redirect_uri
            )
        except Exception as e:
            logger.error("Failed to generate LinkedIn authorization URL: %s", e)
            if update.effective_message:
                await update.effective_message.reply_text(
                    f"❌ Failed to generate authorization URL: {e}"
                )
            return

    msg = (
        "🔗 <b>Connect Your LinkedIn Account</b>\n\n"
        f"1. <a href=\"{url}\"><b>Click here to authorize LinkedIn access</b></a>\n\n"
        "2. After signing in, LinkedIn will redirect to your configured redirect URL.\n"
        "3. Copy the <code>code</code> and <code>state</code> query parameters from your URL.\n"
        "4. Send them to this bot:\n"
        "<code>/connect_token &lt;code&gt; &lt;state&gt;</code>\n\n"
        "⏱️ <i>This link and security state expire in 15 minutes.</i>"
    )
    if update.effective_message:
        await update.effective_message.reply_text(
            msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )


@owner_only
async def connect_token_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /connect_token <code> <state> to complete the OAuth exchange (FR-018, SEC-004)."""
    settings: Settings = context.bot_data["settings"]
    session_factory = context.bot_data["db_session_factory"]

    args = context.args or []
    if len(args) < 2:
        if update.effective_message:
            await update.effective_message.reply_text(
                "Usage: <code>/connect_token &lt;code&gt; &lt;state&gt;</code>",
                parse_mode=ParseMode.HTML,
            )
        return

    code = args[0].strip()
    state = args[1].strip()
    redirect_uri = settings.linkedin_redirect_url or "https://localhost/callback"

    with session_factory() as session:
        service = LinkedInOAuthService(session, settings.token_encryption_key)
        try:
            res = await service.exchange_code_for_token(
                code=code,
                state_str=state,
                client_id=settings.linkedin_client_id,
                client_secret=settings.linkedin_client_secret,
                redirect_uri=redirect_uri,
            )
        except Exception as e:
            logger.warning("LinkedIn token exchange rejected: %s", e)
            if update.effective_message:
                await update.effective_message.reply_text(
                    f"❌ <b>LinkedIn Connection Failed:</b> {e}",
                    parse_mode=ParseMode.HTML,
                )
            return

    msg = (
        "✅ <b>LinkedIn Connected Successfully!</b>\n\n"
        f"• <b>Member URN:</b> <code>{res['member_urn']}</code>\n"
        f"• <b>Token Validity:</b> {res['days_valid']} days\n"
        f"• <b>Expires At:</b> <code>{res['expires_at']}</code>\n\n"
        "Official post publishing can now be performed when approved."
    )
    if update.effective_message:
        await update.effective_message.reply_text(msg, parse_mode=ParseMode.HTML)


@owner_only
async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /disconnect to disconnect LinkedIn account."""
    settings: Settings = context.bot_data["settings"]
    session_factory = context.bot_data["db_session_factory"]

    with session_factory() as session:
        service = LinkedInOAuthService(session, settings.token_encryption_key)
        service.disconnect()

    if update.effective_message:
        await update.effective_message.reply_text(
            "🔌 <b>LinkedIn Account Disconnected</b>\n\n"
            "The bot has returned to drafts-only mode. Use /connect to re-link anytime.",
            parse_mode=ParseMode.HTML,
        )
