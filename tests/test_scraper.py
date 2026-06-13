import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from backend.scraper import UPCScraper


@pytest.fixture
def scraper():
    return UPCScraper()


@pytest.mark.asyncio
async def test_scrape_openfoodfacts_success(scraper):
    """Test Open Food Facts scraper with successful response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "product": {
            "product_name": "Test Product",
            "brands": "TestBrand",
            "categories": "Snacks,Chips",
            "image_url": "https://example.com/image.jpg",
            "quantity": "150g",
        }
    }

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await scraper.scrape_openfoodfacts("123456789012")

    assert result.success is True
    assert result.name == "Test Product"
    assert result.brand == "TestBrand"
    assert result.source == "OpenFoodFacts"


@pytest.mark.asyncio
async def test_scrape_openfoodfacts_not_found(scraper):
    """Test Open Food Facts scraper with 404 response."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await scraper.scrape_openfoodfacts("123456789012")

    assert result.success is False
    assert "404" in result.error or result.error is not None


@pytest.mark.asyncio
async def test_scrape_upcitemdb_success(scraper):
    """Test UPCItemDB scraper with successful response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [{
            "title": "Test Item",
            "brand": "TestBrand",
            "category": "Electronics",
            "description": "A test item",
            "images": ["https://example.com/img.jpg"],
        }]
    }

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        result = await scraper.scrape_upcitemdb("123456789012")

    assert result.success is True
    assert result.name == "Test Item"
    assert result.brand == "TestBrand"


@pytest.mark.asyncio
async def test_scrape_all_sources(scraper):
    """Test that scrape_all aggregates results from multiple sources."""
    mock_response_off = MagicMock()
    mock_response_off.status_code = 200
    mock_response_off.json.return_value = {
        "product": {
            "product_name": "OFF Product",
            "brands": "OFFBrand",
            "categories": "Food",
            "image_url": "https://off.com/img.jpg",
        }
    }

    mock_response_upc = MagicMock()
    mock_response_upc.status_code = 200
    mock_response_upc.json.return_value = {
        "items": [{
            "title": "UPC Product",
            "brand": "UPCBrand",
            "category": "Groceries",
            "description": "UPC description",
            "images": ["https://upc.com/img.jpg"],
        }]
    }

    # Mock other sources to return failures quickly
    mock_fail = MagicMock()
    mock_fail.status_code = 404
    mock_fail.text = "Not found"

    def mock_get(url, **kwargs):
        if "world.openfoodfacts.org" in url:
            return mock_response_off
        elif "api.upcitemdb.com" in url:
            return mock_response_upc
        return mock_fail

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        results = await scraper.scrape_all("123456789012")

    assert len(results) >= 2
    sources = [r.source for r in results if r.success]
    assert "OpenFoodFacts" in sources
    assert "UPCItemDB" in sources


@pytest.mark.asyncio
async def test_rate_limiting(scraper):
    """Test that rate limiting delays are applied between requests."""
    import time

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"

    with patch("httpx.AsyncClient.get", return_value=mock_response):
        start = time.time()
        # Make two requests to the same source
        await scraper.scrape_openfoodfacts("111111111111")
        await scraper.scrape_openfoodfacts("222222222222")
        elapsed = time.time() - start

    # Should have at least 1 second delay between requests
    assert elapsed >= 1.0
