"""Image generation service for LinkedIn post visuals (free, watermark-free)."""

import io
import logging
import secrets
import urllib.parse

import httpx
from PIL import Image

from src.ai.groq_client import generate_completion
from src.ai.prompts import build_image_prompt

logger = logging.getLogger(__name__)


async def generate_smart_image_prompt(post_text: str, api_key: str = "", model: str = "") -> str:
    """Use AI to extract the real-world subject and create a tailored, authentic visual prompt.

    Args:
        post_text: Full drafted post body.
        api_key: Optional Groq API key for intelligent visual prompt generation.
        model: Model identifier.

    Returns:
        str: Specific visual prompt tailored to the draft.
    """
    if api_key and model:
        try:
            system_prompt = (
                "You are an expert visual director for top LinkedIn tech and business creators. "
                "Analyze the given post and identify its real-world context (e.g. software "
                "engineering, system architecture, AI development, product strategy, desk setup). "
                "Return ONLY a vivid, 20-30 word description of a photorealistic scene directly "
                "illustrating that scenario. Style: High-end editorial photography, 35mm lens, "
                "natural cinematic lighting, crisp depth of field. STRICT: NO text, NO words, "
                "NO letters, NO logos, NO abstract fantasy avatars, NO glowing crystal puzzles. "
                "Ground it in real life."
            )
            ai_prompt = await generate_completion(
                api_key=api_key,
                model=model,
                system_prompt=system_prompt,
                user_prompt=post_text[:1200],
                max_tokens=60,
                temperature=0.4,
            )
            cleaned = ai_prompt.strip().replace("\n", " ").replace('"', "")
            if len(cleaned) > 15:
                return cleaned
        except Exception as exc:
            logger.debug("AI image prompt generation failed, falling back: %s", exc)

    return build_image_prompt(post_text)


def get_post_image_url(visual_prompt: str, seed: int | None = None) -> str:
    """Generate a clean 1200x700 LinkedIn graphic URL (cropped to 1200x630 watermark-free).

    Args:
        visual_prompt: The detailed visual description.
        seed: Optional random seed for variation.

    Returns:
        str: Direct image URL.
    """
    clean_prompt = f"{visual_prompt.strip()}, photorealistic, clean borders, highly detailed, 4k"
    encoded = urllib.parse.quote(clean_prompt)
    random_seed = seed or (100000 + secrets.randbelow(899999))
    base_url = "https://image.pollinations.ai/prompt"
    # Request 1200x700 so we can crop the bottom 70px to eliminate any watermark
    params = f"width=1200&height=700&seed={random_seed}&model=flux"
    return f"{base_url}/{encoded}?{params}"


async def download_and_clean_image(image_url: str, crop_bottom_px: int = 70) -> io.BytesIO:
    """Download image and remove bottom watermark strip, returning pristine 1200x630 bytes.

    Args:
        image_url: The image URL to fetch.
        crop_bottom_px: Height of bottom watermark strip to crop out (default 70px).

    Returns:
        io.BytesIO: Buffer containing pristine watermark-free JPEG bytes.
    """
    async with httpx.AsyncClient(timeout=35.0) as client:
        resp = await client.get(image_url)
        resp.raise_for_status()
        raw_bytes = resp.content

    img = Image.open(io.BytesIO(raw_bytes))
    w, h = img.size

    # Crop the bottom banner containing platform watermarks
    crop_height = max(100, h - crop_bottom_px)
    cropped = img.crop((0, 0, w, crop_height))

    # Resize to exact standard LinkedIn landscape format (1200x630)
    final_img = cropped.resize((1200, 630), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    buf.name = "linkedin_visual.jpg"
    final_img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf

