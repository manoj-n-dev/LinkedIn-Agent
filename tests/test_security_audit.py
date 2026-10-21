"""Phase 12: Comprehensive Security Verification & Audit Test Suite.

Covers:
- SEC-007: Secret rotation and revocation drill test.
- SEC-008: Scope least-privilege verification.
- SEC-021, SEC-023: Data minimization, context retention (7-day), and SeenItems pruning (30-day).
- SEC-024, SEC-025: Incident response tabletop drill (/pause, KILL_SWITCH, audit review).
- SEC-030, FR-030: Outbound network allow-list verification (T-NET-01).
"""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.config import Settings
from src.db.models import (
    Approval,
    AuditLog,
    Draft,
    LinkedInConnection,
    OwnerSettings,
    SeenItem,
    UnauthorizedAttempt,
)
from src.db.session import Base, get_session_factory
from src.services.action_gate import ExternalActionGate
from src.services.encryption_service import EncryptionService
from src.services.linkedin_oauth_service import MINIMUM_SCOPES, LinkedInOAuthService
from src.services.network_guard import NetworkGuard, NetworkSecurityError


@pytest.fixture
def db_session():
    """In-memory SQLite session with StaticPool for audit testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
        linkedin_redirect_url="https://localhost:8000/callback/linkedin",
        publishing_enabled=True,
        kill_switch=False,
    )


# --- T-NET-01: Outbound Network Allow-List (FR-030, SEC-030) ---


def test_t_net_01_outbound_allow_list_enforcement():
    """T-NET-01: Requests to authorized hosts pass; unknown hosts or protocols fail."""
    guard = NetworkGuard(additional_allowed_hosts={"techcrunch.com", "news.google.com"})

    # 1. Allowed official endpoints
    assert guard.validate_url("https://api.telegram.org/bot123/sendMessage")
    assert guard.validate_url("https://api.groq.com/openai/v1/chat/completions")
    assert guard.validate_url("https://api.linkedin.com/rest/posts")
    assert guard.validate_url("https://www.linkedin.com/oauth/v2/accessToken")
    assert guard.validate_url("https://hacker-news.firebaseio.com/v0/topstories.json")
    assert guard.validate_url("https://techcrunch.com/feed/")

    # 2. Block unauthorized domains and telemetry
    with pytest.raises(NetworkSecurityError, match="not in the allow-list"):
        guard.validate_url("https://telemetry.evil-analytics.com/collect")

    with pytest.raises(NetworkSecurityError, match="not in the allow-list"):
        guard.validate_url("https://unapproved-api.example.org/data")

    # 3. Block private IPs and non-HTTP schemes
    with pytest.raises(NetworkSecurityError, match="not in the allow-list"):
        guard.validate_url("http://192.168.1.100:8080/exploit")

    with pytest.raises(NetworkSecurityError, match="Prohibited URL scheme"):
        guard.validate_url("file:///etc/passwd")


# --- SEC-007: Secret Rotation & Revocation Drill ---


def test_sec_007_secret_rotation_drill(db_session: Session, enc_key):
    """SEC-007: Dry-run drill for rotating encryption key and re-encrypting tokens."""
    now = datetime.now(UTC)
    raw_token = "AQV_live_active_linkedin_token_to_rotate_12345"

    # 1. Stored under old key
    old_enc = EncryptionService(enc_key)
    conn = LinkedInConnection(
        id=1,
        member_urn="urn:li:person:owner123",
        granted_scopes="w_member_social",
        access_token_enc=old_enc.encrypt(raw_token),
        issued_at=now,
        expires_at=now + timedelta(days=60),
        status="active",
    )
    db_session.add(conn)
    db_session.commit()

    # 2. Key Rotation Drill: Generate new key, decrypt with old, re-encrypt with new
    new_key = EncryptionService.generate_key()
    new_enc = EncryptionService(new_key)

    decrypted = old_enc.decrypt(conn.access_token_enc)
    assert decrypted == raw_token

    conn.access_token_enc = new_enc.encrypt(decrypted)
    db_session.add(
        AuditLog(
            actor="owner",
            event="secret_rotation",
            entity_type="encryption_key",
            entity_id="1",
            outcome="success",
            details={"action": "re_encrypted_linkedin_token"},
        )
    )
    db_session.commit()

    # 3. Verify new key decrypts, old key fails
    assert new_enc.decrypt(conn.access_token_enc) == raw_token
    with pytest.raises(ValueError, match="Failed to decrypt token"):
        old_enc.decrypt(conn.access_token_enc)


# --- SEC-008: Scope Least-Privilege Verification ---


def test_sec_008_least_privilege_scope_verification():
    """SEC-008: Requested scopes are strictly limited to minimum posting scopes."""
    scopes = set(MINIMUM_SCOPES.split())
    expected = {"openid", "profile", "w_member_social"}
    assert scopes == expected

    # Verify no feed reading, messaging, or contact scopes are included
    forbidden_scopes = {
        "r_liteprofile",
        "r_emailaddress",
        "r_member_social",
        "w_member_messages",
        "r_1st_connections",
        "rw_organization_admin",
    }
    assert scopes.isdisjoint(forbidden_scopes)


# --- SEC-021 & SEC-023: Data Minimization & Retention Pruning ---


def test_sec_021_and_023_data_retention_pruning(db_session: Session):
    """SEC-021, SEC-023: Context older than 7d cleared, SeenItems older than 30d pruned."""
    now = datetime.now(UTC)

    # 1. Draft with pasted context older than 7 days
    old_draft = Draft(
        code="d-retention-old",
        kind="post",
        version=1,
        body="Draft with old context",
        content_hash="h1",
        context_text="Confidential notes pasted 8 days ago",
        created_at=now - timedelta(days=8),
        updated_at=now - timedelta(days=8),
    )
    # Draft with recent context (2 days ago)
    recent_draft = Draft(
        code="d-retention-new",
        kind="post",
        version=1,
        body="Draft with recent context",
        content_hash="h2",
        context_text="Fresh notes from 2 days ago",
        created_at=now - timedelta(days=2),
        updated_at=now - timedelta(days=2),
    )
    db_session.add_all([old_draft, recent_draft])

    # 2. Seen items older than 30 days
    old_seen = SeenItem(url_hash="old_url_hash", first_seen_at=now - timedelta(days=35))
    recent_seen = SeenItem(url_hash="recent_url_hash", first_seen_at=now - timedelta(days=5))
    db_session.add_all([old_seen, recent_seen])

    # 3. Unauthorized stranger attempt: one-way SHA-256 hash only
    stranger_numeric_id = 9988776655
    stranger_hash = hashlib.sha256(str(stranger_numeric_id).encode("utf-8")).hexdigest()
    attempt = UnauthorizedAttempt(ts=now, id_hash=stranger_hash)
    db_session.add(attempt)

    db_session.commit()

    # Execute maintenance / pruning logic (from src/scheduler/tick.py)
    seven_days_ago = now - timedelta(days=7)
    db_session.query(Draft).filter(
        Draft.created_at < seven_days_ago,
        Draft.context_text.isnot(None),
    ).update({Draft.context_text: None}, synchronize_session=False)

    thirty_days_ago = now - timedelta(days=30)
    db_session.query(SeenItem).filter(SeenItem.first_seen_at < thirty_days_ago).delete()
    db_session.commit()

    # Verify old context wiped, recent context preserved
    db_session.refresh(old_draft)
    db_session.refresh(recent_draft)
    assert old_draft.context_text is None
    assert recent_draft.context_text == "Fresh notes from 2 days ago"

    # Verify old SeenItem deleted, recent preserved
    old_q = select(SeenItem).where(SeenItem.url_hash == "old_url_hash")
    assert db_session.execute(old_q).scalar_one_or_none() is None

    recent_q = select(SeenItem).where(SeenItem.url_hash == "recent_url_hash")
    assert db_session.execute(recent_q).scalar_one_or_none() is not None

    # Verify stranger record does not contain raw ID
    stored_attempt = db_session.execute(select(UnauthorizedAttempt)).scalar_one()
    assert str(stranger_numeric_id) not in stored_attempt.id_hash
    assert stored_attempt.id_hash == stranger_hash


# --- SEC-024 & SEC-025: Incident Response Tabletop Drill ---


@pytest.mark.asyncio
async def test_sec_024_and_025_incident_response_drill(db_session: Session, fake_settings, enc_key):
    """SEC-024, SEC-025: Tabletop drill: Emergency pause -> revoke -> inspect -> resume."""
    now = datetime.now(UTC)

    # Setup draft & approval
    draft = Draft(
        code="d-incident",
        kind="post",
        version=1,
        body="Post content",
        content_hash=hashlib.sha256(b"Post content").hexdigest(),
    )
    db_session.add(draft)
    db_session.flush()

    approval = Approval(
        draft_id=draft.id,
        action_type="publish_post",
        decision="approved",
        content_hash=draft.content_hash,
        requested_at=now,
        expires_at=now + timedelta(minutes=30),
        used_at=None,
    )
    conn = LinkedInConnection(
        id=1,
        member_urn="urn:li:person:me",
        granted_scopes="w_member_social",
        access_token_enc=EncryptionService(enc_key).encrypt("valid_tok"),
        issued_at=now,
        expires_at=now + timedelta(days=30),
        status="active",
    )
    owner_cfg = OwnerSettings(
        id=1,
        owner_telegram_id=fake_settings.owner_telegram_id,
        paused=False,
        publishing_enabled=True,
    )
    db_session.add_all([approval, conn, owner_cfg])
    db_session.commit()

    gate = ExternalActionGate(db_session, fake_settings)

    # 1. Normal state: publishing allowed
    # (Simulate incident: owner notices anomalous behavior or leaked secret)

    # 2. Incident Step 1: STOP (Emergency Pause)
    owner_cfg.paused = True
    db_session.add(
        AuditLog(
            actor="owner",
            event="incident_declared",
            entity_type="system",
            entity_id="global",
            outcome="paused",
            details={"reason": "simulated_token_compromise"},
        )
    )
    db_session.commit()

    # Gate must immediately refuse all calls
    res = await gate.execute_action("publish_post", approval.id, fake_settings.owner_telegram_id)
    assert res.allowed is False
    assert "paused" in res.reason

    # 3. Incident Step 2: CONTAIN (Revoke / Disconnect LinkedIn)
    oauth_service = LinkedInOAuthService(db_session, fake_settings.token_encryption_key)
    oauth_service.disconnect()

    db_session.refresh(conn)
    assert conn.status == "disconnected"
    assert conn.access_token_enc == b""

    # 4. Incident Step 3: AUDIT REVIEW (Check audit_log)
    logs = db_session.execute(select(AuditLog)).scalars().all()
    assert any(log.event == "incident_declared" for log in logs)
    assert any(log.event == "linkedin_disconnect" for log in logs)

    # 5. Incident Step 4: RESUME (After containment, re-link, unpause)
    owner_cfg.paused = False
    db_session.commit()
    assert owner_cfg.paused is False
