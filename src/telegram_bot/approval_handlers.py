"""Telegram handlers for approvals, fallback commands, and inline button decisions.

Covers FR-006, FR-017.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.config import Settings
from src.db.models import Approval, Draft
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
async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /approve <draft_code> — request approval review with buttons or approve."""
    if not update.effective_message:
        return

    text = update.effective_message.text or ""
    parts = text.split()
    if len(parts) < 2 or not parts[1].strip():
        await update.effective_message.reply_text(
            "Please specify a draft code to approve.\nExample: /approve d-a1b2c3"
        )
        return

    draft_code = parts[1].strip()
    with _get_db(context) as session:
        service = ApprovalService(session)
        try:
            _, approve_tok, reject_tok, preview = service.request_approval(draft_code)
        except ValueError as exc:
            await update.effective_message.reply_text(f"⚠️ {exc}")
            return

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=approve_tok.token),
                    InlineKeyboardButton("❌ Reject", callback_data=reject_tok.token),
                ]
            ]
        )
        await update.effective_message.reply_text(preview, reply_markup=keyboard)


@owner_only
async def reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reject <draft_code> — reject pending approvals for a draft."""
    if not update.effective_message:
        return

    text = update.effective_message.text or ""
    parts = text.split()
    if len(parts) < 2 or not parts[1].strip():
        await update.effective_message.reply_text(
            "Please specify a draft code to reject.\nExample: /reject d-a1b2c3"
        )
        return

    draft_code = parts[1].strip()
    with _get_db(context) as session:
        draft = session.execute(select(Draft).where(Draft.code == draft_code)).scalar_one_or_none()
        if not draft:
            await update.effective_message.reply_text(f"⚠️ Draft '{draft_code}' not found.")
            return

        pending_approvals = (
            session.execute(
                select(Approval).where(
                    Approval.draft_id == draft.id, Approval.decision == "pending"
                )
            )
            .scalars()
            .all()
        )

        if not pending_approvals:
            await update.effective_message.reply_text(
                f"No pending approval requests found for [{draft_code}]."
            )
            return

        for app in pending_approvals:
            app.decision = "rejected"
        session.commit()

        await update.effective_message.reply_text(
            f"❌ Draft [{draft_code}] has been marked as rejected."
        )


@owner_only
async def decision_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle single-use button press for approve/reject (FR-006, SEC-002, SEC-013)."""
    query = update.callback_query
    if not query:
        return

    token_str = query.data or ""
    settings: Settings = context.bot_data["settings"]

    if token_str.startswith("gen_img:"):
        draft_code = token_str.split(":", 1)[1]
        await query.answer("🎨 Generating cover image...")
        with _get_db(context) as session:
            draft = (
                session.execute(select(Draft).where(Draft.code == draft_code)).scalar_one_or_none()
            )
            if not draft:
                if query.message:
                    await query.message.reply_text(f"⚠️ Draft '{draft_code}' not found.")
                return
            body = draft.body

        try:
            from src.services.image_service import get_post_image_url

            image_url = get_post_image_url(body)
            if query.message:
                await query.message.reply_photo(
                    photo=image_url,
                    caption=(
                        f"🖼️ Cover Graphic for [{draft_code}]\n\n"
                        "Ready to pair with your LinkedIn post! 🚀"
                    ),
                )
        except Exception:
            if query.message:
                err_msg = f"⚠️ Image generation failed. Try /image {draft_code}"
                await query.message.reply_text(err_msg)
        return

    if token_str.startswith("review_appr:"):
        draft_code = token_str.split(":", 1)[1]
        await query.answer()
        with _get_db(context) as session:
            service = ApprovalService(session)
            try:
                _, approve_tok, reject_tok, preview = service.request_approval(draft_code)
            except ValueError as exc:
                if query.message:
                    await query.message.reply_text(f"⚠️ {exc}")
                return

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=approve_tok.token),
                        InlineKeyboardButton("❌ Reject", callback_data=reject_tok.token),
                    ]
                ]
            )
            if query.message:
                await query.message.reply_text(preview, reply_markup=keyboard)
        return

    with _get_db(context) as session:
        service = ApprovalService(session)
        success, message, _ = service.handle_callback_decision(
            token_str=token_str,
            owner_telegram_id=settings.owner_telegram_id,
        )

    await query.answer()

    # Edit the message to remove buttons and show decision status
    current_text = query.message.text if query.message else ""
    updated_text = f"{current_text}\n\n📌 Decision: {message}"
    try:
        await query.edit_message_text(text=updated_text, reply_markup=None)
    except Exception as exc:
        logger.debug("Failed editing callback message: %s", exc)
