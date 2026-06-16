from unittest.mock import AsyncMock, patch

import pytest

from backend.image_acquisition import acquire_required_product_images


@pytest.mark.asyncio
async def test_acquire_required_product_images_applies_listing_evidence():
    product = {
        "upc": "123456789012",
        "name": "Unknown Product",
        "brand": None,
        "category": "Snacks",
        "description": "No reliable information available for this product.",
        "images": [],
        "citations": [],
        "reasoning_trace": [],
    }
    listing = {
        "source": "example-retailer.com",
        "source_url": "https://example-retailer.com/product/123",
        "name": "Example Snack Pack",
        "brand": "Example Brand",
        "description": "A real product description from a retailer listing.",
        "image_urls": ["https://example.com/product.jpg"],
    }

    with (
        patch("backend.image_acquisition.search_product_listing_pages", new=AsyncMock(return_value=[{"url": listing["source_url"]}])),
        patch("backend.image_acquisition.scrape_product_listing_page", new=AsyncMock(return_value=listing)),
        patch(
            "backend.image_acquisition.search_product_images",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "backend.image_acquisition.select_verified_images",
            new=AsyncMock(return_value=([{"url": "https://example.com/product.jpg", "source": "example-retailer.com", "score": 0.9, "verified": True}], "https://example.com/product.jpg")),
        ),
    ):
        images, best_url, trace = await acquire_required_product_images(product, per_query_timeout=0.1)

    assert best_url == "https://example.com/product.jpg"
    assert images[0]["verified"] is True
    assert product["name"] == "Example Snack Pack"
    assert product["brand"] == "Example Brand"
    assert product["description"] == "A real product description from a retailer listing."
    assert product["citations"][0]["source"] == "example-retailer.com"
    assert any("listing evidence" in line.lower() for line in trace)


@pytest.mark.asyncio
async def test_acquire_required_product_images_returns_review_candidate_when_unverified():
    product = {
        "upc": "123456789012",
        "name": "Snack item 123456789012",
        "brand": None,
        "category": "Snacks",
        "description": "Snacks product imported from POS UPC 123456789012.",
        "images": [],
        "citations": [],
        "reasoning_trace": [],
    }

    with (
        patch("backend.image_acquisition.search_product_listing_pages", new=AsyncMock(return_value=[])),
        patch(
            "backend.image_acquisition.search_product_images",
            new=AsyncMock(return_value=[{"url": "https://example.com/candidate.jpg", "source": "Image Search"}]),
        ),
        patch("backend.image_acquisition.select_verified_images", new=AsyncMock(return_value=([], None))),
    ):
        images, best_url, trace = await acquire_required_product_images(product, per_query_timeout=0.1)

    assert best_url == "https://example.com/candidate.jpg"
    assert images[0]["needs_review"] is True
    assert images[0]["verified"] is False
    assert any("real image candidates" in line for line in trace)
