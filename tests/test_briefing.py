"""Tests for research collection, SSRF protection, deduplication, and daily briefing.

Covers FR-008, FR-010, FR-012, SEC-006, SEC-020.
"""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from telegram import Chat, Message, Update, User

from src.ai.groq_client import GROQ_API_URL
from src.config import Settings
from src.db.models import BriefingItem
from src.db.session import Base, get_session_factory
from src.research.dedup import canonicalize_url, compute_url_hash, is_url_seen, mark_url_seen
from src.research.fetcher import (
    ResponseTooLargeError,
    SSRFBlockedError,
    safe_fetch,
    validate_target_url,
)
from src.research.hn_client import HN_ITEM_URL_TEMPLATE, HN_TOP_STORIES_URL, fetch_hn_top_stories
from src.research.rss_client import fetch_rss_feed
from src.services.briefing_service import BriefingService, sanitize_briefing_text
from src.telegram_bot.research_handlers import report_command


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
        owner_display_name="Manoj",
    )


# --- SSRF and Outbound Protection Tests ---


def test_ssrf_blocks_private_and_local_ips():
    """SEC-020, FR-030: Reject localhost, private subnets, and cloud metadata."""
    forbidden_urls = [
        "http://localhost:8000/feed.xml",
        "http://127.0.0.1:8080/feed",
        "http://10.0.0.5/rss",
        "http://172.16.0.1/atom",
        "http://192.168.1.1/news",
        "http://169.254.169.254/latest/meta-data/",
    ]
    for url in forbidden_urls:
        with pytest.raises(SSRFBlockedError):
            validate_target_url(url)


def test_ssrf_blocks_linkedin_scraping():
    """SEC-006: Any fetch targeting linkedin.com must be blocked."""
    with pytest.raises(SSRFBlockedError) as exc_info:
        validate_target_url("https://www.linkedin.com/feed")
    assert "linkedin.com is prohibited" in str(exc_info.value)


def test_ssrf_blocks_non_http_schemes():
    """FR-009: Only HTTP and HTTPS are permitted."""
    with pytest.raises(SSRFBlockedError):
        validate_target_url("ftp://example.com/feed.xml")
    with pytest.raises(SSRFBlockedError):
        validate_target_url("file:///etc/passwd")


@pytest.mark.asyncio
async def test_fetcher_blocks_oversized_response():
    """FR-009: Response size exceeding 1 MB is rejected."""
    huge_body = "x" * (1024 * 1024 + 100)
    with respx.mock() as respx_mock:
        respx_mock.get("https://example.com/big_feed.xml").respond(
            200, text=huge_body, headers={"Content-Length": str(len(huge_body))}
        )
        async with httpx.AsyncClient() as client:
            with pytest.raises(ResponseTooLargeError):
                await safe_fetch("https://example.com/big_feed.xml", client=client)


# --- Deduplication Tests ---


def test_url_canonicalization_and_dedup(db_session: Session):
    """FR-012: URL canonicalization strips tracking tags and computes SHA-256."""
    url1 = "https://example.com/post?utm_source=twitter&utm_medium=social"
    url2 = "https://example.com/post"

    assert canonicalize_url(url1) == canonicalize_url(url2)
    assert compute_url_hash(url1) == compute_url_hash(url2)

    assert not is_url_seen(db_session, url1)
    mark_url_seen(db_session, url1)
    db_session.commit()

    assert is_url_seen(db_session, url1)
    assert is_url_seen(db_session, url2)


# --- Source Client Tests ---


@pytest.mark.asyncio
async def test_fetch_hn_top_stories():
    """FR-008: Fetch top stories from Hacker News Firebase API."""
    with respx.mock() as respx_mock:
        respx_mock.get(HN_TOP_STORIES_URL).respond(200, json=[1001, 1002])
        respx_mock.get(HN_ITEM_URL_TEMPLATE.format(item_id=1001)).respond(
            200,
            json={
                "id": 1001,
                "type": "story",
                "title": "Python 3.14 Released",
                "url": "https://python.org/release-3-14",
                "score": 250,
                "by": "guido",
                "time": 1729400000,
            },
        )
        respx_mock.get(HN_ITEM_URL_TEMPLATE.format(item_id=1002)).respond(
            200,
            json={
                "id": 1002,
                "type": "story",
                "title": "Ask HN: What are you building?",
                "score": 50,
                "time": 1729400010,
            },
        )

        async with httpx.AsyncClient() as client:
            items = await fetch_hn_top_stories(limit=2, client=client)

        assert len(items) == 2
        assert items[0].title == "Python 3.14 Released"
        assert items[0].url == "https://python.org/release-3-14"
        assert items[0].source_name == "Hacker News"


@pytest.mark.asyncio
async def test_fetch_rss_feed():
    """FR-008: Fetch and parse RSS feed."""
    sample_xml = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>Python News</title>
        <item>
          <title>&lt;b&gt;Asyncio Best Practices&lt;/b&gt;</title>
          <link>https://example.com/asyncio-guide</link>
          <description>Learn how to use &lt;i&gt;asyncio&lt;/i&gt; cleanly.</description>
        </item>
      </channel>
    </rss>"""

    with respx.mock() as respx_mock:
        respx_mock.get("https://example.com/rss.xml").respond(200, text=sample_xml)
        async with httpx.AsyncClient() as client:
            items = await fetch_rss_feed(
                "https://example.com/rss.xml", "Example Blog", client=client
            )

        assert len(items) == 1
        assert items[0].title == "Asyncio Best Practices"
        assert items[0].url == "https://example.com/asyncio-guide"
        assert "Learn how to use asyncio cleanly." in items[0].summary


# --- Briefing Service Tests ---


def test_cr_12_sanitizes_trending_on_linkedin():
    """CR-12: The phrase 'trending on LinkedIn' must never appear."""
    text = "Here is what is trending on LinkedIn right now."
    sanitized = sanitize_briefing_text(text)
    assert "trending on LinkedIn" not in sanitized.lower()
    assert "emerging in tech" in sanitized


@pytest.mark.asyncio
async def test_briefing_service_full_flow(db_session: Session, fake_settings):
    """FR-008, FR-010, CR-01: Briefing stores distinct fact and interpretation."""
    service = BriefingService(
        db=db_session,
        api_key=fake_settings.groq_api_key,
        model=fake_settings.groq_model,
    )

    ai_response = """ITEM: 1
FACT: Python 3.14 improves interpreter speed by 15%.
INTERPRETATION: Teams running high-throughput backend services can see lower cloud costs.

SUGGESTIONS:
- Share how performance gains affect microservices.
- Ask followers what Python version they are using in production."""

    with respx.mock() as respx_mock:
        # Mock HN
        respx_mock.get(HN_TOP_STORIES_URL).respond(200, json=[5001])
        respx_mock.get(HN_ITEM_URL_TEMPLATE.format(item_id=5001)).respond(
            200,
            json={
                "id": 5001,
                "type": "story",
                "title": "Python 3.14 Benchmarks",
                "url": "https://example.com/benchmarks",
                "score": 300,
            },
        )
        # Mock RSS
        for _, url in [
            ("Python Insider", "https://feeds.feedburner.com/PythonInsider"),
            ("ArXiv CS AI", "https://export.arxiv.org/rss/cs.AI"),
        ]:
            respx_mock.get(url).respond(200, text="<rss><channel></channel></rss>")

        # Mock Groq
        respx_mock.post(GROQ_API_URL).respond(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": ai_response}}]},
        )

        async with httpx.AsyncClient() as client:
            briefing, formatted_text = await service.generate_daily_briefing(client=client)

    assert briefing is not None
    assert briefing.status == "ready"
    assert "📌 Fact: Python 3.14 improves interpreter speed by 15%." in formatted_text
    assert "💡 Why it matters: Teams running high-throughput backend services" in formatted_text
    assert "trending on LinkedIn" not in formatted_text.lower()

    # Verify persisted in database
    db_items = (
        db_session.execute(select(BriefingItem).where(BriefingItem.briefing_id == briefing.id))
        .scalars()
        .all()
    )
    assert len(db_items) >= 1
    assert db_items[0].fact_text == "Python 3.14 improves interpreter speed by 15%."
    assert "Teams running high-throughput" in db_items[0].interpretation_text

    # Verify URL was marked as seen
    assert is_url_seen(db_session, "https://example.com/benchmarks")


@pytest.mark.asyncio
async def test_briefing_fallback_when_ai_offline(db_session: Session, fake_settings):
    """FR-022: When AI service is unavailable, briefing falls back to headlines gracefully."""
    service = BriefingService(
        db=db_session,
        api_key=fake_settings.groq_api_key,
        model=fake_settings.groq_model,
    )

    with respx.mock() as respx_mock:
        respx_mock.get(HN_TOP_STORIES_URL).respond(200, json=[6001])
        respx_mock.get(HN_ITEM_URL_TEMPLATE.format(item_id=6001)).respond(
            200,
            json={
                "id": 6001,
                "type": "story",
                "title": "PostgreSQL 17 Released",
                "url": "https://postgresql.org/release-17",
                "score": 400,
            },
        )
        for _, url in [
            ("Python Insider", "https://feeds.feedburner.com/PythonInsider"),
            ("ArXiv CS AI", "https://export.arxiv.org/rss/cs.AI"),
        ]:
            respx_mock.get(url).respond(200, text="<rss><channel></channel></rss>")

        # AI fails with 503
        respx_mock.post(GROQ_API_URL).respond(503, text="Service Unavailable")

        async with httpx.AsyncClient() as client:
            briefing, formatted_text = await service.generate_daily_briefing(client=client)

    assert briefing is not None
    assert "PostgreSQL 17 Released" in formatted_text
    assert "Detailed interpretation unavailable (AI service offline)." in formatted_text


# --- Telegram Command Handlers Tests ---


def _build_telegram_mocks(user_id: int, text: str, settings, session_factory):
    user = User(id=user_id, first_name="User", is_bot=False)
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
    context.bot_data = {
        "settings": settings,
        "db_session_factory": session_factory,
    }
    return update, message, context


@pytest.mark.asyncio
async def test_telegram_report_command_owner_flow(fake_settings):
    """T-AUTH-01 & FR-008: /report command works for owner and ignores non-owner."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = get_session_factory(engine)

    # 1. Non-owner message is silently ignored
    up_stranger, msg_stranger, ctx_stranger = _build_telegram_mocks(
        user_id=111111,
        text="/report",
        settings=fake_settings,
        session_factory=session_factory,
    )
    await report_command(up_stranger, ctx_stranger)
    assert msg_stranger.reply_text.call_count == 0

    # 2. Owner message produces report reply
    with respx.mock() as respx_mock:
        respx_mock.get(HN_TOP_STORIES_URL).respond(200, json=[])
        for _, url in [
            ("Python Insider", "https://feeds.feedburner.com/PythonInsider"),
            ("ArXiv CS AI", "https://export.arxiv.org/rss/cs.AI"),
        ]:
            respx_mock.get(url).respond(200, text="<rss><channel></channel></rss>")

        up_owner, msg_owner, ctx_owner = _build_telegram_mocks(
            user_id=fake_settings.owner_telegram_id,
            text="/report",
            settings=fake_settings,
            session_factory=session_factory,
        )
        await report_command(up_owner, ctx_owner)
        assert msg_owner.reply_text.call_count >= 2
        last_reply = msg_owner.reply_text.call_args_list[-1][0][0]
        assert "Daily Briefing" in last_reply
