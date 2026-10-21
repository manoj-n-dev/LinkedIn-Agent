"""Tests for FastAPI webhook deployment, secret token validation, and OAuth callback.

Covers:
- T-WEB-01: Webhook request without or with wrong secret header -> rejected 403 (SEC-010).
- Webhook update deduplication and idempotency.
- Liveness healthcheck /health.
- Web-based OAuth redirect callback /callback/linkedin.
"""

from unittest.mock import AsyncMock, patch

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from src.config import Settings
from src.db.models import OAuthState
from src.db.session import Base, get_session_factory
from src.services.encryption_service import EncryptionService
from src.services.linkedin_oauth_service import LINKEDIN_TOKEN_ENDPOINT, LINKEDIN_USERINFO_ENDPOINT
from src.web.app import create_app


@pytest.fixture
def db_session():
    """In-memory SQLite database session for deployment testing."""
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
def deploy_settings(enc_key):
    return Settings(
        telegram_bot_token="123456789:ABCDefghIJKLmnOPQRstuvWXYZ",
        owner_telegram_id=987654321,
        database_url="sqlite:///:memory:",
        groq_api_key="gsk_" + "dummyfakegroqapikey123456789",
        groq_model="llama-3.3-70b-versatile",
        telegram_webhook_secret="super_secret_webhook_token_xyz123",
        token_encryption_key=enc_key,
        linkedin_client_id="deploy_client_id",
        linkedin_client_secret="deploy_client_secret",
        linkedin_redirect_url="https://localhost:8000/callback/linkedin",
    )


@pytest.fixture
def test_client(deploy_settings):
    """TestClient fixture with in-memory database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = get_session_factory(engine)

    app = create_app(
        settings=deploy_settings, session_factory=session_factory, init_bot=False
    )
    with TestClient(app) as client:
        yield client, session_factory


def test_healthcheck_endpoint(test_client):
    """Liveness probe /health returns 200 OK."""
    client, _ = test_client
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_t_web_01_webhook_rejected_without_secret_token(test_client, deploy_settings):
    """T-WEB-01: Inbound webhook missing secret header is rejected with 403 (SEC-010)."""
    client, _ = test_client
    payload = {"update_id": 1001, "message": {"text": "/start"}}

    # 1. No secret header
    resp1 = client.post("/webhook/telegram", json=payload)
    assert resp1.status_code == 403
    assert "Invalid secret token" in resp1.json()["detail"]

    # 2. Wrong secret header
    headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong_secret_value"}
    resp2 = client.post("/webhook/telegram", json=payload, headers=headers)
    assert resp2.status_code == 403


def test_webhook_accepted_with_valid_secret(test_client, deploy_settings):
    """Inbound webhook with valid secret token is accepted."""
    client, _ = test_client
    payload = {
        "update_id": 2001,
        "message": {
            "message_id": 1,
            "date": 1600000000,
            "chat": {"id": deploy_settings.owner_telegram_id, "type": "private"},
            "from": {
                "id": deploy_settings.owner_telegram_id,
                "is_bot": False,
                "first_name": "Owner",
            },
            "text": "/help",
        },
    }
    headers = {"X-Telegram-Bot-Api-Secret-Token": deploy_settings.telegram_webhook_secret}

    with patch("telegram.ext.Application.process_update", new_callable=AsyncMock) as mock_process:
        resp = client.post("/webhook/telegram", json=payload, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_process.assert_awaited_once()


def test_webhook_idempotency_duplicate_update_ignored(test_client, deploy_settings):
    """Duplicate update_id is recognized and ignored idempotently."""
    client, _ = test_client
    payload = {
        "update_id": 3001,
        "message": {
            "message_id": 1,
            "date": 1600000000,
            "chat": {"id": deploy_settings.owner_telegram_id, "type": "private"},
            "from": {
                "id": deploy_settings.owner_telegram_id,
                "is_bot": False,
                "first_name": "Owner",
            },
            "text": "/status",
        },
    }
    headers = {"X-Telegram-Bot-Api-Secret-Token": deploy_settings.telegram_webhook_secret}

    with patch("telegram.ext.Application.process_update", new_callable=AsyncMock) as mock_process:
        # First delivery -> processed
        resp1 = client.post("/webhook/telegram", json=payload, headers=headers)
        assert resp1.status_code == 200
        assert mock_process.await_count == 1

        # Second delivery with same update_id -> duplicate ignored
        resp2 = client.post("/webhook/telegram", json=payload, headers=headers)
        assert resp2.status_code == 200
        assert resp2.json().get("note") == "duplicate"
        assert mock_process.await_count == 1  # Not processed again


def test_oauth_callback_browser_redirect_flow(test_client, deploy_settings):
    """Browser OAuth callback endpoint /callback/linkedin handles exchange and renders HTML."""
    client, session_factory = test_client

    # 1. Error response from LinkedIn
    err_resp = client.get("/callback/linkedin?error=user_cancelled_login")
    assert err_resp.status_code == 400
    assert "user_cancelled_login" in err_resp.text

    # 2. Missing code or state
    missing_resp = client.get("/callback/linkedin")
    assert missing_resp.status_code == 400
    assert "Missing Parameters" in missing_resp.text

    # 3. Successful exchange
    # Seed OAuthState in database
    from datetime import UTC, datetime, timedelta
    now = datetime.now(UTC)
    with session_factory() as session:
        session.add(
            OAuthState(
                state="valid_oauth_state_123",
                created_at=now,
                expires_at=now + timedelta(minutes=15),
                used_at=None,
            )
        )
        session.commit()

    with respx.mock() as respx_mock:
        respx_mock.post(LINKEDIN_TOKEN_ENDPOINT).mock(
            return_value=Response(
                200,
                json={"access_token": "valid_token_abc", "expires_in": 5184000},
            )
        )
        respx_mock.get(LINKEDIN_USERINFO_ENDPOINT).mock(
            return_value=Response(200, json={"sub": "member_web_123"})
        )

        success_resp = client.get(
            "/callback/linkedin?code=auth_code_xyz&state=valid_oauth_state_123"
        )
        assert success_resp.status_code == 200
        assert "LinkedIn Connected Successfully" in success_resp.text
        assert "member_web_123" in success_resp.text
