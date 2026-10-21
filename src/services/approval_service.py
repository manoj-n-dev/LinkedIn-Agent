"""Approval service implementing exact-text, single-use approval workflows.

Covers FR-006, FR-017, FR-027, SEC-013.
"""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Approval, AuditLog, CallbackToken, Draft, OwnerSettings

logger = logging.getLogger(__name__)

DEFAULT_APPROVAL_EXPIRY_MINUTES = 30


def compute_text_hash(text: str) -> str:
    """Compute SHA-256 hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ApprovalService:
    """Orchestrates approval generation, button callbacks, and publish validation."""

    def __init__(self, db: Session):
        self.db = db

    def _get_or_create_owner_settings(self, owner_telegram_id: int) -> OwnerSettings:
        cfg = self.db.execute(
            select(OwnerSettings).where(OwnerSettings.id == 1)
        ).scalar_one_or_none()
        if not cfg:
            cfg = OwnerSettings(id=1, owner_telegram_id=owner_telegram_id)
            self.db.add(cfg)
            self.db.flush()
        return cfg

    def request_approval(
        self,
        draft_code: str,
        action_type: str = "publish_post",
        expires_minutes: int = DEFAULT_APPROVAL_EXPIRY_MINUTES,
    ) -> tuple[Approval, CallbackToken, CallbackToken, str]:
        """Create an approval request with exact-text hash and single-use tokens.
        (FR-006, FR-017).
        """
        draft = self.db.execute(select(Draft).where(Draft.code == draft_code)).scalar_one_or_none()
        if not draft:
            raise ValueError(f"Draft '{draft_code}' not found.")

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=expires_minutes)
        content_hash = compute_text_hash(draft.body)

        approval = Approval(
            draft_id=draft.id,
            action_type=action_type,
            content_hash=content_hash,
            requested_at=now,
            expires_at=expires_at,
            decision="pending",
        )
        self.db.add(approval)
        self.db.flush()

        approve_token = CallbackToken(
            token=f"app_{secrets.token_urlsafe(16)}",
            purpose="approve",
            draft_id=draft.id,
            approval_id=approval.id,
            created_at=now,
            expires_at=expires_at,
        )
        reject_token = CallbackToken(
            token=f"rej_{secrets.token_urlsafe(16)}",
            purpose="reject",
            draft_id=draft.id,
            approval_id=approval.id,
            created_at=now,
            expires_at=expires_at,
        )
        self.db.add_all([approve_token, reject_token])

        self.db.add(
            AuditLog(
                actor="system",
                event="approval_requested",
                entity_type="approval",
                entity_id=approval.id,
                outcome="pending",
                details={
                    "draft_code": draft.code,
                    "draft_version": draft.version,
                    "content_hash": content_hash,
                    "expires_at": expires_at.isoformat(),
                },
            )
        )
        self.db.commit()
        self.db.refresh(approval)

        char_count = len(draft.body)
        word_count = len(draft.body.split())
        preview_text = (
            f"📋 Approval Request for [{draft.code}] (v{draft.version}):\n\n"
            f"{draft.body}\n\n"
            f"📊 Length: {char_count} chars, {word_count} words\n"
            f"⏰ Valid for {expires_minutes} minutes"
        )
        return approval, approve_token, reject_token, preview_text

    def handle_callback_decision(
        self,
        token_str: str,
        owner_telegram_id: int,
    ) -> tuple[bool, str, Approval | None]:
        """Handle inline button press for approve/reject using single-use token (SEC-013)."""
        now = datetime.now(UTC)
        cb_token = self.db.execute(
            select(CallbackToken).where(CallbackToken.token == token_str)
        ).scalar_one_or_none()

        if not cb_token:
            return False, "Invalid or unrecognized button.", None

        if cb_token.used_at is not None:
            return False, "This button has already been used.", None

        expires_at = cb_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if now > expires_at:
            cb_token.used_at = now
            self.db.commit()
            return False, "This approval request has expired.", None

        approval = self.db.execute(
            select(Approval).where(Approval.id == cb_token.approval_id)
        ).scalar_one_or_none()

        if not approval:
            return False, "Associated approval record not found.", None

        app_expires = approval.expires_at
        if app_expires.tzinfo is None:
            app_expires = app_expires.replace(tzinfo=UTC)

        if now > app_expires:
            approval.decision = "expired"
            cb_token.used_at = now
            self.db.commit()
            return False, "This approval request has expired.", approval

        if approval.decision != "pending":
            cb_token.used_at = now
            self.db.commit()
            return False, f"Approval has already been resolved as '{approval.decision}'.", approval

        is_approved = cb_token.purpose == "approve"
        approval.decision = "approved" if is_approved else "rejected"
        approval.decided_at = now
        approval.decided_by_telegram_id = owner_telegram_id
        cb_token.used_at = now

        self.db.add(
            AuditLog(
                actor="owner",
                event=f"draft_{approval.decision}",
                entity_type="approval",
                entity_id=approval.id,
                outcome="success",
                details={"draft_id": approval.draft_id, "token_used": token_str},
            )
        )
        self.db.commit()
        self.db.refresh(approval)

        decision_word = "approved ✅" if is_approved else "rejected ❌"
        msg = f"Draft [{approval.draft.code}] has been {decision_word}."
        return True, msg, approval

    def validate_for_publish(
        self,
        approval_id: str,
        current_text: str,
        kill_switch: bool = False,
    ) -> tuple[bool, str]:
        """Strict validation before any publish attempt (SEC-013 list).

        Checks:
        1. Kill switch / paused mode.
        2. Approval exists and decision == 'approved'.
        3. Approval single-use check (used_at IS NULL).
        4. Approval expiration check (now <= expires_at).
        5. Exact text content hash match (content_hash == hash(current_text)).
        """
        now = datetime.now(UTC)

        # Check 1: Kill switch and pause state
        if kill_switch:
            return False, "Publishing blocked: Kill switch is active."

        cfg = self.db.execute(
            select(OwnerSettings).where(OwnerSettings.id == 1)
        ).scalar_one_or_none()
        if cfg and cfg.paused:
            return False, "Publishing blocked: Bot is currently paused."

        # Check 2: Approval existence
        approval = self.db.execute(
            select(Approval).where(Approval.id == approval_id)
        ).scalar_one_or_none()
        if not approval:
            return False, "Publishing blocked: Approval record not found."

        # Check 3: Expiration check
        app_expires = approval.expires_at
        if app_expires.tzinfo is None:
            app_expires = app_expires.replace(tzinfo=UTC)

        if now > app_expires:
            approval.decision = "expired"
            self.db.commit()
            return False, "Publishing blocked: Approval has expired."

        # Check 4: Must be in 'approved' status
        if approval.decision != "approved":
            return (
                False,
                f"Publishing blocked: Approval status is '{approval.decision}', not 'approved'.",
            )

        # Check 5: Single-use check (FR-017)
        if approval.used_at is not None:
            return False, "Publishing blocked: Approval has already been used."

        # Check 6: Exact-text content hash match (SEC-013)
        candidate_hash = compute_text_hash(current_text)
        if candidate_hash != approval.content_hash:
            return False, "Publishing blocked: Text was modified after approval was granted."

        # All checks passed: mark approval used
        approval.used_at = now
        self.db.add(
            AuditLog(
                actor="system",
                event="approval_consumed",
                entity_type="approval",
                entity_id=approval.id,
                outcome="success",
                details={"content_hash": candidate_hash},
            )
        )
        self.db.commit()
        return True, "Approval validated and consumed."

    def pause_bot(self, owner_telegram_id: int) -> None:
        """Pause all external actions (FR-027)."""
        cfg = self._get_or_create_owner_settings(owner_telegram_id)
        cfg.paused = True
        self.db.add(
            AuditLog(
                actor="owner",
                event="bot_paused",
                entity_type="settings",
                entity_id="1",
                outcome="success",
            )
        )
        self.db.commit()

    def resume_bot(self, owner_telegram_id: int) -> None:
        """Resume external actions (FR-027)."""
        cfg = self._get_or_create_owner_settings(owner_telegram_id)
        cfg.paused = False
        self.db.add(
            AuditLog(
                actor="owner",
                event="bot_resumed",
                entity_type="settings",
                entity_id="1",
                outcome="success",
            )
        )
        self.db.commit()

    def get_status_overview(self, owner_telegram_id: int, kill_switch: bool = False) -> str:
        """Generate status overview text for /status command."""
        cfg = self._get_or_create_owner_settings(owner_telegram_id)
        pending_count = len(
            self.db.execute(select(Approval).where(Approval.decision == "pending")).scalars().all()
        )
        drafts_count = len(self.db.execute(select(Draft)).scalars().all())

        state_icon = "⏸️ PAUSED" if cfg.paused else "▶️ ACTIVE"
        kill_icon = "🛑 ACTIVE" if kill_switch else "OFF"
        pub_icon = "ENABLED" if cfg.publishing_enabled else "DISABLED (drafts only)"

        return (
            f"🤖 Bot Status Overview:\n\n"
            f"State: {state_icon}\n"
            f"Publishing: {pub_icon}\n"
            f"Kill Switch: {kill_icon}\n"
            f"Briefing Time: {cfg.briefing_time} ({cfg.timezone})\n"
            f"Briefing Enabled: {'Yes' if cfg.briefing_enabled else 'No'}\n\n"
            f"📊 Statistics:\n"
            f"• Total drafts created: {drafts_count}\n"
            f"• Pending approvals: {pending_count}\n"
        )
