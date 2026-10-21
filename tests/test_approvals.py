"""Tests for approval workflows, single-use guarantees, emergency controls,
and the SEC-013 list (FR-006, FR-017, FR-027, SEC-002, SEC-013).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from telegram import CallbackQuery, Chat, Message, Update, User

from src.config import Settings
from src.db.models import AuditLog, Draft
from src.db.session import Base, get_session_factory
from src.services.approval_service import ApprovalService
from src.telegram_bot.approval_handlers import approve_command, decision_callback_handler
from src.telegram_bot.control_handlers import pause_command, resume_command, status_command


@pytest.fixture
def db_session():
    """In-memory SQLite database session for tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def fake_settings():
    return Settings(
        telegram_bot_token="123456789:ABCDefghIJKLmnOPQRstuvWXYZ",
        owner_telegram_id=987654321,
        database_url="sqlite:///:memory:",
        groq_api_key="gsk_" + "fakegroqapikeyfortesting123456",
        groq_model="llama-3.3-70b-versatile",
        owner_display_name="Manoj",
    )


@pytest.fixture
def sample_draft(db_session: Session):
    draft = Draft(
        code="d-sec013",
        kind="post",
        version=1,
        body="This is an exact-text post to be published on LinkedIn.",
        content_hash="dummyhash",
        status="draft",
    )
    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)
    return draft


# --- Approval Request & Callback Tests ---


def test_approval_request_flow(db_session: Session, sample_draft):
    """FR-006: Request approval creates record, hashes exact text, and issues single-use tokens."""
    service = ApprovalService(db_session)
    approval, app_tok, rej_tok, preview = service.request_approval(
        sample_draft.code, expires_minutes=30
    )

    assert approval.decision == "pending"
    assert approval.used_at is None
    assert app_tok.token.startswith("app_")
    assert rej_tok.token.startswith("rej_")
    assert "Approval Request for [d-sec013]" in preview
    assert "Length:" in preview

    # Verify audit log recorded
    audit = db_session.execute(
        select(AuditLog).where(AuditLog.event == "approval_requested")
    ).scalar_one()
    assert audit.entity_id == approval.id


def test_callback_decision_approve_and_reject(db_session: Session, sample_draft, fake_settings):
    """FR-006: Owner clicking approve sets decision to approved and marks token used."""
    service = ApprovalService(db_session)
    approval, app_tok, rej_tok, _ = service.request_approval(sample_draft.code)

    success, msg, app_result = service.handle_callback_decision(
        token_str=app_tok.token,
        owner_telegram_id=fake_settings.owner_telegram_id,
    )
    assert success
    assert "approved" in msg
    assert app_result.decision == "approved"
    assert app_result.decided_by_telegram_id == fake_settings.owner_telegram_id

    # Verify token is now marked used
    db_session.refresh(app_tok)
    assert app_tok.used_at is not None


# --- SEC-013 Attack List Tests ---


def test_sec_013_1_edited_text_rejected(db_session: Session, sample_draft, fake_settings):
    """SEC-013.1: Text modified after approval was granted must be rejected."""
    service = ApprovalService(db_session)
    approval, app_tok, _, _ = service.request_approval(sample_draft.code)
    service.handle_callback_decision(app_tok.token, fake_settings.owner_telegram_id)

    # Candidate text is altered by even one character
    altered_text = sample_draft.body + " sneaky extra text"
    valid, reason = service.validate_for_publish(approval.id, altered_text)
    assert not valid
    assert "Text was modified" in reason

    # Original unaltered text passes
    valid_orig, _ = service.validate_for_publish(approval.id, sample_draft.body)
    assert valid_orig


def test_sec_013_2_expired_approval_rejected(db_session: Session, sample_draft, fake_settings):
    """SEC-013.2: Expired approval cannot be published."""
    service = ApprovalService(db_session)
    # Create already-expired approval (-10 minutes)
    approval, app_tok, _, _ = service.request_approval(sample_draft.code, expires_minutes=-10)

    # Callback fails due to expiry
    success, msg, _ = service.handle_callback_decision(
        app_tok.token, fake_settings.owner_telegram_id
    )
    assert not success
    assert "expired" in msg.lower()

    # Direct publish validation also rejects expired
    valid, reason = service.validate_for_publish(approval.id, sample_draft.body)
    assert not valid
    assert "expired" in reason.lower()


def test_sec_013_3_reused_approval_rejected(db_session: Session, sample_draft, fake_settings):
    """SEC-013.3, FR-017: Single-use approval invariant prevents double publishing."""
    service = ApprovalService(db_session)
    approval, app_tok, _, _ = service.request_approval(sample_draft.code)
    service.handle_callback_decision(app_tok.token, fake_settings.owner_telegram_id)

    # First publish succeeds and consumes approval
    first_valid, _ = service.validate_for_publish(approval.id, sample_draft.body)
    assert first_valid
    db_session.refresh(approval)
    assert approval.used_at is not None

    # Replay/second publish attempt is rejected
    second_valid, reason = service.validate_for_publish(approval.id, sample_draft.body)
    assert not second_valid
    assert "already been used" in reason


def test_sec_013_4_rejected_approval_cannot_publish(
    db_session: Session, sample_draft, fake_settings
):
    """SEC-013.4: Rejection prevents any publish attempt."""
    service = ApprovalService(db_session)
    approval, _, rej_tok, _ = service.request_approval(sample_draft.code)
    service.handle_callback_decision(rej_tok.token, fake_settings.owner_telegram_id)

    valid, reason = service.validate_for_publish(approval.id, sample_draft.body)
    assert not valid
    assert "rejected" in reason


@pytest.mark.asyncio
async def test_sec_013_5_stranger_button_tap_ignored(fake_settings):
    """SEC-013.5, SEC-002: Button tap from non-owner is silently ignored."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = get_session_factory(engine)

    with session_factory() as session:
        draft = Draft(
            code="d-stranger",
            kind="post",
            version=1,
            body="Text",
            content_hash="h1",
        )
        session.add(draft)
        session.commit()
        service = ApprovalService(session)
        _, app_tok, _, _ = service.request_approval(draft.code)
        token_str = app_tok.token

    # Stranger taps button
    stranger_user = User(id=111111, first_name="Stranger", is_bot=False)
    query = MagicMock(spec=CallbackQuery)
    query.from_user = stranger_user
    query.data = token_str
    query.answer = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_user = stranger_user
    update.callback_query = query

    context = MagicMock()
    context.bot_data = {"settings": fake_settings, "db_session_factory": session_factory}

    await decision_callback_handler(update, context)
    query.answer.assert_not_awaited()


def test_sec_013_6_replayed_button_rejected(db_session: Session, sample_draft, fake_settings):
    """SEC-013.6: Replayed or re-clicked button token is rejected."""
    service = ApprovalService(db_session)
    approval, app_tok, _, _ = service.request_approval(sample_draft.code)

    # First tap succeeds
    s1, _, _ = service.handle_callback_decision(app_tok.token, fake_settings.owner_telegram_id)
    assert s1

    # Replay of token fails
    s2, msg, _ = service.handle_callback_decision(app_tok.token, fake_settings.owner_telegram_id)
    assert not s2
    assert "already been used" in msg


# --- Emergency Controls Tests ---


def test_emergency_controls_pause_resume_and_kill_switch(
    db_session: Session, sample_draft, fake_settings
):
    """FR-027: Pause and Kill Switch block publish validation."""
    service = ApprovalService(db_session)
    approval, app_tok, _, _ = service.request_approval(sample_draft.code)
    service.handle_callback_decision(app_tok.token, fake_settings.owner_telegram_id)

    # 1. Kill switch blocks publishing
    k_valid, k_reason = service.validate_for_publish(
        approval.id, sample_draft.body, kill_switch=True
    )
    assert not k_valid
    assert "Kill switch is active" in k_reason

    # 2. Pause blocks publishing
    service.pause_bot(fake_settings.owner_telegram_id)
    p_valid, p_reason = service.validate_for_publish(approval.id, sample_draft.body)
    assert not p_valid
    assert "paused" in p_reason

    # 3. Resume restores publishing
    service.resume_bot(fake_settings.owner_telegram_id)
    r_valid, _ = service.validate_for_publish(approval.id, sample_draft.body)
    assert r_valid


# --- Telegram Command Handlers Tests ---


def _build_telegram_mocks(user_id: int, text: str, settings, session_factory):
    user = User(id=user_id, first_name="Owner", is_bot=False)
    chat = Chat(id=user_id, type=Chat.PRIVATE)
    message = MagicMock(spec=Message)
    message.from_user = user
    message.chat = chat
    message.text = text
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_message = message
    update.effective_user = user
    update.effective_chat = chat

    context = MagicMock()
    context.bot_data = {
        "settings": settings,
        "db_session_factory": session_factory,
    }
    return update, message, context


@pytest.mark.asyncio
async def test_telegram_pause_resume_status_commands(fake_settings):
    """FR-027: /pause, /resume, /status work for owner."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = get_session_factory(engine)

    # 1. /pause
    up_pause, msg_pause, ctx_pause = _build_telegram_mocks(
        user_id=fake_settings.owner_telegram_id,
        text="/pause",
        settings=fake_settings,
        session_factory=session_factory,
    )
    await pause_command(up_pause, ctx_pause)
    assert "paused" in msg_pause.reply_text.call_args[0][0].lower()

    # 2. /status shows PAUSED
    up_stat, msg_stat, ctx_stat = _build_telegram_mocks(
        user_id=fake_settings.owner_telegram_id,
        text="/status",
        settings=fake_settings,
        session_factory=session_factory,
    )
    await status_command(up_stat, ctx_stat)
    assert "PAUSED" in msg_stat.reply_text.call_args[0][0]

    # 3. /resume
    up_res, msg_res, ctx_res = _build_telegram_mocks(
        user_id=fake_settings.owner_telegram_id,
        text="/resume",
        settings=fake_settings,
        session_factory=session_factory,
    )
    await resume_command(up_res, ctx_res)
    assert "resumed" in msg_res.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_telegram_approve_command_renders_buttons(fake_settings):
    """FR-006: /approve <code> renders preview and inline keyboard."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = get_session_factory(engine)

    with session_factory() as session:
        draft = Draft(
            code="d-render",
            kind="post",
            version=1,
            body="Post text to preview",
            content_hash="h2",
        )
        session.add(draft)
        session.commit()

    up_app, msg_app, ctx_app = _build_telegram_mocks(
        user_id=fake_settings.owner_telegram_id,
        text="/approve d-render",
        settings=fake_settings,
        session_factory=session_factory,
    )
    await approve_command(up_app, ctx_app)
    msg_app.reply_text.assert_awaited_once()
    args, kwargs = msg_app.reply_text.call_args
    assert "Approval Request" in args[0]
    assert kwargs.get("reply_markup") is not None
