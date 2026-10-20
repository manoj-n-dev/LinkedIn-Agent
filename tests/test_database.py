"""Tests for Database Schema, Constraints, and Migrations (T-DB-01, T-DB-02)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from src.db.models import (
    Approval,
    Base,
    Briefing,
    BriefingItem,
    Draft,
    JobRun,
    PublishAttempt,
)


@pytest.fixture
def db_session(tmp_path):
    """Provide a clean SQLite database session with all tables created."""
    db_file = tmp_path / "test_constraints.db"
    engine = create_engine(f"sqlite:///{db_file}")

    # Enable foreign keys and check constraints on SQLite connection
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")

    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    yield session
    session.close()
    engine.dispose()


def test_t_db_01_duplicate_job_slot_prevented(db_session):
    """T-DB-01: UNIQUE(job_name, slot) prevents duplicate job executions (FR-021)."""
    slot_time = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)
    job1 = JobRun(
        job_name="daily_briefing",
        slot=slot_time,
        status="running",
    )
    db_session.add(job1)
    db_session.commit()

    # Second job attempting to insert the exact same slot must be rejected
    job2 = JobRun(
        job_name="daily_briefing",
        slot=slot_time,
        status="running",
    )
    db_session.add(job2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_t_db_01_approval_used_at_requires_approved_decision(db_session):
    """T-DB-01: CHECK constraint requires decision='approved' before used_at is populated."""
    draft = Draft(
        code="D-TEST1",
        kind="post",
        version=1,
        body="Sample text",
        content_hash="abc123hash",
        status="pending_approval",
    )
    db_session.add(draft)
    db_session.commit()

    # Case A: pending approval cannot have used_at
    invalid_approval = Approval(
        draft_id=draft.id,
        action_type="publish_post",
        content_hash="abc123hash",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        decision="pending",
        used_at=datetime.now(UTC),  # Invalid!
    )
    db_session.add(invalid_approval)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Case B: rejected approval cannot have used_at
    rejected_approval = Approval(
        draft_id=draft.id,
        action_type="publish_post",
        content_hash="abc123hash",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        decision="rejected",
        used_at=datetime.now(UTC),  # Invalid!
    )
    db_session.add(rejected_approval)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Case C: approved decision can have used_at
    valid_approval = Approval(
        draft_id=draft.id,
        action_type="publish_post",
        content_hash="abc123hash",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        decision="approved",
        used_at=datetime.now(UTC),
    )
    db_session.add(valid_approval)
    db_session.commit()
    assert valid_approval.used_at is not None


def test_t_db_01_single_publish_attempt_per_approval(db_session):
    """T-DB-01: UNIQUE(approval_id) in publish_attempts prevents duplicate publication."""
    draft = Draft(
        code="D-TEST2",
        kind="post",
        version=1,
        body="Post text",
        content_hash="hash456",
        status="approved",
    )
    db_session.add(draft)
    db_session.commit()

    approval = Approval(
        draft_id=draft.id,
        action_type="publish_post",
        content_hash="hash456",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        decision="approved",
    )
    db_session.add(approval)
    db_session.commit()

    # First attempt
    attempt1 = PublishAttempt(
        draft_id=draft.id,
        approval_id=approval.id,
        idempotency_key="attempt-key-1",
        outcome="started",
    )
    db_session.add(attempt1)
    db_session.commit()

    # Second attempt referencing same approval must fail
    attempt2 = PublishAttempt(
        draft_id=draft.id,
        approval_id=approval.id,
        idempotency_key="attempt-key-2",
        outcome="started",
    )
    db_session.add(attempt2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_t_db_01_unique_draft_version(db_session):
    """T-DB-01: Enforces unique version numbers per parent draft."""
    parent_draft = Draft(
        code="D-PARENT",
        kind="post",
        version=1,
        body="Version 1",
        content_hash="hash_v1",
        status="draft",
    )
    db_session.add(parent_draft)
    db_session.commit()

    child_v2 = Draft(
        code="D-CHILD1",
        kind="post",
        parent_id=parent_draft.id,
        version=2,
        body="Version 2",
        content_hash="hash_v2",
        status="draft",
    )
    db_session.add(child_v2)
    db_session.commit()

    # Attempting duplicate version 2 under same parent must fail
    duplicate_child_v2 = Draft(
        code="D-CHILD2",
        kind="post",
        parent_id=parent_draft.id,
        version=2,
        body="Duplicate Version 2",
        content_hash="hash_v2_dup",
        status="draft",
    )
    db_session.add(duplicate_child_v2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_briefing_items_separate_fact_and_interpretation(db_session):
    """FR-010, CR-01: Briefing items must store fact and interpretation in separate columns."""
    briefing = Briefing(
        run_date=date(2026, 10, 20),
        status="ready",
    )
    db_session.add(briefing)
    db_session.commit()

    item = BriefingItem(
        briefing_id=briefing.id,
        position=1,
        title="Python 3.12 release update",
        url="https://example.com/news",
        source_name="Example News",
        fact_text="Python 3.12 has improved performance.",
        interpretation_text="This speeds up backend API processing.",
    )
    db_session.add(item)
    db_session.commit()

    saved = db_session.scalar(select(BriefingItem).where(BriefingItem.id == item.id))
    assert saved.fact_text == "Python 3.12 has improved performance."
    assert saved.interpretation_text == "This speeds up backend API processing."


def test_t_db_02_alembic_upgrade_and_downgrade(tmp_path):
    """T-DB-02: Alembic migrations up and down execute cleanly without error."""
    test_db_path = tmp_path / "migration_test.db"
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{test_db_path}")

    # Run upgrade to head
    command.upgrade(alembic_cfg, "head")

    # Run downgrade back to base
    command.downgrade(alembic_cfg, "base")

    # Re-run upgrade to head to ensure re-applicability
    command.upgrade(alembic_cfg, "head")
