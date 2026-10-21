"""URL canonicalization, SHA-256 hashing, and deduplication tracking (FR-012)."""

import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.db.models import SeenItem

TRACKING_PARAMS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "fbclid",
        "gclid",
        "ref",
        "source",
    }
)


def canonicalize_url(raw_url: str) -> str:
    """Canonicalize a URL by normalizing case and stripping tracking parameters."""
    parsed = urlparse(raw_url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Filter out common analytics and marketing tracking query parameters
    query_params = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    query_params.sort(key=lambda x: x[0])
    cleaned_query = urlencode(query_params)

    path = parsed.path
    if path == "/":
        path = ""

    return urlunparse((scheme, netloc, path, parsed.params, cleaned_query, ""))


def compute_url_hash(raw_url: str) -> str:
    """Return SHA-256 hex digest of the canonicalized URL."""
    canonical = canonicalize_url(raw_url)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_url_seen(db: Session, raw_url: str) -> bool:
    """Check if the URL has already been processed in a prior run."""
    url_hash = compute_url_hash(raw_url)
    existing = db.execute(
        select(SeenItem.url_hash).where(SeenItem.url_hash == url_hash)
    ).scalar_one_or_none()
    return existing is not None


def mark_url_seen(db: Session, raw_url: str) -> None:
    """Record URL hash in seen_items table."""
    url_hash = compute_url_hash(raw_url)
    existing = db.execute(
        select(SeenItem.url_hash).where(SeenItem.url_hash == url_hash)
    ).scalar_one_or_none()
    if not existing:
        db.add(SeenItem(url_hash=url_hash))


def prune_old_seen_items(db: Session, retention_days: int = 90) -> int:
    """Remove seen item records older than the retention period."""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    result = db.execute(delete(SeenItem).where(SeenItem.first_seen_at < cutoff))
    return result.rowcount or 0
