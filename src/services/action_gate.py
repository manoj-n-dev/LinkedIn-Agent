"""External Action Gate (SEC-013, SEC-014, SEC-020, POL-F, FR-007, FR-025).

The ONLY code path to LinkedIn in the entire application.
Enforces the mandatory 9-step check order:
1. Kill switch environment flag (stops all LinkedIn actions).
2. Bot paused setting.
3. Feature flag (publishing_enabled).
4. Owner ID check (caller is owner).
5. Policy check (action in allowed list, not in forbidden list).
6. Approval validity (status == 'approved', unexpired, unused).
7. Content integrity (hash == draft body hash).
8. Token validity (active LinkedIn connection with valid decrypted token).
9. Atomic attempt record: Create PublishAttempt and mark approval used in ONE
   transaction BEFORE calling LinkedIn.
10. Call official LinkedIn API; handle success, failure, and timeout (outcome UNKNOWN).
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import Settings
from src.db.models import (
    Approval,
    AuditLog,
    Draft,
    OwnerSettings,
    PublishAttempt,
)
from src.services.linkedin_client import (
    PublishAPIError,
    PublishTimeoutError,
    publish_ugc_post,
)
from src.services.linkedin_oauth_service import LinkedInOAuthService

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS: set[str] = {"publish_post"}

FORBIDDEN_ACTIONS: set[str] = {
    "like",
    "reaction",
    "comment",
    "dm",
    "direct_message",
    "connect",
    "connection_invite",
    "accept_invitation",
    "scrape",
    "scrape_feed",
    "scrape_profile",
    "auto_like",
    "auto_comment",
    "auto_dm",
    "auto_connect",
}


def compute_text_hash(text: str) -> str:
    """Compute standard SHA-256 hash for exact content matching."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class GateResult:
    """Result of an External Action Gate execution."""

    allowed: bool
    outcome: str  # refused / success / failed / unknown
    reason: str = ""
    post_id: str | None = None
    http_status: int | None = None
    attempt_id: str | None = None


class ExternalActionGate:
    """The single centralized security gate for all LinkedIn-facing actions."""

    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings

    def _get_owner_settings(self) -> OwnerSettings | None:
        return self.db.execute(
            select(OwnerSettings).where(OwnerSettings.id == 1)
        ).scalar_one_or_none()

    async def execute_action(
        self,
        action_name: str,
        approval_id: str,
        caller_telegram_id: int,
        endpoint_override: str | None = None,
    ) -> GateResult:
        """Execute a LinkedIn action through the strict verification sequence.

        Args:
            action_name: Requested action (must be 'publish_post').
            approval_id: UUID of the approved approval row.
            caller_telegram_id: Telegram user ID of the caller.
            endpoint_override: Optional alternative endpoint for testing.

        Returns:
            GateResult: Outcome and details of the gate check and execution.
        """
        now = datetime.now(UTC)

        # -------------------------------------------------------------
        # CHECK 1: Kill switch (Host environment setting)
        # -------------------------------------------------------------
        if self.settings.kill_switch:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason="Publishing refused: KILL_SWITCH is active in host environment.",
            )

        # -------------------------------------------------------------
        # CHECK 2: Bot paused setting
        # -------------------------------------------------------------
        owner_cfg = self._get_owner_settings()
        if owner_cfg and owner_cfg.paused:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason="Publishing refused: Bot is currently paused.",
            )

        # -------------------------------------------------------------
        # CHECK 3: Feature flag (publishing_enabled default DENY)
        # -------------------------------------------------------------
        is_publishing_enabled = self.settings.publishing_enabled or (
            owner_cfg is not None and owner_cfg.publishing_enabled
        )
        if not is_publishing_enabled:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason=(
                    "Publishing refused: publishing_enabled is OFF. "
                    "The bot is running in drafts-only mode (FR-020)."
                ),
            )

        # -------------------------------------------------------------
        # CHECK 4: Owner ID check
        # -------------------------------------------------------------
        if caller_telegram_id != self.settings.owner_telegram_id:
            logger.warning(
                "Unauthorized publish attempt by caller %s (expected %s)",
                caller_telegram_id,
                self.settings.owner_telegram_id,
            )
            return GateResult(
                allowed=False,
                outcome="refused",
                reason="Publishing refused: Caller is not the designated owner.",
            )

        # -------------------------------------------------------------
        # CHECK 5: Policy check (Allowed actions vs Forbidden list)
        # -------------------------------------------------------------
        clean_action = action_name.strip().lower()
        if clean_action in FORBIDDEN_ACTIONS:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason=f"Action '{action_name}' is strictly forbidden by policy (POL-F).",
            )

        if clean_action not in ALLOWED_ACTIONS:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason=f"Action '{action_name}' is not an authorized LinkedIn action.",
            )

        # -------------------------------------------------------------
        # CHECK 6: Approval validity (Approved + Unexpired + Unused)
        # -------------------------------------------------------------
        approval = self.db.execute(
            select(Approval).where(Approval.id == approval_id)
        ).scalar_one_or_none()
        if not approval:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason=f"Approval record '{approval_id}' not found.",
            )

        if approval.decision != "approved":
            return GateResult(
                allowed=False,
                outcome="refused",
                reason=f"Approval decision is '{approval.decision}', not 'approved'.",
            )

        if approval.used_at is not None:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason="Approval has already been used (single-use guarantee violated).",
            )

        app_expires = approval.expires_at
        if app_expires.tzinfo is None:
            app_expires = app_expires.replace(tzinfo=UTC)

        if now > app_expires:
            approval.decision = "expired"
            self.db.commit()
            return GateResult(
                allowed=False,
                outcome="refused",
                reason="Approval has expired. A fresh approval is required.",
            )

        # -------------------------------------------------------------
        # CHECK 7: Content integrity (Exact SHA-256 text hash match)
        # -------------------------------------------------------------
        draft = self.db.execute(
            select(Draft).where(Draft.id == approval.draft_id)
        ).scalar_one_or_none()
        if not draft:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason="Referenced draft for approval was not found.",
            )

        current_hash = compute_text_hash(draft.body)
        if current_hash != approval.content_hash:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason="Draft content was modified after approval was granted (hash mismatch).",
            )

        # -------------------------------------------------------------
        # CHECK 8: Decrypted token & active LinkedIn connection check
        # -------------------------------------------------------------
        oauth_service = LinkedInOAuthService(
            self.db, encryption_key=self.settings.token_encryption_key
        )
        conn_status = oauth_service.get_connection_status()
        if not conn_status["connected"]:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason="No active LinkedIn connection found. Use /connect to link your account.",
            )

        access_token = oauth_service.get_decrypted_token()
        if not access_token:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason="Failed to decrypt LinkedIn access token. Check encryption key.",
            )

        author_urn = str(conn_status.get("member_urn") or "")
        if not author_urn or author_urn == "unknown":
            author_urn = "urn:li:person:me"

        # -------------------------------------------------------------
        # CHECK 9: Atomic attempt creation & approval consumption BEFORE API call
        # -------------------------------------------------------------
        idempotency_key = f"pub-{approval.id}"
        existing_attempt = self.db.execute(
            select(PublishAttempt).where(PublishAttempt.approval_id == approval.id)
        ).scalar_one_or_none()
        if existing_attempt:
            return GateResult(
                allowed=False,
                outcome="refused",
                reason="A publish attempt already exists for this approval (idempotency guard).",
            )

        attempt = PublishAttempt(
            draft_id=draft.id,
            approval_id=approval.id,
            idempotency_key=idempotency_key,
            started_at=now,
            outcome="started",
        )
        approval.used_at = now
        self.db.add(attempt)
        self.db.commit()

        # -------------------------------------------------------------
        # STEP 10: Official LinkedIn API Call
        # -------------------------------------------------------------
        target_endpoint = endpoint_override or "https://api.linkedin.com/rest/posts"

        try:
            pub_res = await publish_ugc_post(
                access_token=access_token,
                author_urn=author_urn,
                text=draft.body,
                endpoint=target_endpoint,
            )
            # Success (HTTP 200 or 201)
            finished_now = datetime.now(UTC)
            attempt.outcome = "success"
            attempt.finished_at = finished_now
            attempt.http_status = pub_res["http_status"]
            attempt.linkedin_post_id = pub_res["post_id"]
            draft.status = "published"

            self.db.add(
                AuditLog(
                    actor="gate",
                    event="post_published",
                    entity_type="draft",
                    entity_id=draft.id,
                    outcome="success",
                    details={"post_id": pub_res["post_id"], "attempt_id": attempt.id},
                )
            )
            self.db.commit()

            return GateResult(
                allowed=True,
                outcome="success",
                post_id=pub_res["post_id"],
                http_status=pub_res["http_status"],
                attempt_id=attempt.id,
            )

        except PublishAPIError as e:
            # HTTP 4xx, 429, 5xx: Failed. NEVER retry automatically.
            finished_now = datetime.now(UTC)
            attempt.outcome = "failed"
            attempt.finished_at = finished_now
            attempt.http_status = e.status_code
            attempt.error_code = e.message[:500]

            self.db.add(
                AuditLog(
                    actor="gate",
                    event="post_publish_failed",
                    entity_type="draft",
                    entity_id=draft.id,
                    outcome="failed",
                    details={"status_code": e.status_code, "error": e.message[:200]},
                )
            )
            self.db.commit()

            return GateResult(
                allowed=True,
                outcome="failed",
                reason=f"LinkedIn API error (HTTP {e.status_code}): {e.message[:200]}",
                http_status=e.status_code,
                attempt_id=attempt.id,
            )

        except PublishTimeoutError as e:
            # Network Timeout: outcome UNKNOWN. NEVER retry automatically.
            finished_now = datetime.now(UTC)
            attempt.outcome = "unknown"
            attempt.finished_at = finished_now
            attempt.error_code = str(e)[:500]

            self.db.add(
                AuditLog(
                    actor="gate",
                    event="post_publish_timeout",
                    entity_type="draft",
                    entity_id=draft.id,
                    outcome="unknown",
                    details={"error": str(e)[:200]},
                )
            )
            self.db.commit()

            return GateResult(
                allowed=True,
                outcome="unknown",
                reason=(
                    "Network timed out while communicating with LinkedIn. "
                    "Outcome is UNKNOWN. Automatic retry is FORBIDDEN. "
                    "Please check your LinkedIn profile manually before re-approving."
                ),
                attempt_id=attempt.id,
            )
