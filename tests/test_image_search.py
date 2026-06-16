from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.image_search import (
    _amazon_result_to_listing,
    _clean_image_url,
    _shopping_result_to_listing,
    category_listing_urls_for_upc,
    category_search_domains,
    scrape_product_listing_page,
    search_images_for_product,
    search_product_images,
    search_structured_marketplace_listings,
)


def test_clean_image_url_rejects_invalid():
    assert _clean_image_url("") is None
    assert _clean_image_url("/relative/path.jpg") is None
    assert _clean_image_url("https://googletagmanager.com/track.png") is None


def test_clean_image_url_accepts_direct_image():
    url = "https://example.com/product.jpg"
    assert _clean_image_url(url) == url


def test_category_listing_urls_route_pet_care_to_specialists():
    urls = category_listing_urls_for_upc("017800111719", "Pet Care")
    assert any("chewy.com" in url for url in urls)
    assert any("petco.com" in url for url in urls)
    assert "chewy.com" in category_search_domains("pet supplies")


def test_amazon_result_to_listing_maps_images_and_fields():
    listing = _amazon_result_to_listing(
        {
            "title": "Amazon Product",
            "asin": "B000TEST",
            "link": "https://www.amazon.com/dp/B000TEST",
            "image_url": "https://m.media-amazon.com/images/I/test.jpg",
            "price": 12.99,
            "currency": "USD",
            "rating": 4.5,
        },
        "Amazon Scraper API",
    )

    assert listing["source"] == "Amazon Scraper API"
    assert listing["name"] == "Amazon Product"
    assert listing["source_url"] == "https://www.amazon.com/dp/B000TEST"
    assert listing["image_urls"] == ["https://m.media-amazon.com/images/I/test.jpg"]
    assert listing["attributes"]["asin"] == "B000TEST"


def test_shopping_result_to_listing_maps_merchant_and_thumbnail():
    listing = _shopping_result_to_listing(
        {
            "title": "Shopping Product",
            "thumbnail": "https://encrypted-tbn0.gstatic.com/images?q=test",
            "price": "$4.99",
            "source": "Retailer",
            "product_link": "https://example.com/product",
        },
        "SerpAPI Google Shopping",
    )

    assert listing["source"] == "SerpAPI Google Shopping"
    assert listing["name"] == "Shopping Product"
    assert listing["source_url"] == "https://example.com/product"
    assert listing["image_urls"] == ["https://encrypted-tbn0.gstatic.com/images?q=test"]
    assert listing["attributes"]["merchant"] == "Retailer"


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
    assert results[0]["source"] == "DuckDuckGo Images"


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


@pytest.mark.asyncio
async def test_structured_marketplace_listings_aggregate_providers():
    with (
        patch("backend.image_search._omkar_amazon_search", new=AsyncMock(return_value=[{"source": "Amazon Scraper API"}])),
        patch("backend.image_search._rapidapi_amazon_search", new=AsyncMock(return_value=[{"source": "Amazon RapidAPI"}])),
        patch("backend.image_search._ebay_listing_search", new=AsyncMock(return_value=[{"source": "eBay Browse"}])),
    ):
        results = await search_structured_marketplace_listings("test", max_results=5)

    assert [r["source"] for r in results] == ["Amazon Scraper API", "Amazon RapidAPI", "eBay Browse"]
