"""LinkedIn OAuth 2.0 service implementing FR-018, FR-019, FR-020, SEC-004, SEC-008, SEC-009.

Features:
- Single-use, cryptographically secure dynamic state parameters with 15-minute expiry.
- Minimum scopes requested: openid, profile, w_member_social.
- Tokens encrypted at rest using Fernet before saving to linkedin_connection (id=1).
- Token lifetime tracking with 14/7/3/1-day renewal warnings.
"""

import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import AuditLog, LinkedInConnection, OAuthState
from src.services.encryption_service import EncryptionService

LINKEDIN_AUTH_BASE = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_ENDPOINT = "https://www.linkedin.com/oauth/v2/accessToken"  # noqa: S105
LINKEDIN_USERINFO_ENDPOINT = "https://api.linkedin.com/v2/userinfo"
MINIMUM_SCOPES = "openid profile w_member_social"
DEFAULT_STATE_EXPIRY_MINUTES = 15


class LinkedInOAuthService:
    """Manages LinkedIn authorization, code exchange, and token persistence."""

    def __init__(self, db: Session, encryption_key: str = ""):
        self.db = db
        self.encryption_key = encryption_key

    def generate_authorization_url(self, client_id: str, redirect_uri: str) -> tuple[str, str]:
        """Generate official LinkedIn OAuth authorization URL with secure state (SEC-008, SEC-009).

        Returns:
            tuple[str, str]: (authorization_url, state)
        """
        if not client_id or not redirect_uri:
            raise ValueError("Client ID and redirect URI are required.")

        state = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=DEFAULT_STATE_EXPIRY_MINUTES)

        oauth_state = OAuthState(
            state=state,
            created_at=now,
            expires_at=expires_at,
            used_at=None,
        )
        self.db.add(oauth_state)
        self.db.commit()

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": MINIMUM_SCOPES,
        }
        url = f"{LINKEDIN_AUTH_BASE}?{urlencode(params)}"
        return url, state

    def validate_and_consume_state(self, state_str: str) -> None:
        """Validate that state exists, is unexpired, and has not been used (SEC-008)."""
        if not state_str:
            raise ValueError("State parameter is missing.")

        state_record = self.db.execute(
            select(OAuthState).where(OAuthState.state == state_str)
        ).scalar_one_or_none()

        if not state_record:
            raise ValueError("Invalid or unknown OAuth state.")

        if state_record.used_at is not None:
            raise ValueError("OAuth state has already been used (replay detected).")

        now = datetime.now(UTC)
        expires_at = state_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if now > expires_at:
            raise ValueError("OAuth state has expired.")

        # Mark as consumed immediately
        state_record.used_at = now
        self.db.commit()

    async def exchange_code_for_token(
        self,
        code: str,
        state_str: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> dict[str, str | int]:
        """Exchange authorization code for access token and persist encrypted (FR-018, SEC-004).

        Returns:
            dict with member_urn, expires_at (ISO), days_valid.
        """
        if not self.encryption_key:
            raise ValueError("Token encryption key is not configured.")

        # 1. State verification and single-use consumption
        self.validate_and_consume_state(state_str)

        # 2. Exchange code with LinkedIn official endpoint
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(LINKEDIN_TOKEN_ENDPOINT, data=data)

        if resp.status_code != 200:
            raise ValueError(
                f"LinkedIn token exchange failed: HTTP {resp.status_code}. Please try again."
            )

        payload = resp.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise ValueError("LinkedIn response did not contain an access_token.")

        expires_in = int(payload.get("expires_in", 5184000))  # Default 60 days
        granted_scope = payload.get("scope", MINIMUM_SCOPES)

        # 3. Retrieve member URN via OIDC userinfo endpoint
        member_urn = None
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                u_resp = await client.get(LINKEDIN_USERINFO_ENDPOINT, headers=headers)
            if u_resp.status_code == 200:
                sub = u_resp.json().get("sub")
                if sub:
                    member_urn = f"urn:li:person:{sub}"
        except Exception:
            # Fallback if userinfo is temporarily unreachable
            member_urn = "urn:li:person:unknown"

        # 4. Encrypt access token at rest (SEC-004)
        enc_service = EncryptionService(self.encryption_key)
        encrypted_token = enc_service.encrypt(access_token)

        # 5. Persist connection (single row id=1)
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=expires_in)

        conn = self.db.execute(
            select(LinkedInConnection).where(LinkedInConnection.id == 1)
        ).scalar_one_or_none()

        if conn is None:
            conn = LinkedInConnection(
                id=1,
                member_urn=member_urn,
                granted_scopes=granted_scope,
                access_token_enc=encrypted_token,
                issued_at=now,
                expires_at=expires_at,
                status="active",
                last_warning_days=None,
            )
            self.db.add(conn)
        else:
            conn.member_urn = member_urn
            conn.granted_scopes = granted_scope
            conn.access_token_enc = encrypted_token
            conn.issued_at = now
            conn.expires_at = expires_at
            conn.status = "active"
            conn.last_warning_days = None

        self.db.add(
            AuditLog(
                actor="owner",
                event="linkedin_connect",
                entity_type="linkedin_connection",
                entity_id="1",
                outcome="success",
                details={"expires_in": expires_in, "member_urn": member_urn},
            )
        )
        self.db.commit()

        days_valid = (expires_at - now).days
        return {
            "member_urn": member_urn or "unknown",
            "expires_at": expires_at.isoformat(),
            "days_valid": days_valid,
        }

    def get_connection_status(self) -> dict[str, str | int | bool | None]:
        """Query connection status, expiry, and renewal warning indicators (FR-019)."""
        conn = self.db.execute(
            select(LinkedInConnection).where(LinkedInConnection.id == 1)
        ).scalar_one_or_none()

        if not conn or conn.status != "active":
            return {
                "connected": False,
                "status": "not_connected" if not conn else conn.status,
                "days_remaining": None,
                "member_urn": None,
                "warning_needed": False,
            }

        now = datetime.now(UTC)
        expires_at = conn.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        delta = expires_at - now
        days_remaining = delta.days

        if days_remaining <= 0:
            conn.status = "expired"
            self.db.commit()
            return {
                "connected": False,
                "status": "expired",
                "days_remaining": 0,
                "member_urn": conn.member_urn,
                "warning_needed": True,
            }

        warning_needed = days_remaining <= 14
        return {
            "connected": True,
            "status": "active",
            "days_remaining": days_remaining,
            "expires_at": expires_at.isoformat(),
            "member_urn": conn.member_urn,
            "warning_needed": warning_needed,
        }

    def get_decrypted_token(self) -> str | None:
        """Decrypt and return the current active access token.

        Returns:
            str | None: Active access token if connected and valid, None otherwise.
        """
        status = self.get_connection_status()
        if not status["connected"]:
            return None

        conn = self.db.execute(
            select(LinkedInConnection).where(LinkedInConnection.id == 1)
        ).scalar_one_or_none()
        if not conn or not conn.access_token_enc or not self.encryption_key:
            return None

        enc_service = EncryptionService(self.encryption_key)
        return enc_service.decrypt(conn.access_token_enc)

    def disconnect(self) -> None:
        """Disconnect LinkedIn account and mark connection inactive."""
        conn = self.db.execute(
            select(LinkedInConnection).where(LinkedInConnection.id == 1)
        ).scalar_one_or_none()
        if conn:
            conn.status = "disconnected"
            conn.access_token_enc = b""
            self.db.add(
                AuditLog(
                    actor="owner",
                    event="linkedin_disconnect",
                    entity_type="linkedin_connection",
                    entity_id="1",
                    outcome="success",
                )
            )
            self.db.commit()
