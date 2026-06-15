from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.scraper import UPCScraper


@pytest.fixture
def scraper():
    client = httpx.AsyncClient()
    return UPCScraper(client)


@pytest.mark.asyncio
async def test_scrape_openfoodfacts_success(scraper):
    """Test Open Food Facts scraper with successful response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": 1,
        "product": {
            "product_name": "Test Product",
            "brands": "TestBrand",
            "categories": "Snacks,Chips",
            "image_url": "https://example.com/image.jpg",
            "quantity": "150g",
        },
    }

    with patch.object(scraper, "_get_with_retry", return_value=mock_response):
        result = await scraper._open_food_facts("123456789012")

    assert result["success"] is True
    assert result["name"] == "Test Product"
    assert result["brand"] == "TestBrand"
    assert result["source"] == "Open Food Facts"


@pytest.mark.asyncio
async def test_scrape_openfoodfacts_not_found(scraper):
    """Test Open Food Facts scraper with missing product."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": 0, "product": {}}

    with patch.object(scraper, "_get_with_retry", return_value=mock_response):
        result = await scraper._open_food_facts("123456789012")

    assert result["success"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_scrape_upcitemdb_success(scraper):
    """Test UPCItemDB scraper with successful response."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "title": "Test Item",
                "brand": "TestBrand",
                "category": "Electronics",
                "description": "A test item",
                "images": ["https://example.com/img.jpg"],
            }
        ]
    }

    with patch.object(scraper, "_get_with_retry", return_value=mock_response):
        result = await scraper._upcitemdb("123456789012")

    assert result["success"] is True
    assert result["name"] == "Test Item"
    assert result["brand"] == "TestBrand"


@pytest.mark.asyncio
async def test_scrape_all_aggregates_results(scraper):
    """Test that scrape_all aggregates results from multiple sources."""
    off_response = MagicMock()
    off_response.json.return_value = {
        "status": 1,
        "product": {
            "product_name": "OFF Product",
            "brands": "OFFBrand",
            "categories": "Food",
            "image_url": "https://off.com/img.jpg",
        },
    }

    upc_response = MagicMock()
    upc_response.json.return_value = {
        "items": [
            {
                "title": "UPC Product",
                "brand": "UPCBrand",
                "category": "Groceries",
                "description": "UPC description",
                "images": ["https://upc.com/img.jpg"],
            }
        ]
    }

    fail_response = MagicMock()
    fail_response.json.return_value = {}

    def mock_get(url, **kwargs):
        if "world.openfoodfacts.org" in url:
            return off_response
        elif "api.upcitemdb.com" in url:
            return upc_response
        return fail_response

    with patch.object(scraper, "_get_with_retry", side_effect=mock_get):
        results = await scraper.scrape_all("123456789012")

    sources = [r["source"] for r in results if r.get("success")]
    assert "Open Food Facts" in sources
    assert "UPCItemDB" in sources


@pytest.mark.asyncio
async def test_rate_limiting(scraper):
    """Test that scraper handles sequential requests."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": 0}

    with patch.object(scraper, "_get_with_retry", return_value=mock_response):
        result1 = await scraper._open_food_facts("111111111111")
        result2 = await scraper._open_food_facts("222222222222")

    assert result1["success"] is False
    assert result2["success"] is False
