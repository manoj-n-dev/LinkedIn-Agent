"""Programmatic content rule checks (09-content-rules.md, SEC-012).

"A rule only in the prompt is a wish; a rule in code is a rule."
Checks character limits, verifies URLs against allow-lists, and appends mandatory
manual-action notices.
"""

import re
from typing import NamedTuple

POST_MAX_LENGTH = 3000
COMMENT_MAX_LENGTH = 1250
CONNECTION_NOTE_MAX_LENGTH = 200

COMMENT_DISCLAIMER = "\n\n💡 Copy and post this yourself. I did not send anything."
NOTE_DISCLAIMER = "\n\n💡 Send this yourself from LinkedIn."

URL_REGEX = re.compile(r"https?://[^\s<>\"']+")
HASHTAG_REGEX = re.compile(r"(?:^|\s)(#[A-Za-z0-9_\-]+)")


class ValidationResult(NamedTuple):
    """Result of content rules validation."""

    is_valid: bool
    cleaned_text: str
    warnings: list[str]
    disallowed_urls: list[str]


def extract_post_and_checklist(raw_text: str) -> tuple[str, str | None]:
    """Extract <POST> content and <CHECKLIST> if wrapped in XML tags, or return raw."""
    post_match = re.search(r"<POST>(.*?)</POST>", raw_text, re.DOTALL | re.IGNORECASE)
    checklist_match = re.search(
        r"<CHECKLIST>(.*?)</CHECKLIST>", raw_text, re.DOTALL | re.IGNORECASE
    )

    post_body = post_match.group(1).strip() if post_match else raw_text.strip()
    checklist = checklist_match.group(1).strip() if checklist_match else None
    return post_body, checklist


def validate_post(text: str, allowed_urls: set[str] | None = None) -> ValidationResult:
    """Validate LinkedIn post draft against length, links, and hashtags."""
    warnings: list[str] = []
    disallowed: list[str] = []

    body, checklist = extract_post_and_checklist(text)

    # 1. Length check
    if len(body) > POST_MAX_LENGTH:
        warnings.append(
            f"Draft length ({len(body)} chars) exceeds maximum limit ({POST_MAX_LENGTH} chars)."
        )

    # 2. Check URLs (no invented links - CR-02, CR-08)
    found_urls = set(URL_REGEX.findall(body))
    if allowed_urls is None:
        # If no allowed URLs provided, any invented URL triggers a warning
        if found_urls:
            disallowed = list(found_urls)
            warnings.append(f"Draft contains unverified URLs: {', '.join(disallowed)}")
    else:
        for url in found_urls:
            if url not in allowed_urls:
                disallowed.append(url)
        if disallowed:
            warnings.append(f"Draft contains unapproved URLs: {', '.join(disallowed)}")

    # 3. Check hashtags (max 3 - CR-06)
    hashtags = HASHTAG_REGEX.findall(body)
    if len(hashtags) > 3:
        warnings.append(f"Draft has {len(hashtags)} hashtags (recommended max 3).")

    # Combine body with checklist if present
    final_text = body
    if checklist:
        final_text += f"\n\n🔍 Check before posting:\n{checklist}"

    return ValidationResult(
        is_valid=len(body) <= POST_MAX_LENGTH and not disallowed,
        cleaned_text=final_text,
        warnings=warnings,
        disallowed_urls=disallowed,
    )


def validate_comment(text: str) -> ValidationResult:
    """Validate comment draft and append mandatory manual-post reminder."""
    warnings: list[str] = []
    body = text.strip()

    if len(body) > COMMENT_MAX_LENGTH:
        warnings.append(
            f"Comment length ({len(body)} chars) exceeds limit ({COMMENT_MAX_LENGTH} chars)."
        )

    final_text = body + COMMENT_DISCLAIMER
    return ValidationResult(
        is_valid=len(body) <= COMMENT_MAX_LENGTH,
        cleaned_text=final_text,
        warnings=warnings,
        disallowed_urls=[],
    )


def validate_connection_note(text: str) -> ValidationResult:
    """Validate connection note against strict 200 char limit and append disclaimer."""
    warnings: list[str] = []
    body = text.strip()

    if len(body) > CONNECTION_NOTE_MAX_LENGTH:
        warnings.append(f"Connection note ({len(body)} chars) exceeds strict 200 character limit.")

    final_text = body + NOTE_DISCLAIMER
    return ValidationResult(
        is_valid=len(body) <= CONNECTION_NOTE_MAX_LENGTH,
        cleaned_text=final_text,
        warnings=warnings,
        disallowed_urls=[],
    )
