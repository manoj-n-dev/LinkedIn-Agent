"""SQLAlchemy ORM models implementing the database schema from docs/05.

All 17 tables and integrity constraints:
- Single-owner constraints (id=1)
- Single-use approval constraints (used_at IS NULL OR decision = 'approved')
- Duplicate job prevention UNIQUE(job_name, slot)
- One publish attempt per approval UNIQUE(approval_id)
- Distinct fact and interpretation columns for briefings
- Encrypted access token storage
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.session import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(UTC)


def generate_uuid() -> str:
    """Generate a standard UUID string."""
    return str(uuid.uuid4())


BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class OwnerSettings(Base):
    """Owner configuration and preferences (single row id=1)."""

    __tablename__ = "owner_settings"
    __table_args__ = (CheckConstraint("id = 1", name="single_row_owner_settings"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    owner_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="Asia/Kolkata")
    briefing_time: Mapped[str] = mapped_column(Text, nullable=False, default="08:00")
    briefing_enabled: Mapped[bool] = mapped_column(default=True)
    topics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tone: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(Text, default="English")
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    paused: Mapped[bool] = mapped_column(default=False, nullable=False)
    publishing_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    scheduling_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    ai_fallback_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class LinkedInConnection(Base):
    """Stored LinkedIn credentials and status (single row id=1, token encrypted)."""

    __tablename__ = "linkedin_connection"
    __table_args__ = (CheckConstraint("id = 1", name="single_row_linkedin_connection"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    member_urn: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    last_warning_days: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)


class OAuthState(Base):
    """One-time state parameter for LinkedIn OAuth."""

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Source(Base):
    """Configured news and research sources."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # 'rss' or 'hn'
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)


class SeenItem(Base):
    """Deduplication tracker for processed article URLs."""

    __tablename__ = "seen_items"

    url_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Draft(Base):
    """Post, comment, and connection-note drafts with version tracking."""

    __tablename__ = "drafts"
    __table_args__ = (UniqueConstraint("parent_id", "version", name="unique_draft_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # post / comment / connection_note
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("drafts.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    idea: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    visibility: Mapped[str] = mapped_column(Text, default="PUBLIC")
    context_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # Deleted after 7 days
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="draft")


class Approval(Base):
    """Approval decision bound to an exact content hash and expiry."""

    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('pending', 'approved', 'rejected', 'expired')",
            name="valid_approval_decision",
        ),
        CheckConstraint(
            "used_at IS NULL OR decision = 'approved'",
            name="approval_must_be_approved_before_use",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("drafts.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)  # publish_post / schedule_post
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    draft: Mapped["Draft"] = relationship("Draft", back_populates="approvals")


class ScheduledAction(Base):
    """Scheduled publish queue entry."""

    __tablename__ = "scheduled_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("drafts.id"), nullable=False)
    approval_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("approvals.id"), unique=True, nullable=False
    )
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="scheduled")
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PublishAttempt(Base):
    """Record of an outbound publication attempt to LinkedIn."""

    __tablename__ = "publish_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("drafts.id"), nullable=False)
    approval_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("approvals.id"), unique=True, nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # outcome: started / success / failed / unknown
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_post_id: Mapped[str | None] = mapped_column(Text, nullable=True)


class Briefing(Base):
    """Daily briefing record."""

    __tablename__ = "briefings"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    run_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    # status: building / ready / sent / failed / partial
    status: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    telegram_message_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["BriefingItem"]] = relationship("BriefingItem", back_populates="briefing")


class BriefingItem(Base):
    """Individual item in a daily briefing with facts and interpretation kept distinct."""

    __tablename__ = "briefing_items"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    briefing_id: Mapped[int] = mapped_column(BigIntPK, ForeignKey("briefings.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_name: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fact_text: Mapped[str] = mapped_column(Text, nullable=False)
    interpretation_text: Mapped[str] = mapped_column(Text, nullable=False)

    briefing: Mapped["Briefing"] = relationship("Briefing", back_populates="items")


class JobRun(Base):
    """Record of an external scheduled tick execution; unique slot prevents duplicate runs."""

    __tablename__ = "job_runs"
    __table_args__ = (UniqueConstraint("job_name", "slot", name="job_slot_once"),)

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(Text, nullable=False)
    slot: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class TelegramUpdate(Base):
    """Processed update IDs for idempotent webhook retry handling."""

    __tablename__ = "telegram_updates"

    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CallbackToken(Base):
    """One-time button tokens for Telegram inline keyboards."""

    __tablename__ = "callback_tokens"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    draft_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    """Append-only audit trail for decisions and external actions (SEC-016, FR-023)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)  # owner / system / ai
    event: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AICall(Base):
    """Usage log for AI API requests to track quota."""

    __tablename__ = "ai_calls"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)


class UnauthorizedAttempt(Base):
    """Counter record for stranger interactions storing only a hashed ID."""

    __tablename__ = "unauthorized_attempts"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    id_hash: Mapped[str] = mapped_column(String(64), nullable=False)
