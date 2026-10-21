"""Safe HTTP fetcher with SSRF prevention and size limits (FR-009, SEC-006, SEC-020)."""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 1024 * 1024  # 1 MB
DEFAULT_TIMEOUT_SECONDS = 10.0

DISALLOWED_DOMAINS = frozenset({"linkedin.com", "www.linkedin.com", "api.linkedin.com"})


class SSRFBlockedError(ValueError):
    """Raised when a URL attempts to access private, local, or disallowed hosts."""


class ResponseTooLargeError(ValueError):
    """Raised when response body exceeds maximum allowed size."""


def is_ip_disallowed(ip_str: str) -> bool:
    """Check if an IP string is private, loopback, link-local, or reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return True


def validate_target_url(url: str) -> None:
    """Validate URL scheme, domain, and IP to prevent SSRF and forbidden targets."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFBlockedError(
            f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP/HTTPS allowed."
        )

    hostname = (parsed.hostname or "").lower().strip()
    if not hostname:
        raise SSRFBlockedError("URL has no valid hostname.")

    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise SSRFBlockedError("Access to localhost is blocked.")

    # Strictly block any LinkedIn URLs from research fetching (SEC-006)
    if hostname in DISALLOWED_DOMAINS or hostname.endswith(".linkedin.com"):
        raise SSRFBlockedError("Fetching from linkedin.com is prohibited (SEC-006).")

    # Resolve hostname to verify destination IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if is_ip_disallowed(ip_str):
                raise SSRFBlockedError(
                    f"Host '{hostname}' resolved to disallowed/private IP '{ip_str}'."
                )
    except socket.gaierror as exc:
        raise SSRFBlockedError(f"Unable to resolve host '{hostname}': {exc}") from exc


async def safe_fetch(
    url: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_size: int = MAX_BODY_BYTES,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Safely fetch a URL with SSRF checks, timeout, and response size limits."""
    validate_target_url(url)

    async def _do_fetch(http_client: httpx.AsyncClient) -> str:
        headers = {
            "User-Agent": "LinkedInAgent-Research/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml, text/html, application/json",
        }
        resp = await http_client.get(
            url,
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
        )

        content_length_hdr = resp.headers.get("Content-Length")
        if content_length_hdr and content_length_hdr.isdigit():
            if int(content_length_hdr) > max_size:
                raise ResponseTooLargeError(
                    f"Response size ({content_length_hdr} bytes) exceeds {max_size} bytes limit."
                )

        body_bytes = resp.content
        if len(body_bytes) > max_size:
            raise ResponseTooLargeError(
                f"Response body size ({len(body_bytes)} bytes) exceeds {max_size} bytes limit."
            )

        resp.raise_for_status()
        return resp.text

    if client is not None:
        return await _do_fetch(client)

    async with httpx.AsyncClient() as new_client:
        return await _do_fetch(new_client)
