"""Outbound Network Allow-List Guard (FR-030, SEC-030, T-NET-01).

Restricts all outbound HTTP calls to an approved list of official hosts:
- Telegram Bot API (api.telegram.org)
- Groq AI API (api.groq.com)
- LinkedIn Official APIs (api.linkedin.com, www.linkedin.com for OAuth)
- Approved research sources (Hacker News Firebase API, owner RSS feeds)

Strictly blocks all unauthorized hosts, telemetry, and private networks.
"""

from urllib.parse import urlparse

DEFAULT_ALLOWED_HOSTS: set[str] = {
    "api.telegram.org",
    "api.groq.com",
    "api.linkedin.com",
    "www.linkedin.com",
    "hacker-news.firebaseio.com",
    "news.ycombinator.com",
}


class NetworkSecurityError(Exception):
    """Raised when an outbound request attempts to contact an unapproved host (SEC-030)."""


class NetworkGuard:
    """Enforces strict outbound host allow-list (FR-030, SEC-030)."""

    def __init__(self, additional_allowed_hosts: set[str] | None = None):
        self.allowed_hosts = set(DEFAULT_ALLOWED_HOSTS)
        if additional_allowed_hosts:
            self.allowed_hosts.update(h.lower().strip() for h in additional_allowed_hosts)

    def validate_url(self, url: str) -> str:
        """Validate whether a target URL is in the outbound allow-list.

        Args:
            url: Outbound target URL string.

        Returns:
            str: Validated URL string.

        Raises:
            NetworkSecurityError: If host is not allow-listed or uses an invalid scheme.
        """
        if not url:
            raise NetworkSecurityError("Target URL cannot be empty.")

        parsed = urlparse(url)
        scheme = (parsed.scheme or "").lower()
        if scheme not in ("http", "https"):
            raise NetworkSecurityError(f"Prohibited URL scheme '{scheme}'. Only HTTP/S allowed.")

        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise NetworkSecurityError("Target URL must contain a valid hostname.")

        # Check against allowed hosts (exact match or subdomain match for trusted sources)
        is_allowed = False
        for allowed in self.allowed_hosts:
            if hostname == allowed or hostname.endswith("." + allowed):
                is_allowed = True
                break

        if not is_allowed:
            raise NetworkSecurityError(
                f"Outbound network request to '{hostname}' refused: Host is not in the allow-list "
                f"(FR-030, SEC-030). Telemetry and unauthorized network access are forbidden."
            )

        return url
