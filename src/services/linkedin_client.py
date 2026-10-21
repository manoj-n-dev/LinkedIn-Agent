"""Official LinkedIn API Client (FR-007, SEC-014, POL-F-14).

Strict scope:
- ONLY official LinkedIn API endpoints.
- NO scraping, browser automation, or unofficial APIs.
- Mandatory timeout handling: timeouts raise PublishTimeoutError (outcome UNKNOWN).
"""

from typing import Any

import httpx

REST_POSTS_ENDPOINT = "https://api.linkedin.com/rest/posts"
UGC_POSTS_ENDPOINT = "https://api.linkedin.com/v2/ugcPosts"
DEFAULT_API_VERSION = "202401"


class LinkedInPublishError(Exception):
    """Base exception for LinkedIn publishing errors."""


class PublishTimeoutError(LinkedInPublishError):
    """Raised when publishing request times out (outcome UNKNOWN, FR-025)."""


class PublishAPIError(LinkedInPublishError):
    """Raised when LinkedIn API returns 4xx or 5xx status codes (SEC-014)."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"LinkedIn API error (HTTP {status_code}): {message}")


async def publish_ugc_post(
    access_token: str,
    author_urn: str,
    text: str,
    endpoint: str = REST_POSTS_ENDPOINT,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    """Publish a text post via the official LinkedIn API.

    Args:
        access_token: Plaintext OAuth 2.0 bearer token.
        author_urn: LinkedIn member URN (e.g. 'urn:li:person:12345').
        text: Pre-validated exact post commentary.
        endpoint: Official API endpoint URL.
        timeout_seconds: Strict timeout limit.

    Returns:
        dict with 'post_id' and 'raw_response'.

    Raises:
        PublishTimeoutError: If the HTTP request times out.
        PublishAPIError: If LinkedIn returns a 4xx or 5xx error.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    # Format payload depending on endpoint
    if "ugcPosts" in endpoint:
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
    else:
        # Default REST Posts API
        headers["Linkedin-Version"] = DEFAULT_API_VERSION
        payload = {
            "author": author_urn,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(endpoint, headers=headers, json=payload)
    except httpx.TimeoutException as e:
        raise PublishTimeoutError(
            f"LinkedIn publishing timed out after {timeout_seconds}s. Outcome is UNKNOWN."
        ) from e
    except httpx.RequestError as e:
        raise PublishTimeoutError(
            f"Network connection failed during LinkedIn publish: {e}. Outcome is UNKNOWN."
        ) from e

    if resp.status_code not in (200, 201):
        raise PublishAPIError(
            status_code=resp.status_code,
            message=resp.text[:500],
        )

    # Post ID is either in headers['x-restli-id'] or payload['id']
    post_id = resp.headers.get("x-restli-id")
    if not post_id and resp.content:
        try:
            body = resp.json()
            post_id = body.get("id")
        except Exception:
            post_id = None

    if not post_id:
        post_id = "unknown_id"

    return {"post_id": post_id, "http_status": resp.status_code}
