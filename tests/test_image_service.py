"""Unit tests for image_service covering smart prompt, URL formatting, and Pillow cleaning."""

import io
from unittest.mock import AsyncMock, patch

import pytest
import respx
from PIL import Image

from src.services.image_service import (
    download_and_clean_image,
    generate_smart_image_prompt,
    get_post_image_url,
)


@pytest.mark.asyncio
async def test_generate_smart_image_prompt_fallback():
    """Verify fallback to build_image_prompt when Groq API key is omitted."""
    post = (
        "I spent three days debugging a distributed consensus bug. "
        "Lessons learned: monitor latency."
    )
    prompt = await generate_smart_image_prompt(post, api_key="", model="")
    assert len(prompt) > 10
    lower = prompt.lower()
    assert "consensus" in lower or "latency" in lower or "debugging" in lower


@pytest.mark.asyncio
async def test_generate_smart_image_prompt_ai_success():
    """Verify smart prompt generation uses Groq completion when configured."""
    post = "We built a multi-agent system for LinkedIn. It watches feeds and learns."
    with patch(
        "src.services.image_service.generate_completion",
        new=AsyncMock(
            return_value="A software architect reviewing neural network graphs on modern monitors."
        ),
    ):
        prompt = await generate_smart_image_prompt(post, api_key="gsk_dummy", model="model_dummy")
        assert "software architect" in prompt


def test_get_post_image_url_params():
    """Verify get_post_image_url formats URL with seed for Pollinations free tier."""
    url = get_post_image_url("developer at clean desk", seed=12345)
    assert "image.pollinations.ai" in url
    assert "seed=12345" in url


@pytest.mark.asyncio
async def test_download_and_clean_image_crops_watermark():
    """Verify download_and_clean_image removes bottom strip and outputs 1200x630."""
    raw_img = Image.new("RGB", (1200, 700), color=(30, 40, 50))
    raw_buf = io.BytesIO()
    raw_img.save(raw_buf, format="JPEG")
    raw_bytes = raw_buf.getvalue()

    fake_url = "https://image.pollinations.ai/prompt/test?width=1200&height=700"
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get(fake_url).respond(
            status_code=200,
            headers={"content-type": "image/jpeg"},
            content=raw_bytes,
        )
        clean_buf = await download_and_clean_image(fake_url, crop_bottom_px=70)

    clean_img = Image.open(clean_buf)
    assert clean_img.size == (1200, 630)
