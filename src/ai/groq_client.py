"""Groq AI client implementation for drafting (FR-004, FR-022, V6).

AI is strictly an untrusted text generator with no tool access and no secrets (SEC-005).
Uses standard OpenAI-compatible completions API with one Groq account key.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_TIMEOUT_SECONDS = 30.0


class AIError(Exception):
    """Base exception for AI provider errors."""


class AIRateLimitError(AIError):
    """Raised when Groq returns 429 Too Many Requests (FR-022)."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class AITimeoutError(AIError):
    """Raised when the AI call times out (FR-022)."""


class AIUnavailableError(AIError):
    """Raised when the AI provider returns 5xx or connection fails (FR-022)."""


async def generate_completion(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 1500,
    client: httpx.AsyncClient | None = None,
) -> str:
    """Send prompt to Groq and return generated text.

    Args:
        api_key: Groq API key from settings.
        model: Model identifier.
        system_prompt: System prompt with persona and rules.
        user_prompt: Untrusted user input enclosed in delimiters.
        temperature: Sampling temperature.
        max_tokens: Maximum tokens in response.
        client: Optional pre-existing httpx AsyncClient (useful for testing/reuse).

    Returns:
        Generated text response.

    Raises:
        AIRateLimitError: If HTTP 429 is received.
        AITimeoutError: If call times out.
        AIUnavailableError: On 5xx or connection error.
        AIError: On other client errors.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async def _send(http_client: httpx.AsyncClient) -> str:
        try:
            resp = await http_client.post(
                GROQ_API_URL,
                json=payload,
                headers=headers,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as exc:
            logger.warning("Groq API request timed out: %s", type(exc).__name__)
            raise AITimeoutError("AI service request timed out. Please try again.") from exc
        except httpx.RequestError as exc:
            logger.warning("Groq API connection error: %s", type(exc).__name__)
            raise AIUnavailableError(
                "Unable to reach AI service. Please check your connection."
            ) from exc

        if resp.status_code == 429:
            retry_after_hdr = resp.headers.get("Retry-After")
            retry_after = (
                int(retry_after_hdr) if retry_after_hdr and retry_after_hdr.isdigit() else None
            )
            logger.warning("Groq 429 rate limit reached. Retry-After: %s", retry_after)
            raise AIRateLimitError(
                "AI rate limit reached. Please wait a moment before drafting again.",
                retry_after=retry_after,
            )

        if resp.status_code >= 500:
            logger.error("Groq 5xx server error: %d", resp.status_code)
            raise AIUnavailableError(
                f"AI service temporarily unavailable (status {resp.status_code})."
            )

        if resp.status_code >= 400:
            logger.error("Groq 4xx client error: %d", resp.status_code)
            raise AIError(f"AI service error (status {resp.status_code}).")

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
            return content.strip()
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Malformed AI response format: %s", exc)
            raise AIError("Received malformed response from AI service.") from exc

    if client is not None:
        return await _send(client)

    async with httpx.AsyncClient() as new_client:
        return await _send(new_client)
