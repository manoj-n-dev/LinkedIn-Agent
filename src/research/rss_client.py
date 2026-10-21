"""RSS feed client using feedparser and safe_fetch (FR-008, FR-009)."""

import logging
import re
import time
from datetime import UTC, datetime

import feedparser
import httpx

from src.research.fetcher import safe_fetch
from src.research.hn_client import ResearchItem

logger = logging.getLogger(__name__)

HTML_TAG_REGEX = re.compile(r"<[^>]+>")


def clean_html_text(raw_text: str) -> str:
    """Strip HTML tags and condense whitespace."""
    if not raw_text:
        return ""
    text_without_tags = HTML_TAG_REGEX.sub(" ", raw_text)
    return " ".join(text_without_tags.split())


async def fetch_rss_feed(
    feed_url: str,
    source_name: str,
    limit: int = 10,
    client: httpx.AsyncClient | None = None,
) -> list[ResearchItem]:
    """Fetch and parse an RSS or Atom feed safely."""
    try:
        content = await safe_fetch(feed_url, client=client)
    except Exception as exc:
        logger.warning("Failed to fetch RSS feed '%s' (%s): %s", source_name, feed_url, exc)
        return []

    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        logger.warning("Malformed RSS feed for '%s': %s", source_name, parsed.bozo_exception)
        return []

    items: list[ResearchItem] = []
    for entry in parsed.entries[:limit]:
        title = clean_html_text(entry.get("title", ""))
        link = entry.get("link", "").strip()
        summary = clean_html_text(entry.get("summary", entry.get("description", "")))

        if not title or not link:
            continue

        pub_date: datetime | None = None
        time_struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if time_struct:
            try:
                pub_date = datetime.fromtimestamp(time.mktime(time_struct), tz=UTC)
            except Exception:
                pub_date = None

        items.append(
            ResearchItem(
                title=title,
                url=link,
                source_name=source_name,
                published_at=pub_date,
                summary=summary[:300] if summary else "",
            )
        )

    return items
