"""Tests for periodic scheduler, slot uniqueness, briefing timing, and maintenance.

Covers FR-011, FR-021.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.config import Settings
from src.db.models import Approval, Briefing, JobRun, LinkedInConnection, OwnerSettings, SeenItem
from src.db.session import Base, get_session_factory
from src.scheduler.tick import (
    calculate_slot,
    check_token_warning,
    claim_job_slot,
    execute_tick,
    is_briefing_due,
    run_maintenance,
)


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
        timezone="Asia/Kolkata",
    )


# --- Slot Calculation and Uniqueness Tests ---


def test_calculate_slot_rounds_down_to_15_minutes():
    """Slot time must round down to nearest 15-minute boundary."""
    dt1 = datetime(2026, 10, 21, 8, 14, 59, 999999, tzinfo=UTC)
    assert calculate_slot(dt1, 15) == datetime(2026, 10, 21, 8, 0, 0, tzinfo=UTC)

    dt2 = datetime(2026, 10, 21, 8, 15, 0, 0, tzinfo=UTC)
    assert calculate_slot(dt2, 15) == datetime(2026, 10, 21, 8, 15, 0, tzinfo=UTC)

    dt3 = datetime(2026, 10, 21, 8, 44, 30, tzinfo=UTC)
    assert calculate_slot(dt3, 15) == datetime(2026, 10, 21, 8, 30, 0, tzinfo=UTC)


def test_claim_job_slot_prevents_duplicate_runs(db_session: Session):
    """FR-021: Unique constraint on (job_name, slot) prevents duplicate execution."""
    slot = datetime(2026, 10, 21, 8, 0, 0, tzinfo=UTC)

    # First claim succeeds
    job1 = claim_job_slot(db_session, "tick", slot)
    assert job1 is not None
    assert job1.status == "running"

    # Second claim for identical slot returns None
    job2 = claim_job_slot(db_session, "tick", slot)
    assert job2 is None

    # Different slot succeeds
    different_slot = datetime(2026, 10, 21, 8, 15, 0, tzinfo=UTC)
    job3 = claim_job_slot(db_session, "tick", different_slot)
    assert job3 is not None


# --- Timezone and Timing Tests ---


def test_is_briefing_due_timezone_conversion(db_session: Session):
    """FR-011: Timezone conversion from UTC to Asia/Kolkata (UTC+5:30) for 08:00 delivery."""
    # 02:15 UTC = 07:45 IST (before 08:00)
    utc_early = datetime(2026, 10, 21, 2, 15, 0, tzinfo=UTC)
    due_early, run_date = is_briefing_due(
        db_session, utc_early, default_tz="Asia/Kolkata", default_time="08:00"
    )
    assert not due_early
    assert run_date == datetime(2026, 10, 21, 7, 45, tzinfo=ZoneInfo("Asia/Kolkata")).date()

    # 02:30 UTC = 08:00 IST (exactly scheduled time)
    utc_on_time = datetime(2026, 10, 21, 2, 30, 0, tzinfo=UTC)
    due_on_time, run_date = is_briefing_due(
        db_session, utc_on_time, default_tz="Asia/Kolkata", default_time="08:00"
    )
    assert due_on_time
    assert run_date == datetime(2026, 10, 21, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata")).date()

    # Mark briefing as sent for today
    briefing = Briefing(
        run_date=run_date,
        status="sent",
        sent_at=utc_on_time,
    )
    db_session.add(briefing)
    db_session.commit()

    # Once sent, should no longer be due on same day
    utc_later = datetime(2026, 10, 21, 3, 0, 0, tzinfo=UTC)
    due_later, _ = is_briefing_due(
        db_session, utc_later, default_tz="Asia/Kolkata", default_time="08:00"
    )
    assert not due_later


def test_is_briefing_due_respects_pause(db_session: Session):
    """FR-011: Paused setting stops scheduled briefing."""
    owner_settings = OwnerSettings(
        id=1,
        owner_telegram_id=987654321,
        timezone="Asia/Kolkata",
        briefing_time="08:00",
        briefing_enabled=True,
        paused=True,
    )
    db_session.add(owner_settings)
    db_session.commit()

    utc_on_time = datetime(2026, 10, 21, 2, 30, 0, tzinfo=UTC)
    due, _ = is_briefing_due(db_session, utc_on_time)
    assert not due


# --- Maintenance and Cleanup Tests ---


def test_run_maintenance_prunes_seen_items_and_expires_approvals(db_session: Session):
    """Periodic maintenance prunes seen items > 90 days and expires stale approvals."""
    now = datetime(2026, 10, 21, 10, 0, 0, tzinfo=UTC)

    # 1. Seen items: one fresh, one 95 days old
    fresh_item = SeenItem(url_hash="fresh123", first_seen_at=now - timedelta(days=10))
    old_item = SeenItem(url_hash="old12345", first_seen_at=now - timedelta(days=95))
    db_session.add_all([fresh_item, old_item])

    # 2. Approvals: one future, one expired
    active_approval = Approval(
        draft_id="d1",
        action_type="post",
        content_hash="h1",
        decision="pending",
        expires_at=now + timedelta(minutes=15),
    )
    stale_approval = Approval(
        draft_id="d2",
        action_type="post",
        content_hash="h2",
        decision="pending",
        expires_at=now - timedelta(minutes=10),
    )
    db_session.add_all([active_approval, stale_approval])
    db_session.commit()

    stats = run_maintenance(db_session, now)
    assert stats["pruned_urls"] == 1
    assert stats["expired_approvals"] == 1

    # Verify old item was removed and fresh item kept
    remaining_hashes = db_session.execute(select(SeenItem.url_hash)).scalars().all()
    assert "fresh123" in remaining_hashes
    assert "old12345" not in remaining_hashes

    # Verify stale approval expired
    db_session.refresh(active_approval)
    db_session.refresh(stale_approval)
    assert active_approval.decision == "pending"
    assert stale_approval.decision == "expired"


# --- Token Expiration Warning Tests ---


@pytest.mark.asyncio
async def test_check_token_warning_alerts_within_7_days(db_session: Session):
    """Scheduler alerts owner if LinkedIn token expires in <= 7 days."""
    now = datetime(2026, 10, 21, 10, 0, 0, tzinfo=UTC)
    conn = LinkedInConnection(
        id=1,
        access_token_enc=b"enc_token",
        expires_at=now + timedelta(days=5),
        status="active",
        last_warning_days=None,
    )
    db_session.add(conn)
    db_session.commit()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    await check_token_warning(db_session, now, mock_bot, owner_id=12345)
    mock_bot.send_message.assert_awaited_once()
    assert "5 days" in mock_bot.send_message.call_args[1]["text"]

    db_session.refresh(conn)
    assert conn.last_warning_days == 5


# --- Full Tick Execution Tests ---


@pytest.mark.asyncio
async def test_execute_tick_full_cycle(db_session: Session, fake_settings, monkeypatch):
    """FR-011, FR-021: Full tick cycle claims slot, delivers due briefing, and finishes."""
    mock_briefing = Briefing(
        run_date=datetime(2026, 10, 21).date(),
        status="ready",
    )
    formatted_msg = "📰 Daily Briefing — 2026-10-21\n1. Tech News\n📌 Fact: Something happened."

    async def mock_gen_briefing(*args, **kwargs):
        return mock_briefing, formatted_msg

    monkeypatch.setattr(
        "src.scheduler.tick.BriefingService.generate_daily_briefing",
        mock_gen_briefing,
    )

    now_due = datetime(2026, 10, 21, 2, 30, 0, tzinfo=UTC)  # 08:00 IST
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    # 1. Execute tick for slot
    success = await execute_tick(db_session, fake_settings, bot=mock_bot, now_utc=now_due)
    assert success

    # Verify Telegram delivery
    mock_bot.send_message.assert_awaited_once_with(
        chat_id=fake_settings.owner_telegram_id,
        text=formatted_msg,
    )

    # Verify slot marked finished
    slot = calculate_slot(now_due)
    job = db_session.execute(select(JobRun).where(JobRun.slot == slot)).scalar_one()
    assert job.status == "finished"

    # 2. Second tick run with same slot fails to re-claim (FR-021)
    second_success = await execute_tick(db_session, fake_settings, bot=mock_bot, now_utc=now_due)
    assert not second_success
