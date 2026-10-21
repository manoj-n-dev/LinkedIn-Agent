"""Briefing service orchestrating research collection, AI analysis, and persistence.

Implements FR-008, FR-010, FR-012.
"""

import asyncio
import logging
import re
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.ai.groq_client import AIError, generate_completion
from src.ai.prompts import build_briefing_prompt
from src.db.models import AICall, AuditLog, Briefing, BriefingItem, Source
from src.research.dedup import is_url_seen, mark_url_seen
from src.research.hn_client import ResearchItem, fetch_hn_top_stories
from src.research.rss_client import fetch_rss_feed

logger = logging.getLogger(__name__)

DEFAULT_RSS_SOURCES = [
    ("Python Insider", "https://feeds.feedburner.com/PythonInsider"),
    ("ArXiv CS AI", "https://export.arxiv.org/rss/cs.AI"),
]


def sanitize_briefing_text(text: str) -> str:
    """Enforce CR-12: The phrase 'trending on LinkedIn' must never appear."""
    pattern = re.compile(r"trending\s+on\s+linkedin", re.IGNORECASE)
    return pattern.sub("emerging in tech", text)


def parse_ai_briefing_response(
    raw_response: str,
    items: list[ResearchItem],
) -> tuple[dict[int, tuple[str, str]], str]:
    """Parse structured FACT, INTERPRETATION, and SUGGESTIONS from AI response."""
    facts_and_interps: dict[int, tuple[str, str]] = {}
    suggestions = ""

    lines = raw_response.splitlines()
    current_idx: int | None = None
    current_fact: str = ""
    current_interp: str = ""
    in_suggestions = False
    suggestion_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.upper().startswith("SUGGESTIONS"):
            in_suggestions = True
            if current_idx is not None:
                facts_and_interps[current_idx] = (current_fact.strip(), current_interp.strip())
            continue

        if in_suggestions:
            suggestion_lines.append(stripped)
            continue

        item_match = re.match(r"^ITEM:\s*(\d+)", stripped, re.IGNORECASE)
        if item_match:
            if current_idx is not None:
                facts_and_interps[current_idx] = (current_fact.strip(), current_interp.strip())
            current_idx = int(item_match.group(1))
            current_fact = ""
            current_interp = ""
            continue

        if stripped.upper().startswith("FACT:"):
            current_fact = stripped[5:].strip()
        elif stripped.upper().startswith("INTERPRETATION:"):
            current_interp = stripped[15:].strip()

    if current_idx is not None and current_idx not in facts_and_interps:
        facts_and_interps[current_idx] = (current_fact.strip(), current_interp.strip())

    if suggestion_lines:
        suggestions = "\n".join(suggestion_lines)

    # Fallback for any items missed by parser
    for idx, itm in enumerate(items, start=1):
        if idx not in facts_and_interps or not facts_and_interps[idx][0]:
            facts_and_interps[idx] = (itm.title, "Developer discussion and industry update.")

    return facts_and_interps, suggestions


class BriefingService:
    """Manages legal research item fetching, AI distillation, and persistence."""

    def __init__(self, db: Session, api_key: str, model: str):
        self.db = db
        self.api_key = api_key
        self.model = model

    async def collect_fresh_items(
        self,
        max_items: int = 5,
        client: httpx.AsyncClient | None = None,
    ) -> list[ResearchItem]:
        """Fetch items from Hacker News and configured RSS feeds, filtering out seen URLs."""
        # 1. Load active sources from database or fallback to defaults
        db_sources = (
            self.db.execute(
                select(Source).where(Source.enabled == True)  # noqa: E712
            )
            .scalars()
            .all()
        )

        tasks = []
        if db_sources:
            for s in db_sources:
                if s.kind == "hn":
                    tasks.append(fetch_hn_top_stories(limit=10, client=client))
                elif s.kind == "rss" and s.url:
                    tasks.append(fetch_rss_feed(s.url, source_name=s.name, limit=10, client=client))
        else:
            tasks.append(fetch_hn_top_stories(limit=10, client=client))
            for name, url in DEFAULT_RSS_SOURCES:
                tasks.append(fetch_rss_feed(url, source_name=name, limit=10, client=client))

        source_results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: list[ResearchItem] = []
        for res in source_results:
            if isinstance(res, list):
                all_items.extend(res)

        # 2. Filter out already-seen URLs (FR-012)
        fresh_items: list[ResearchItem] = []
        for itm in all_items:
            if not is_url_seen(self.db, itm.url):
                fresh_items.append(itm)
                if len(fresh_items) >= max_items:
                    break

        return fresh_items

    async def generate_daily_briefing(
        self,
        run_date: date | None = None,
        tone: str = "friendly, honest, curious, professional",
        language: str = "English",
        client: httpx.AsyncClient | None = None,
    ) -> tuple[Briefing | None, str]:
        """Generate a complete briefing, persist to database, and return formatted text."""
        target_date = run_date or datetime.now(UTC).date()

        # Check if briefing for this date already exists
        existing_briefing = self.db.execute(
            select(Briefing).where(Briefing.run_date == target_date)
        ).scalar_one_or_none()

        if existing_briefing and existing_briefing.items:
            return existing_briefing, self.format_briefing_message(existing_briefing)

        # 1. Fetch fresh items
        items = await self.collect_fresh_items(max_items=5, client=client)
        if not items:
            return None, "📰 Daily Briefing: No new research items found today across your sources."

        # 2. Prepare AI distillation input
        items_payload_lines = []
        for idx, itm in enumerate(items, start=1):
            items_payload_lines.append(
                f"Item {idx}:\nTitle: {itm.title}\nSource: {itm.source_name}\n"
                f"Summary: {itm.summary}\nURL: {itm.url}"
            )
        items_text = "\n\n".join(items_payload_lines)

        sys_prompt, user_prompt = build_briefing_prompt(items_text, tone=tone, language=language)

        # 3. Call AI with fallback for unavailable/rate-limited AI (FR-022)
        parsed_analysis: dict[int, tuple[str, str]] = {}
        suggestions_text = ""
        try:
            ai_text = await generate_completion(
                api_key=self.api_key,
                model=self.model,
                system_prompt=sys_prompt,
                user_prompt=user_prompt,
                client=client,
            )
            clean_ai_text = sanitize_briefing_text(ai_text)
            parsed_analysis, suggestions_text = parse_ai_briefing_response(clean_ai_text, items)

            self.db.add(
                AICall(
                    provider="groq",
                    purpose="daily_briefing",
                    status="success",
                    http_status=200,
                )
            )
        except (AIError, Exception) as exc:
            logger.warning("AI briefing generation failed, falling back to headlines: %s", exc)
            self.db.add(
                AICall(
                    provider="groq",
                    purpose="daily_briefing",
                    status="fallback",
                )
            )
            # Graceful fallback: headlines as facts, offline notice as interpretation
            for idx, itm in enumerate(items, start=1):
                parsed_analysis[idx] = (
                    itm.title,
                    "Detailed interpretation unavailable (AI service offline).",
                )

        # 4. Save Briefing record
        if existing_briefing:
            briefing = existing_briefing
            briefing.status = "ready"
            briefing.notes = suggestions_text
        else:
            briefing = Briefing(
                run_date=target_date,
                status="ready",
                notes=suggestions_text,
            )
            self.db.add(briefing)
        self.db.flush()

        # 5. Save BriefingItems and mark URLs seen (FR-010, FR-012)
        for idx, itm in enumerate(items, start=1):
            fact, interp = parsed_analysis.get(idx, (itm.title, "Industry development."))
            b_item = BriefingItem(
                briefing_id=briefing.id,
                position=idx,
                title=itm.title,
                url=itm.url,
                source_name=itm.source_name,
                published_at=itm.published_at,
                fact_text=fact,
                interpretation_text=interp,
            )
            self.db.add(b_item)
            mark_url_seen(self.db, itm.url)

        self.db.add(
            AuditLog(
                actor="system",
                event="briefing_created",
                entity_type="briefing",
                entity_id=str(briefing.id),
                outcome="success",
                details={"date": str(target_date), "items_count": len(items)},
            )
        )
        self.db.commit()
        self.db.refresh(briefing)
        return briefing, self.format_briefing_message(briefing)

    def format_briefing_message(self, briefing: Briefing) -> str:
        """Format briefing into a readable Telegram message with clear fact/opinion separation."""
        lines = [f"📰 Daily Briefing — {briefing.run_date.isoformat()}\n"]

        sorted_items = sorted(briefing.items, key=lambda x: x.position)
        for itm in sorted_items:
            lines.append(
                f"{itm.position}. {itm.title} ({itm.source_name})\n"
                f"   🔗 {itm.url}\n"
                f"   📌 Fact: {itm.fact_text}\n"
                f"   💡 Why it matters: {itm.interpretation_text}\n"
            )

        if briefing.notes and briefing.notes.strip():
            lines.append(f"💡 Ideas for your next post:\n{briefing.notes.strip()}\n")

        lines.append("To draft a post from any item: /draft <your idea or item number>")
        result = "\n".join(lines)
        return sanitize_briefing_text(result)
