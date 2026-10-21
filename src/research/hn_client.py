"""Hacker News Firebase API client for tech trend research (FR-008)."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

logger = logging.getLogger(__name__)

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL_TEMPLATE = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"


@dataclass
class ResearchItem:
    """Standardized news or research item."""

    title: str
    url: str
    source_name: str
    published_at: datetime | None = None
    summary: str = ""


async def fetch_hn_top_stories(
    limit: int = 10,
    client: httpx.AsyncClient | None = None,
) -> list[ResearchItem]:
    """Fetch top stories from the official Hacker News Firebase API."""

    async def _fetch(http_client: httpx.AsyncClient) -> list[ResearchItem]:
        try:
            resp = await http_client.get(HN_TOP_STORIES_URL, timeout=10.0)
            resp.raise_for_status()
            story_ids: list[int] = resp.json()[:limit]
        except Exception as exc:
            logger.warning("Failed to fetch Hacker News top stories: %s", exc)
            return []

        async def _fetch_story(story_id: int) -> ResearchItem | None:
            try:
                story_resp = await http_client.get(
                    HN_ITEM_URL_TEMPLATE.format(item_id=story_id),
                    timeout=5.0,
                )
                if story_resp.status_code != 200:
                    return None
                data = story_resp.json()
                if not data or data.get("type") != "story":
                    return None

                title = data.get("title", "").strip()
                url = data.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
                time_val = data.get("time")
                pub_date = datetime.fromtimestamp(time_val, tz=UTC) if time_val else None

                if not title:
                    return None

                return ResearchItem(
                    title=title,
                    url=url,
                    source_name="Hacker News",
                    published_at=pub_date,
                    summary=f"Score: {data.get('score', 0)} by {data.get('by', 'unknown')}",
                )
            except Exception as exc:
                logger.debug("Failed fetching HN item %d: %s", story_id, exc)
                return None

        tasks = [_fetch_story(s_id) for s_id in story_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        items: list[ResearchItem] = []
        for res in results:
            if isinstance(res, ResearchItem):
                items.append(res)
        return items

    if client is not None:
        return await _fetch(client)

    async with httpx.AsyncClient() as new_client:
        return await _fetch(new_client)
