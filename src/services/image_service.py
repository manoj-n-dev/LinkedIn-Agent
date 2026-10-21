"""Image generation service for LinkedIn post visual assets (free, zero-config)."""

import urllib.parse

from src.ai.prompts import build_image_prompt


def get_post_image_url(post_text: str, custom_prompt: str | None = None) -> str:
    """Generate a high-quality 1200x630 LinkedIn graphic URL using Pollinations AI.

    Args:
        post_text: The drafted post body to generate a graphic for.
        custom_prompt: Optional custom visual prompt override.

    Returns:
        str: Direct image URL suitable for Telegram send_photo or web preview.
    """
    raw_prompt = custom_prompt or build_image_prompt(post_text)
    encoded = urllib.parse.quote(raw_prompt)
    base_url = "https://image.pollinations.ai/prompt"
    return f"{base_url}/{encoded}?width=1200&height=630&nologo=true&model=flux"
