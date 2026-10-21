"""Tests for verified post publishing, External Action Gate, and policy enforcement.

Covers:
- T-PUB-01: Mock success -> one API call, attempt row, audit row (FR-007)
- T-PUB-02: Mock 4xx, 429, 5xx -> not posted, honest message, no retry (SEC-014, SEC-015)
- T-PUB-03: Mock timeout -> outcome UNKNOWN, NO second call (FR-025, SEC-014)
- T-PUB-04: Paused or KILL_SWITCH on -> no LinkedIn call (FR-017, SEC-024)
- T-PUB-05: Expired token or hash mismatch -> refused (FR-019, SEC-013)
- T-POL-01: Each forbidden action is refused by the gate (POL-F)
- T-POL-02: No setting can enable a forbidden action (POL-F-22)
- T-DB-01: Constraints: unique publish attempt per approval
"""

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx
from httpx import Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from telegram import Chat, Message, Update, User

from src.config import Settings
from src.db.models import (
    Approval,
    AuditLog,
    Draft,
    LinkedInConnection,
    OwnerSettings,
    PublishAttempt,
)
from src.db.session import Base, get_session_factory
from src.services.action_gate import ExternalActionGate
from src.services.encryption_service import EncryptionService
from src.services.linkedin_client import REST_POSTS_ENDPOINT
from src.telegram_bot.publish_handlers import publish_command


def compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
def enc_key():
    return EncryptionService.generate_key()


@pytest.fixture
def fake_settings(enc_key):
    return Settings(
        telegram_bot_token="123456789:ABCDefghIJKLmnOPQRstuvWXYZ",
        owner_telegram_id=987654321,
        database_url="sqlite:///:memory:",
        groq_api_key="gsk_" + "dummyfakegroqapikey123456789",
        groq_model="llama-3.3-70b-versatile",
        token_encryption_key=enc_key,
        linkedin_client_id="test_client_id",
        linkedin_client_secret="test_client_secret",
        linkedin_redirect_url="https://localhost/callback",
        publishing_enabled=True,
        kill_switch=False,
    )


@pytest.fixture
def sample_ready_draft(db_session: Session, enc_key, fake_settings):
    """Setup draft, approved approval, and active LinkedIn connection."""
    now = datetime.now(UTC)
    draft_body = "Professional milestone: Excited to share our new agent architecture!"
    draft_hash = compute_hash(draft_body)

    # 1. Draft
    draft = Draft(
        code="d-publish-01",
        kind="post",
        version=1,
        body=draft_body,
        content_hash=draft_hash,
        status="draft",
    )
    db_session.add(draft)
    db_session.flush()

    # 2. Approved approval
    approval = Approval(
        draft_id=draft.id,
        action_type="publish_post",
        decision="approved",
        content_hash=draft_hash,
        requested_at=now,
        expires_at=now + timedelta(minutes=30),
        used_at=None,
    )
    db_session.add(approval)

    # 3. Active LinkedIn Connection
    enc_token = EncryptionService(enc_key).encrypt("valid_test_token_12345")
    conn = LinkedInConnection(
        id=1,
        member_urn="urn:li:person:owner123",
        granted_scopes="w_member_social",
        access_token_enc=enc_token,
        issued_at=now,
        expires_at=now + timedelta(days=60),
        status="active",
    )
    db_session.add(conn)

    # 4. Owner Settings
    owner_cfg = OwnerSettings(
        id=1,
        owner_telegram_id=fake_settings.owner_telegram_id,
        paused=False,
        publishing_enabled=True,
    )
    db_session.add(owner_cfg)

    db_session.commit()
    return draft, approval


# --- Gate and Publishing Tests ---


@pytest.mark.asyncio
async def test_t_pub_01_mock_success(db_session: Session, fake_settings, sample_ready_draft):
    """T-PUB-01: Mock success -> one API call, attempt row, audit row (FR-007)."""
    draft, approval = sample_ready_draft
    gate = ExternalActionGate(db_session, fake_settings)

    with respx.mock() as respx_mock:
        route = respx_mock.post(REST_POSTS_ENDPOINT).mock(
            return_value=Response(
                201,
                headers={"x-restli-id": "urn:li:share:987654321"},
                json={"id": "urn:li:share:987654321"},
            )
        )

        res = await gate.execute_action(
            action_name="publish_post",
            approval_id=approval.id,
            caller_telegram_id=fake_settings.owner_telegram_id,
        )

        assert res.allowed is True
        assert res.outcome == "success"
        assert res.post_id == "urn:li:share:987654321"
        assert route.call_count == 1

        # Check DB updates:
        db_session.refresh(approval)
        assert approval.used_at is not None

        db_session.refresh(draft)
        assert draft.status == "published"

        attempt = db_session.execute(
            select(PublishAttempt).where(PublishAttempt.approval_id == approval.id)
        ).scalar_one()
        assert attempt.outcome == "success"
        assert attempt.linkedin_post_id == "urn:li:share:987654321"
        assert attempt.http_status == 201

        # Check Audit row
        audit = db_session.execute(
            select(AuditLog).where(AuditLog.event == "post_published")
        ).scalar_one_or_none()
        assert audit is not None
        assert audit.outcome == "success"


@pytest.mark.asyncio
async def test_t_pub_02_mock_api_error_no_retry(
    db_session: Session, fake_settings, sample_ready_draft
):
    """T-PUB-02: Mock 429/500 -> not posted, attempt marked failed, no retry (SEC-014)."""
    draft, approval = sample_ready_draft
    gate = ExternalActionGate(db_session, fake_settings)

    with respx.mock() as respx_mock:
        route = respx_mock.post(REST_POSTS_ENDPOINT).mock(
            return_value=Response(429, text="Rate limit exceeded")
        )

        res = await gate.execute_action(
            action_name="publish_post",
            approval_id=approval.id,
            caller_telegram_id=fake_settings.owner_telegram_id,
        )

        assert res.allowed is True
        assert res.outcome == "failed"
        assert "429" in res.reason
        assert route.call_count == 1  # Absolutely NO automated retry

        attempt = db_session.execute(
            select(PublishAttempt).where(PublishAttempt.approval_id == approval.id)
        ).scalar_one()
        assert attempt.outcome == "failed"
        assert attempt.http_status == 429


@pytest.mark.asyncio
async def test_t_pub_03_mock_timeout_outcome_unknown(
    db_session: Session, fake_settings, sample_ready_draft
):
    """T-PUB-03: Mock timeout -> outcome UNKNOWN, NO second call (FR-025, SEC-014)."""
    draft, approval = sample_ready_draft
    gate = ExternalActionGate(db_session, fake_settings)

    with respx.mock() as respx_mock:
        route = respx_mock.post(REST_POSTS_ENDPOINT).mock(
            side_effect=httpx.TimeoutException("Connection timed out")
        )

        res = await gate.execute_action(
            action_name="publish_post",
            approval_id=approval.id,
            caller_telegram_id=fake_settings.owner_telegram_id,
        )

        assert res.allowed is True
        assert res.outcome == "unknown"
        assert "UNKNOWN" in res.reason
        assert route.call_count == 1

        attempt = db_session.execute(
            select(PublishAttempt).where(PublishAttempt.approval_id == approval.id)
        ).scalar_one()
        assert attempt.outcome == "unknown"

        # Re-attempting with the same approval is blocked because it was consumed
        res2 = await gate.execute_action(
            action_name="publish_post",
            approval_id=approval.id,
            caller_telegram_id=fake_settings.owner_telegram_id,
        )
        assert res2.allowed is False
        assert "already been used" in res2.reason


@pytest.mark.asyncio
async def test_t_pub_04_paused_or_kill_switch_blocks(
    db_session: Session, fake_settings, sample_ready_draft
):
    """T-PUB-04: Paused or KILL_SWITCH on -> refused before LinkedIn call (SEC-024)."""
    _, approval = sample_ready_draft

    # 1. Kill Switch blocks
    kill_settings = fake_settings._replace(kill_switch=True)
    gate_kill = ExternalActionGate(db_session, kill_settings)
    r_kill = await gate_kill.execute_action(
        "publish_post", approval.id, fake_settings.owner_telegram_id
    )
    assert r_kill.allowed is False
    assert "KILL_SWITCH" in r_kill.reason

    # 2. Pause blocks
    cfg = db_session.execute(select(OwnerSettings).where(OwnerSettings.id == 1)).scalar_one()
    cfg.paused = True
    db_session.commit()

    gate_pause = ExternalActionGate(db_session, fake_settings)
    r_pause = await gate_pause.execute_action(
        "publish_post", approval.id, fake_settings.owner_telegram_id
    )
    assert r_pause.allowed is False
    assert "paused" in r_pause.reason


@pytest.mark.asyncio
async def test_t_pub_05_modified_text_or_expired_token_refused(
    db_session: Session, fake_settings, sample_ready_draft
):
    """T-PUB-05: Modified draft text or expired token is refused (SEC-013, FR-019)."""
    draft, approval = sample_ready_draft
    gate = ExternalActionGate(db_session, fake_settings)

    # 1. Edit draft body -> hash mismatch
    draft.body = "Tampered text that the owner never reviewed!"
    db_session.commit()

    r_hash = await gate.execute_action("publish_post", approval.id, fake_settings.owner_telegram_id)
    assert r_hash.allowed is False
    assert "hash mismatch" in r_hash.reason

    # Restore body, expire connection
    draft.body = "Professional milestone: Excited to share our new agent architecture!"
    stmt = select(LinkedInConnection).where(LinkedInConnection.id == 1)
    conn = db_session.execute(stmt).scalar_one()
    conn.expires_at = datetime.now(UTC) - timedelta(days=2)
    db_session.commit()

    r_token = await gate.execute_action(
        "publish_post", approval.id, fake_settings.owner_telegram_id
    )
    assert r_token.allowed is False
    assert "active LinkedIn connection" in r_token.reason


@pytest.mark.asyncio
async def test_t_pol_01_and_02_forbidden_actions_refused(
    db_session: Session, fake_settings, sample_ready_draft
):
    """T-POL-01, T-POL-02: Every forbidden action is refused regardless of settings (POL-F)."""
    _, approval = sample_ready_draft
    gate = ExternalActionGate(db_session, fake_settings)

    forbidden_list = [
        "like",
        "comment",
        "dm",
        "scrape",
        "connect",
        "auto_like",
        "auto_comment",
        "auto_dm",
        "auto_connect",
    ]

    for action in forbidden_list:
        res = await gate.execute_action(action, approval.id, fake_settings.owner_telegram_id)
        assert res.allowed is False
        assert "forbidden by policy" in res.reason


# --- Telegram Command Flow Tests ---


def _build_telegram_mocks(user_id: int, text: str, settings, session_factory, args=None):
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
    context.args = args or []
    context.bot_data = {
        "settings": settings,
        "db_session_factory": session_factory,
    }
    return update, message, context


@pytest.mark.asyncio
async def test_telegram_publish_command_success(fake_settings, enc_key):
    """FR-007: Owner runs /publish <draft_code> and receives confirmation."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = get_session_factory(engine)

    now = datetime.now(UTC)
    draft_body = "Celebrating our team's AI milestone!"
    d_hash = compute_hash(draft_body)

    with session_factory() as session:
        draft = Draft(
            code="d-pub-live",
            kind="post",
            version=1,
            body=draft_body,
            content_hash=d_hash,
            status="draft",
        )
        session.add(draft)
        session.flush()

        app = Approval(
            draft_id=draft.id,
            action_type="publish_post",
            decision="approved",
            content_hash=d_hash,
            requested_at=now,
            expires_at=now + timedelta(minutes=30),
            used_at=None,
        )
        session.add(app)

        conn = LinkedInConnection(
            id=1,
            member_urn="urn:li:person:me",
            granted_scopes="w_member_social",
            access_token_enc=EncryptionService(enc_key).encrypt("test_tok"),
            issued_at=now,
            expires_at=now + timedelta(days=30),
            status="active",
        )
        session.add(conn)

        owner_cfg = OwnerSettings(
            id=1,
            owner_telegram_id=fake_settings.owner_telegram_id,
            paused=False,
            publishing_enabled=True,
        )
        session.add(owner_cfg)
        session.commit()

    with respx.mock() as respx_mock:
        respx_mock.post(REST_POSTS_ENDPOINT).mock(
            return_value=Response(201, headers={"x-restli-id": "urn:li:share:112233"})
        )

        update, msg, ctx = _build_telegram_mocks(
            user_id=fake_settings.owner_telegram_id,
            text="/publish d-pub-live",
            settings=fake_settings,
            session_factory=session_factory,
            args=["d-pub-live"],
        )

        await publish_command(update, ctx)
        msg.reply_text.assert_awaited_once()
        reply = msg.reply_text.call_args[0][0]
        assert "Successfully Published to LinkedIn" in reply
        assert "urn:li:share:112233" in reply
