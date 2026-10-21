"""Telegram command handlers for verified post publishing (FR-007, SEC-013, SEC-014)."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config import Settings
from src.db.models import Approval, Draft
from src.db.session import create_db_engine, get_session_factory
from src.services.action_gate import ExternalActionGate
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
async def publish_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /publish <draft_code> — publish an approved draft to LinkedIn (FR-007)."""
    if not update.effective_message:
        return

    settings: Settings = context.bot_data["settings"]
    args = context.args or []
    if not args:
        await update.effective_message.reply_text(
            "Usage: <code>/publish &lt;draft_code&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    draft_code = args[0].strip()

    with _get_db(context) as session:
        # Find draft
        draft = session.execute(
            select(Draft).where(Draft.code == draft_code)
        ).scalar_one_or_none()
        if not draft:
            await update.effective_message.reply_text(
                f"❌ Draft <code>{draft_code}</code> not found.",
                parse_mode=ParseMode.HTML,
            )
            return

        # Find valid approval
        approval = session.execute(
            select(Approval)
            .where(
                Approval.draft_id == draft.id,
                Approval.decision == "approved",
                Approval.used_at.is_(None),
            )
            .order_by(Approval.requested_at.desc())
        ).scalars().first()

        if not approval:
            await update.effective_message.reply_text(
                f"⚠️ Draft <code>{draft_code}</code> has no active, approved approval.\n"
                f"Use <code>/approve {draft_code}</code> first.",
                parse_mode=ParseMode.HTML,
            )
            return

        # Execute through the single External Action Gate
        gate = ExternalActionGate(session, settings)
        caller_id = update.effective_user.id if update.effective_user else 0

        res = await gate.execute_action(
            action_name="publish_post",
            approval_id=approval.id,
            caller_telegram_id=caller_id,
        )

    if res.outcome == "success":
        msg = (
            "🚀 <b>Post Successfully Published to LinkedIn!</b>\n\n"
            f"• <b>Draft:</b> <code>{draft_code}</code>\n"
            f"• <b>Post ID:</b> <code>{res.post_id}</code>\n\n"
            "View the live post on your LinkedIn profile."
        )
    elif res.outcome == "unknown":
        msg = (
            "⚠️ <b>Publishing Outcome UNKNOWN (Network Timeout)</b>\n\n"
            f"{res.reason}\n\n"
            "<b>Action Required:</b> Check your LinkedIn profile manually. "
            "Never attempt an automated re-try."
        )
    elif res.outcome == "failed":
        msg = (
            f"❌ <b>Publishing Failed:</b> {res.reason}\n\n"
            "No automatic retry was attempted. Please review the error and try again later."
        )
    else:
        # Refused by gate checks
        msg = f"⛔ <b>Publishing Refused:</b> {res.reason}"

    await update.effective_message.reply_text(msg, parse_mode=ParseMode.HTML)
