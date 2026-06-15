import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from backend.image_verifier import (
    ProductImageVerifier,
    _hamming_distance,
    _image_hash,
    _quality_score,
    _white_background_score,
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
