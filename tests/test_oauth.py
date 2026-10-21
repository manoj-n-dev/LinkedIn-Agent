"""Tests for LinkedIn OAuth 2.0 flow, token encryption, and drafts-only fallback.

Covers: FR-018, FR-019, FR-020, SEC-004, SEC-008, SEC-009, SEC-017.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import respx
from httpx import Response
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from telegram import Chat, Message, Update, User

from src.config import Settings
from src.db.models import AuditLog, LinkedInConnection, OAuthState
from src.db.session import Base, get_session_factory
from src.services.encryption_service import EncryptionService
from src.services.linkedin_oauth_service import (
    LINKEDIN_TOKEN_ENDPOINT,
    LINKEDIN_USERINFO_ENDPOINT,
    LinkedInOAuthService,
)
from src.telegram_bot.oauth_handlers import (
    connect_command,
    connect_token_command,
    disconnect_command,
)


@pytest.fixture
def db_session():
    """In-memory SQLite database session for testing."""
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
        linkedin_client_id="dummy_li_client_id",
        linkedin_client_secret="dummy_li_client_secret",
        linkedin_redirect_url="https://localhost/callback",
    )


# --- Encryption Service Tests (SEC-004) ---


def test_fernet_encryption_and_decryption(enc_key):
    """SEC-004: Plaintext is encrypted to ciphertext and decrypts accurately."""
    service = EncryptionService(enc_key)
    raw_token = "AQV12345_sample_secret_token_from_linkedin"

    ciphertext = service.encrypt(raw_token)
    assert isinstance(ciphertext, bytes)
    assert raw_token.encode("utf-8") not in ciphertext  # Never stored in plaintext

    decrypted = service.decrypt(ciphertext)
    assert decrypted == raw_token


def test_fernet_decryption_with_wrong_key_fails(enc_key):
    """SEC-004: Decrypting with wrong key raises ValueError."""
    service1 = EncryptionService(enc_key)
    other_key = EncryptionService.generate_key()
    service2 = EncryptionService(other_key)

    ciphertext = service1.encrypt("my_secret_token")
    with pytest.raises(ValueError, match="Failed to decrypt token"):
        service2.decrypt(ciphertext)


def test_encryption_service_rejects_empty_or_invalid_key():
    """SEC-004: Empty or malformed encryption key raises ValueError."""
    with pytest.raises(ValueError, match="Encryption key cannot be empty"):
        EncryptionService("")

    with pytest.raises(ValueError, match="Invalid Fernet encryption key"):
        EncryptionService("not_a_base64_fernet_key")


# --- LinkedIn OAuth Service Tests (FR-018, SEC-008, SEC-009) ---


def test_generate_authorization_url_creates_state(db_session: Session, enc_key):
    """SEC-008, SEC-009: Generates dynamic state with 15-min expiry and minimum scopes."""
    service = LinkedInOAuthService(db_session, enc_key)
    url, state = service.generate_authorization_url(
        client_id="test_client_id",
        redirect_uri="https://localhost/callback",
    )

    assert "https://www.linkedin.com/oauth/v2/authorization" in url
    assert "response_type=code" in url
    assert "client_id=test_client_id" in url
    assert "scope=openid+profile+w_member_social" in url or "w_member_social" in url
    assert state in url

    # State recorded in DB
    state_rec = db_session.execute(
        select(OAuthState).where(OAuthState.state == state)
    ).scalar_one_or_none()
    assert state_rec is not None
    assert state_rec.used_at is None
    rec_exp = state_rec.expires_at
    if rec_exp.tzinfo is None:
        rec_exp = rec_exp.replace(tzinfo=UTC)
    assert rec_exp > datetime.now(UTC)


def test_state_replay_rejected(db_session: Session, enc_key):
    """SEC-008: Replaying an already-used state token is rejected."""
    service = LinkedInOAuthService(db_session, enc_key)
    _, state = service.generate_authorization_url("client", "https://localhost/callback")

    # First consumption succeeds
    service.validate_and_consume_state(state)

    # Second consumption raises replay detection error
    with pytest.raises(ValueError, match="already been used"):
        service.validate_and_consume_state(state)


def test_expired_state_rejected(db_session: Session, enc_key):
    """SEC-008: Expired state token is rejected."""
    service = LinkedInOAuthService(db_session, enc_key)
    now = datetime.now(UTC)
    expired_state = OAuthState(
        state="expired_state_val",
        created_at=now - timedelta(minutes=30),
        expires_at=now - timedelta(minutes=15),
        used_at=None,
    )
    db_session.add(expired_state)
    db_session.commit()

    with pytest.raises(ValueError, match="expired"):
        service.validate_and_consume_state("expired_state_val")


@pytest.mark.asyncio
async def test_exchange_code_for_token_mock_success(db_session: Session, enc_key):
    """FR-018, SEC-004: Token exchange succeeds, encrypts token, records audit log."""
    service = LinkedInOAuthService(db_session, enc_key)
    _, state = service.generate_authorization_url("client_id", "https://localhost/callback")

    fake_access_token = "AQV_dummy_linkedin_access_token_12345"

    with respx.mock() as respx_mock:
        respx_mock.post(LINKEDIN_TOKEN_ENDPOINT).mock(
            return_value=Response(
                200,
                json={
                    "access_token": fake_access_token,
                    "expires_in": 5184000,  # 60 days
                    "scope": "openid profile w_member_social",
                },
            )
        )
        respx_mock.get(LINKEDIN_USERINFO_ENDPOINT).mock(
            return_value=Response(200, json={"sub": "manoj123"})
        )

        res = await service.exchange_code_for_token(
            code="sample_auth_code",
            state_str=state,
            client_id="client_id",
            client_secret="client_secret",
            redirect_uri="https://localhost/callback",
        )

        assert res["member_urn"] == "urn:li:person:manoj123"
        assert res["days_valid"] >= 59

        # Verify DB connection record
        conn = db_session.execute(
            select(LinkedInConnection).where(LinkedInConnection.id == 1)
        ).scalar_one_or_none()
        assert conn is not None
        assert conn.status == "active"
        assert conn.access_token_enc != fake_access_token.encode("utf-8")

        # Decrypt token
        decrypted = service.get_decrypted_token()
        assert decrypted == fake_access_token

        # Verify Audit Log
        audit = db_session.execute(
            select(AuditLog).where(AuditLog.event == "linkedin_connect")
        ).scalar_one_or_none()
        assert audit is not None
        assert audit.outcome == "success"


@pytest.mark.asyncio
async def test_exchange_code_handles_linkedin_failure(db_session: Session, enc_key):
    """Token exchange handles 400 Bad Request gracefully."""
    service = LinkedInOAuthService(db_session, enc_key)
    _, state = service.generate_authorization_url("client_id", "https://localhost/callback")

    with respx.mock() as respx_mock:
        respx_mock.post(LINKEDIN_TOKEN_ENDPOINT).mock(
            return_value=Response(400, json={"error": "invalid_grant"})
        )

        with pytest.raises(ValueError, match="HTTP 400"):
            await service.exchange_code_for_token(
                code="bad_code",
                state_str=state,
                client_id="client_id",
                client_secret="client_secret",
                redirect_uri="https://localhost/callback",
            )


def test_connection_status_and_expiry_warnings(db_session: Session, enc_key):
    """FR-019: Connection status flags warnings when token expiry <= 14 days."""
    service = LinkedInOAuthService(db_session, enc_key)

    # 1. Not connected
    status1 = service.get_connection_status()
    assert not status1["connected"]
    assert status1["status"] == "not_connected"

    # 2. Connected with 60 days left
    now = datetime.now(UTC)
    conn = LinkedInConnection(
        id=1,
        member_urn="urn:li:person:abc",
        granted_scopes="w_member_social",
        access_token_enc=EncryptionService(enc_key).encrypt("token"),
        issued_at=now,
        expires_at=now + timedelta(days=60),
        status="active",
    )
    db_session.add(conn)
    db_session.commit()

    status2 = service.get_connection_status()
    assert status2["connected"]
    assert not status2["warning_needed"]

    # 3. Warning needed (7 days left)
    conn.expires_at = now + timedelta(days=7)
    db_session.commit()
    status3 = service.get_connection_status()
    assert status3["connected"]
    assert status3["warning_needed"]

    # 4. Expired (-1 day)
    conn.expires_at = now - timedelta(days=1)
    db_session.commit()
    status4 = service.get_connection_status()
    assert not status4["connected"]
    assert status4["status"] == "expired"


# --- Telegram Command Handlers Tests (FR-018, FR-020) ---


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
async def test_telegram_connect_drafts_only_when_credentials_missing(fake_settings):
    """FR-020: /connect gracefully explains drafts-only mode if credentials not configured."""
    unconfigured_settings = Settings(
        telegram_bot_token=fake_settings.telegram_bot_token,
        owner_telegram_id=fake_settings.owner_telegram_id,
        database_url="sqlite:///:memory:",
        groq_api_key=fake_settings.groq_api_key,
        groq_model=fake_settings.groq_model,
        linkedin_client_id="",  # Empty
        linkedin_client_secret="",  # Empty
        token_encryption_key="",  # Empty
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = get_session_factory(engine)

    update, msg, ctx = _build_telegram_mocks(
        user_id=unconfigured_settings.owner_telegram_id,
        text="/connect",
        settings=unconfigured_settings,
        session_factory=session_factory,
    )

    await connect_command(update, ctx)
    msg.reply_text.assert_awaited_once()
    reply = msg.reply_text.call_args[0][0]
    assert "drafts-only mode" in reply.lower()


@pytest.mark.asyncio
async def test_telegram_connect_and_connect_token_flow(fake_settings):
    """FR-018: Full /connect and /connect_token flow in Telegram."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = get_session_factory(engine)

    # 1. /connect returns authorization link
    up1, msg1, ctx1 = _build_telegram_mocks(
        user_id=fake_settings.owner_telegram_id,
        text="/connect",
        settings=fake_settings,
        session_factory=session_factory,
    )
    await connect_command(up1, ctx1)
    msg1.reply_text.assert_awaited_once()
    assert "Connect Your LinkedIn Account" in msg1.reply_text.call_args[0][0]

    # Retrieve generated state
    with session_factory() as session:
        state_record = session.execute(select(OAuthState)).scalars().first()
        assert state_record is not None
        gen_state = state_record.state

    # 2. /connect_token completes exchange
    with respx.mock() as respx_mock:
        respx_mock.post(LINKEDIN_TOKEN_ENDPOINT).mock(
            return_value=Response(
                200,
                json={"access_token": "mocked_token_val", "expires_in": 5184000},
            )
        )
        respx_mock.get(LINKEDIN_USERINFO_ENDPOINT).mock(
            return_value=Response(200, json={"sub": "owner_sub_id"})
        )

        up2, msg2, ctx2 = _build_telegram_mocks(
            user_id=fake_settings.owner_telegram_id,
            text=f"/connect_token mock_code {gen_state}",
            settings=fake_settings,
            session_factory=session_factory,
            args=["mock_code", gen_state],
        )
        await connect_token_command(up2, ctx2)
        msg2.reply_text.assert_awaited_once()
        assert "LinkedIn Connected Successfully" in msg2.reply_text.call_args[0][0]

    # 3. /disconnect marks disconnected
    up3, msg3, ctx3 = _build_telegram_mocks(
        user_id=fake_settings.owner_telegram_id,
        text="/disconnect",
        settings=fake_settings,
        session_factory=session_factory,
    )
    await disconnect_command(up3, ctx3)
    msg3.reply_text.assert_awaited_once()
    assert "Disconnected" in msg3.reply_text.call_args[0][0]
