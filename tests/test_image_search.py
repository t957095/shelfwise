from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.image_search import (
    _clean_image_url,
    scrape_product_listing_page,
    search_images_for_product,
    search_product_images,
)


def test_clean_image_url_rejects_invalid():
    assert _clean_image_url("") is None
    assert _clean_image_url("/relative/path.jpg") is None
    assert _clean_image_url("https://googletagmanager.com/track.png") is None


def test_clean_image_url_accepts_direct_image():
    url = "https://example.com/product.jpg"
    assert _clean_image_url(url) == url


@pytest.mark.asyncio
async def test_search_product_images_falls_back_to_duckduckgo():
    """When Brave/Google return nothing, DuckDuckGo fallback is used."""
    client = MagicMock()

    # Mock DuckDuckGo token page
    token_response = MagicMock()
    token_response.text = "some html vqd=123-456& more html"

    # Mock DuckDuckGo image results
    results_response = MagicMock()
    results_response.json.return_value = {
        "results": [
            {"image": "https://example.com/img1.jpg"},
            {"image": "https://example.com/img2.jpg"},
        ]
    }

    async def mock_get(url, **kwargs):
        if "duckduckgo.com/i.js" in str(url):
            return results_response
        return token_response

    client.get = AsyncMock(side_effect=mock_get)

    with patch.dict("os.environ", {"BRAVE_API_KEY": "", "GOOGLE_API_KEY": ""}):
        results = await search_product_images("test product", max_results=5, client=client)

    assert len(results) == 2
    assert results[0]["url"] == "https://example.com/img1.jpg"
    assert results[0]["source"] == "Image Search"


@pytest.mark.asyncio
async def test_search_images_for_product_builds_query():
    """search_images_for_product builds a name+brand query."""
    with patch("backend.image_search.search_product_images") as mock_search:
        mock_search.return_value = [{"url": "https://example.com/img.jpg", "source": "Image Search"}]
        results = await search_images_for_product("Soda", brand="Coca-Cola", max_results=3)
        mock_search.assert_called_once_with("Soda Coca-Cola", max_results=3, client=None)
        assert len(results) == 1


@pytest.mark.asyncio
async def test_scrape_product_listing_page_extracts_metadata():
    html = """
    <html>
      <head>
        <meta property="og:title" content="Example Cleaner">
        <meta property="og:description" content="A powerful cleaning product.">
        <meta property="og:image" content="https://cdn.example.com/cleaner.jpg">
        <script type="application/ld+json">
        {"@type":"Product","brand":{"name":"ExampleCo"},"category":"Cleaning Supplies","offers":{"price":"4.99"}}
        </script>
      </head>
    </html>
    """
    response = MagicMock()
    response.text = html
    response.headers = {"content-type": "text/html"}
    response.raise_for_status.return_value = None
    client = MagicMock()
    client.get = AsyncMock(return_value=response)

    result = await scrape_product_listing_page("https://store.example.com/p/cleaner", client=client)

    assert result["name"] == "Example Cleaner"
    assert result["description"] == "A powerful cleaning product."
    assert result["brand"] == "ExampleCo"
    assert result["category"] == "Cleaning Supplies"
    assert result["image_urls"] == ["https://cdn.example.com/cleaner.jpg"]
    assert result["attributes"]["listing_price"] == "4.99"
