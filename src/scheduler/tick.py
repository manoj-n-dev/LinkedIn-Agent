"""Periodic scheduler tick execution (FR-011, FR-021).

Rounds UTC time to 15-minute slot boundary, enforces single execution via
UNIQUE(job_name, slot) constraint in job_runs, checks briefing delivery,
and performs daily maintenance tasks.
"""

import asyncio
import logging
import sys
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from telegram import Bot

from src.config import Settings, load_settings
from src.db.models import Approval, Briefing, JobRun, LinkedInConnection, OwnerSettings
from src.db.session import create_db_engine, get_session_factory
from src.research.dedup import prune_old_seen_items
from src.services.briefing_service import BriefingService

logger = logging.getLogger(__name__)

DEFAULT_SLOT_MINUTES = 15


def calculate_slot(dt: datetime, slot_minutes: int = DEFAULT_SLOT_MINUTES) -> datetime:
    """Round a timezone-aware UTC datetime down to the nearest slot boundary."""
    discard = timedelta(
        minutes=dt.minute % slot_minutes,
        seconds=dt.second,
        microseconds=dt.microsecond,
    )
    return dt - discard


def claim_job_slot(db: Session, job_name: str, slot: datetime) -> JobRun | None:
    """Attempt to claim a unique execution slot (FR-021).

    Returns the JobRun record if claimed, or None if already claimed/executed.
    """
    job_run = JobRun(
        job_name=job_name,
        slot=slot,
        status="running",
    )
    try:
        db.add(job_run)
        db.commit()
        db.refresh(job_run)
        return job_run
    except IntegrityError:
        db.rollback()
        logger.info("Slot %s for job '%s' already claimed. Skipping.", slot, job_name)
        return None


def is_briefing_due(
    db: Session,
    now_utc: datetime,
    default_tz: str = "Asia/Kolkata",
    default_time: str = "08:00",
) -> tuple[bool, date]:
    """Check if owner's daily briefing is due and has not yet been sent (FR-011)."""
    # 1. Read owner preferences from database if configured
    owner_cfg = db.execute(select(OwnerSettings).where(OwnerSettings.id == 1)).scalar_one_or_none()

    if owner_cfg:
        if not owner_cfg.briefing_enabled or owner_cfg.paused:
            return False, now_utc.date()
        target_tz = owner_cfg.timezone
        target_time_str = owner_cfg.briefing_time
    else:
        target_tz = default_tz
        target_time_str = default_time

    # 2. Convert UTC to owner's local timezone
    try:
        local_tz = ZoneInfo(target_tz)
    except Exception:
        local_tz = ZoneInfo("Asia/Kolkata")

    local_dt = now_utc.astimezone(local_tz)
    local_date = local_dt.date()

    # 3. Parse scheduled hour and minute
    try:
        parts = target_time_str.split(":")
        target_hour, target_min = int(parts[0]), int(parts[1])
    except Exception:
        target_hour, target_min = 8, 0

    # If current local time is before the briefing time, not due yet
    if (local_dt.hour, local_dt.minute) < (target_hour, target_min):
        return False, local_date

    # 4. Check if today's briefing has already been sent
    already_sent = db.execute(
        select(Briefing.id).where(
            Briefing.run_date == local_date,
            Briefing.status == "sent",
        )
    ).scalar_one_or_none()

    if already_sent:
        return False, local_date

    return True, local_date


def run_maintenance(db: Session, now_utc: datetime) -> dict[str, int]:
    """Perform routine system maintenance: prune old seen URLs, expire pending approvals."""
    # 1. Prune seen items older than 90 days
    pruned_urls = prune_old_seen_items(db, retention_days=90)

    # 2. Expire old pending approvals that have exceeded their expires_at
    result = db.execute(
        update(Approval)
        .where(
            Approval.decision == "pending",
            Approval.expires_at < now_utc,
        )
        .values(decision="expired")
    )
    expired_approvals = result.rowcount or 0
    db.commit()

    return {
        "pruned_urls": pruned_urls,
        "expired_approvals": expired_approvals,
    }


async def check_token_warning(
    db: Session, now_utc: datetime, bot: Any | None, owner_id: int
) -> None:
    """Send alert if LinkedIn token expires within 7 days."""
    conn = db.execute(
        select(LinkedInConnection).where(LinkedInConnection.id == 1)
    ).scalar_one_or_none()
    if not conn or conn.status != "active":
        return

    expires_at = conn.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    current_utc = now_utc if now_utc.tzinfo is not None else now_utc.replace(tzinfo=UTC)

    days_left = (expires_at - current_utc).days
    if days_left <= 7 and (conn.last_warning_days is None or conn.last_warning_days > days_left):
        conn.last_warning_days = days_left
        db.commit()
        if bot:
            msg = (
                f"⚠️ Your LinkedIn access token will expire in {days_left} days.\n"
                "Use /connect to re-authenticate."
            )
            try:
                await bot.send_message(chat_id=owner_id, text=msg)
            except Exception as exc:
                logger.warning("Failed sending token warning: %s", exc)


async def execute_tick(
    db: Session,
    settings: Settings,
    bot: Any | None = None,
    now_utc: datetime | None = None,
) -> bool:
    """Execute a single scheduler tick (FR-011, FR-021)."""
    now = now_utc or datetime.now(UTC)
    slot = calculate_slot(now)

    job_run = claim_job_slot(db, "tick", slot)
    if job_run is None:
        return False

    logger.info("Executing tick for slot %s", slot)
    try:
        # 1. Maintenance
        run_maintenance(db, now)

        # 2. Check token expiration
        await check_token_warning(db, now, bot, settings.owner_telegram_id)

        # 3. Check and deliver daily briefing
        due, briefing_date = is_briefing_due(db, now, default_tz=settings.timezone)
        if due:
            logger.info("Daily briefing is due for %s", briefing_date)
            service = BriefingService(
                db=db,
                api_key=settings.groq_api_key,
                model=settings.groq_model,
            )
            briefing, formatted_msg = await service.generate_daily_briefing(run_date=briefing_date)

            if briefing:
                # Deliver to owner via Telegram
                if bot:
                    if len(formatted_msg) > 4000:
                        chunks = [
                            formatted_msg[i : i + 4000] for i in range(0, len(formatted_msg), 4000)
                        ]
                        for chunk in chunks:
                            await bot.send_message(chat_id=settings.owner_telegram_id, text=chunk)
                    else:
                        await bot.send_message(
                            chat_id=settings.owner_telegram_id, text=formatted_msg
                        )

                briefing.sent_at = datetime.now(UTC)
                briefing.status = "sent"
                db.commit()
                logger.info("Daily briefing for %s delivered successfully.", briefing_date)

        job_run.status = "finished"
        job_run.finished_at = datetime.now(UTC)
        db.commit()
        return True

    except Exception as exc:
        logger.error("Error during tick execution: %s", exc, exc_info=True)
        job_run.status = "failed"
        job_run.error_summary = str(exc)[:255]
        job_run.finished_at = datetime.now(UTC)
        db.commit()
        return False


async def main() -> None:
    """CLI entry point for running the scheduler tick (from cron or GitHub Actions)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    settings = load_settings()
    engine = create_db_engine(settings.database_url)
    session_factory = get_session_factory(engine)

    bot = Bot(token=settings.telegram_bot_token)
    with session_factory() as db:
        success = await execute_tick(db, settings, bot=bot)
        if not success:
            sys.exit(0)  # Graceful exit if slot was already claimed


if __name__ == "__main__":
    asyncio.run(main())
