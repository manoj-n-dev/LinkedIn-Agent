"""Telegram command handlers for drafting, commenting, notes, and revisions (FR-004, FR-005)."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.ai.groq_client import (
    AIError,
    AIRateLimitError,
    AITimeoutError,
    AIUnavailableError,
)
from src.config import Settings
from src.db.models import Draft
from src.db.session import create_db_engine, get_session_factory
from src.services.draft_service import DraftService
from src.telegram_bot.auth import owner_only

logger = logging.getLogger(__name__)


def _get_db(context: ContextTypes.DEFAULT_TYPE) -> Session:
    """Retrieve a database session from bot_data or initialize one."""
    factory: sessionmaker[Session] | None = context.bot_data.get("db_session_factory")
    if factory is None:
        settings: Settings = context.bot_data["settings"]
        engine = create_db_engine(settings.database_url)
        factory = get_session_factory(engine)
        context.bot_data["db_session_factory"] = factory
    return factory()


@owner_only
async def draft_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /draft <idea> — generate a new post draft."""
    if not update.effective_message:
        return

    text = update.effective_message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.effective_message.reply_text(
            "Please provide an idea for your draft.\n"
            "Example: /draft 3 lessons from my first open source project"
        )
        return

    idea = parts[1].strip()
    settings: Settings = context.bot_data["settings"]

    await update.effective_message.reply_text("✍️ Drafting your post...")

    with _get_db(context) as session:
        service = DraftService(
            db=session,
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
        try:
            draft, validation = await service.create_post_draft(idea=idea)
        except AIRateLimitError as exc:
            wait_info = f" ({exc.retry_after}s)" if exc.retry_after else ""
            await update.effective_message.reply_text(
                f"⏳ Groq rate limit reached{wait_info}. Please wait a moment."
            )
            return
        except AITimeoutError:
            await update.effective_message.reply_text(
                "⌛ Groq request timed out. Please try again."
            )
            return
        except AIUnavailableError:
            await update.effective_message.reply_text(
                "⚠️ Groq service is unavailable. Please try again later."
            )
            return
        except AIError as exc:
            logger.error("AI error during /draft: %s", exc)
            await update.effective_message.reply_text(
                "❌ Failed to generate draft due to an AI service error."
            )
            return

        warning_text = ""
        if validation.warnings:
            warning_text = "\n\n⚠️ Notes:\n" + "\n".join(f"- {w}" for w in validation.warnings)

        reply = (
            f"📝 Draft [{draft.code}] (v{draft.version}):\n\n"
            f"{draft.body}"
            f"{warning_text}\n\n"
            f"💡 To tweak: /revise {draft.code} <your instructions>"
        )

        from src.services.approval_service import ApprovalService

        try:
            approval_svc = ApprovalService(session)
            _, app_tok, rej_tok, _ = approval_svc.request_approval(draft.code)
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🖼️ Add Visual Image", callback_data=f"gen_img:{draft.code}"
                        ),
                        InlineKeyboardButton(
                            "✅ Approve Post", callback_data=app_tok.token
                        ),
                        InlineKeyboardButton(
                            "❌ Reject", callback_data=rej_tok.token
                        ),
                    ]
                ]
            )
        except Exception:
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🖼️ Add Visual Image", callback_data=f"gen_img:{draft.code}"
                        ),
                        InlineKeyboardButton(
                            "✅ Approve", callback_data=f"review_appr:{draft.code}"
                        ),
                    ]
                ]
            )
        await update.effective_message.reply_text(reply, reply_markup=keyboard)


@owner_only
async def comment_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /comment <post text> — generate 2-3 thoughtful comment options."""
    if not update.effective_message:
        return

    text = update.effective_message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.effective_message.reply_text(
            "Please paste the post text you'd like to comment on.\nExample: /comment <pasted text>"
        )
        return

    post_text = parts[1].strip()
    settings: Settings = context.bot_data["settings"]

    await update.effective_message.reply_text("💬 Drafting comment options...")

    with _get_db(context) as session:
        service = DraftService(
            db=session,
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
        try:
            draft, _ = await service.create_comment_draft(post_text=post_text)
        except AIRateLimitError:
            await update.effective_message.reply_text(
                "⏳ AI rate limit reached. Please wait a moment."
            )
            return
        except (AITimeoutError, AIUnavailableError):
            await update.effective_message.reply_text(
                "⚠️ AI service is currently unavailable. Please try again."
            )
            return
        except AIError:
            await update.effective_message.reply_text(
                "❌ Failed to generate comments due to an AI error."
            )
            return

        reply = f"💬 Comment suggestions [{draft.code}]:\n\n{draft.body}"
        await update.effective_message.reply_text(reply)


@owner_only
async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /note <context> — generate a short connection note (< 200 chars)."""
    if not update.effective_message:
        return

    text = update.effective_message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.effective_message.reply_text(
            "Please provide a context or topic for the connection request.\n"
            "Example: /note Met at PyCon India, discussed async architecture"
        )
        return

    recipient_context = parts[1].strip()
    settings: Settings = context.bot_data["settings"]

    await update.effective_message.reply_text("🤝 Drafting connection note...")

    with _get_db(context) as session:
        service = DraftService(
            db=session,
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
        try:
            draft, validation = await service.create_connection_note_draft(
                recipient_context=recipient_context
            )
        except AIRateLimitError:
            await update.effective_message.reply_text(
                "⏳ AI rate limit reached. Please wait a moment."
            )
            return
        except (AITimeoutError, AIUnavailableError):
            await update.effective_message.reply_text(
                "⚠️ AI service is currently unavailable. Please try again."
            )
            return
        except AIError:
            await update.effective_message.reply_text(
                "❌ Failed to generate note due to an AI error."
            )
            return

        warning_text = ""
        if validation.warnings:
            warning_text = "\n\n⚠️ " + "\n".join(validation.warnings)

        reply = f"🤝 Connection note [{draft.code}]:\n\n{draft.body}{warning_text}"
        await update.effective_message.reply_text(reply)


@owner_only
async def revise_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /revise <code> <instruction> — revise an existing draft (FR-005)."""
    if not update.effective_message:
        return

    text = update.effective_message.text or ""
    parts = text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].strip() or not parts[2].strip():
        await update.effective_message.reply_text(
            "Please provide the draft code and revision instructions.\n"
            "Example: /revise d-a1b2c3 make the opening hook punchier"
        )
        return

    draft_code = parts[1].strip()
    instruction = parts[2].strip()
    settings: Settings = context.bot_data["settings"]

    await update.effective_message.reply_text(f"🔄 Revising draft [{draft_code}]...")

    with _get_db(context) as session:
        service = DraftService(
            db=session,
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
        try:
            new_draft, validation = await service.revise_draft(
                draft_code=draft_code,
                instruction=instruction,
            )
        except ValueError as exc:
            await update.effective_message.reply_text(f"⚠️ {exc}")
            return
        except AIRateLimitError:
            await update.effective_message.reply_text(
                "⏳ AI rate limit reached. Please wait a moment."
            )
            return
        except (AITimeoutError, AIUnavailableError):
            await update.effective_message.reply_text(
                "⚠️ AI service is currently unavailable. Please try again."
            )
            return
        except AIError:
            await update.effective_message.reply_text(
                "❌ Failed to revise draft due to an AI error."
            )
            return

        reply = (
            f"🔄 Revised Draft [{new_draft.code}] (v{new_draft.version}, parent {draft_code}):\n\n"
            f"{new_draft.body}\n\n"
            f"Prior approvals (if any) have been voided."
        )

        from src.services.approval_service import ApprovalService

        try:
            approval_svc = ApprovalService(session)
            _, app_tok, rej_tok, _ = approval_svc.request_approval(new_draft.code)
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🖼️ Add Visual Image", callback_data=f"gen_img:{new_draft.code}"
                        ),
                        InlineKeyboardButton(
                            "✅ Approve Post", callback_data=app_tok.token
                        ),
                        InlineKeyboardButton(
                            "❌ Reject", callback_data=rej_tok.token
                        ),
                    ]
                ]
            )
        except Exception:
            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🖼️ Add Visual Image", callback_data=f"gen_img:{new_draft.code}"
                        ),
                        InlineKeyboardButton(
                            "✅ Approve", callback_data=f"review_appr:{new_draft.code}"
                        ),
                    ]
                ]
            )
        await update.effective_message.reply_text(reply, reply_markup=keyboard)


@owner_only
async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /image <draft_code> — generate a visual cover image for a draft."""
    if not update.effective_message:
        return

    text = update.effective_message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.effective_message.reply_text(
            "Please provide a draft code to generate an image for.\nExample: /image d-a1b2c3"
        )
        return

    draft_code = parts[1].strip()
    from src.telegram_bot.approval_handlers import get_or_create_approval_tokens

    with _get_db(context) as session:
        draft = session.execute(select(Draft).where(Draft.code == draft_code)).scalar_one_or_none()
        if not draft:
            await update.effective_message.reply_text(f"⚠️ Draft '{draft_code}' not found.")
            return
        body = draft.body
        try:
            app_tok_str, rej_tok_str = get_or_create_approval_tokens(session, draft_code)
        except Exception:
            app_tok_str, rej_tok_str = "", ""

    settings: Settings = context.bot_data["settings"]
    await update.effective_message.reply_text("🎨 Creating custom, watermark-free visual...")
    try:
        from src.services.image_service import (
            ImageRateLimitError,
            download_and_clean_image,
            generate_smart_image_prompt,
            get_post_image_url,
        )

        prompt = await generate_smart_image_prompt(
            body,
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
        image_url = get_post_image_url(prompt)
        clean_buf = await download_and_clean_image(image_url)

        keyboard_buttons = [
            InlineKeyboardButton("🔄 New Variation", callback_data=f"gen_img:{draft_code}")
        ]
        if app_tok_str and rej_tok_str:
            keyboard_buttons.append(
                InlineKeyboardButton("✅ Approve with Image", callback_data=app_tok_str)
            )
            keyboard_buttons.append(
                InlineKeyboardButton("❌ Reject", callback_data=rej_tok_str)
            )

        keyboard = InlineKeyboardMarkup([keyboard_buttons])
        caption = (
            f"🖼️ Cover Graphic for [{draft_code}]\n\n"
            f"💡 Scene: {prompt[:140]}...\n\n"
            "Ready to pair with your LinkedIn post! 🚀"
        )
        await update.effective_message.reply_photo(
            photo=clean_buf,
            caption=caption,
            reply_markup=keyboard,
        )
    except ImageRateLimitError as exc:
        await update.effective_message.reply_text(
            f"⏳ Free visual generator cooldown active ({exc.retry_after}s remaining).\n"
            f"Please wait a moment and try again: /image {draft_code}"
        )
    except Exception as exc:
        logger.error("Failed to generate image: %s", exc)
        await update.effective_message.reply_text(
            f"⚠️ Could not generate image right now. Please try again: /image {draft_code}"
        )


@owner_only
async def drafts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /drafts — list recent drafts."""
    if not update.effective_message:
        return

    with _get_db(context) as session:
        recent_drafts = (
            session.execute(select(Draft).order_by(Draft.created_at.desc()).limit(5))
            .scalars()
            .all()
        )

        if not recent_drafts:
            await update.effective_message.reply_text(
                "No drafts yet. Use /draft <idea> to write one."
            )
            return

        lines = ["Recent drafts:"]
        for d in recent_drafts:
            preview = (d.body[:60] + "...") if len(d.body) > 60 else d.body
            preview_clean = preview.replace("\n", " ")
            lines.append(f"• [{d.code}] (v{d.version}, {d.kind}): {preview_clean}")

        await update.effective_message.reply_text("\n".join(lines))
