import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from backend.image_verifier import (
    ProductImageVerifier,
    _center_fill_score,
    _hamming_distance,
    _image_hash,
    _quality_score,
    _sharpness_score,
    _white_background_score,
    select_hero_image,
)


def make_image(width: int, height: int, background: str = "white") -> Image.Image:
    """Create a simple test image."""
    if background == "white":
        color = (255, 255, 255)
    elif background == "gray":
        color = (128, 128, 128)
    else:
        color = (0, 0, 0)
    img = Image.new("RGB", (width, height), color)
    return img


def make_hero_image(width: int = 800, height: int = 800) -> Image.Image:
    """Create a product-style image: dark centered object on white background."""
    img = Image.new("RGB", (width, height), (255, 255, 255))
    # Draw a dark rectangle in the center 50% of the frame
    left = width // 4
    top = height // 4
    right = 3 * width // 4
    bottom = 3 * height // 4
    for x in range(left, right):
        for y in range(top, bottom):
            img.putpixel((x, y), (64, 64, 64))
    return img


def test_white_background_score():
    """A fully white image should score high."""
    img = make_image(400, 400, "white")
    score = _white_background_score(img)
    assert score >= 0.9


def test_quality_score_acceptable():
    """A reasonably sized square image should score well."""
    img = make_image(800, 800, "white")
    score = _quality_score(img)
    assert score >= 0.5


def test_quality_score_rejects_small():
    """A tiny image should score zero."""
    img = make_image(100, 100, "white")
    score = _quality_score(img)
    assert score == 0.0


def test_center_fill_score():
    """A product-like center object should score higher than a blank image."""
    hero = make_hero_image(400, 400)
    blank = make_image(400, 400, "white")
    assert _center_fill_score(hero) > _center_fill_score(blank)


def test_sharpness_score():
    """An image with edges should have a non-zero sharpness score."""
    hero = make_hero_image(400, 400)
    score = _sharpness_score(hero)
    assert score > 0.0


def test_image_hash_consistency():
    """Same image should produce same hash."""
    img = make_image(400, 400, "white")
    h1 = _image_hash(img)
    h2 = _image_hash(img)
    assert h1 == h2
    assert _hamming_distance(h1, h2) == 0


@pytest.mark.asyncio
async def test_verify_images_selects_best():
    """Verifier should score and rank candidate images."""
    verifier = ProductImageVerifier()

    # Build a small white test image as bytes
    white_img = make_image(400, 400, "white")
    buf = io.BytesIO()
    white_img.save(buf, format="PNG")
    white_bytes = buf.getvalue()

    mock_response = MagicMock()
    mock_response.content = white_bytes

    candidates = [
        {"url": "https://example.com/a.jpg", "source": "Test", "score": 0.9},
        {"url": "https://example.com/b.jpg", "source": "Test", "score": 0.8},
    ]

    with patch.object(verifier.client, "get", return_value=mock_response):
        results = await verifier.verify_images(candidates)

    assert len(results) >= 1
    assert results[0].is_verified()
    assert results[0].white_bg_score >= 0.9
    await verifier.close()


@pytest.mark.asyncio
async def test_select_hero_image_returns_single_best():
    """select_hero_image should return exactly one hero dict and URL."""
    hero_img = make_hero_image(800, 800)
    buf = io.BytesIO()
    hero_img.save(buf, format="PNG")
    hero_bytes = buf.getvalue()

    mock_response = MagicMock()
    mock_response.content = hero_bytes

    candidates = [
        {"url": "https://example.com/a.jpg", "source": "Test", "score": 0.9},
        {"url": "https://example.com/b.jpg", "source": "Test", "score": 0.8},
    ]

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        hero_dict, hero_url = await select_hero_image(candidates)

    assert hero_dict is not None
    assert hero_url is not None
    assert hero_dict["url"] == hero_url
    assert hero_dict["verified"] is True
