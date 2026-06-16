"""Product image search by name/brand for codes with no public UPC data.

Tries API-based image search first, then falls back to scraping DuckDuckGo
Images so the pipeline can still find verified product photos for local PLUs
and other store-specific codes.
"""

from __future__ import annotations

import logging
import os
import re
import urllib.parse
from urllib.parse import urljoin
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("shelfwise.image_search")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def _clean_image_url(url: str) -> Optional[str]:
    """Clean and validate an image URL from a search engine."""
    if not url:
        return None
    url = url.strip()
    # Google sometimes wraps image URLs
    if url.startswith("/"):
        return None
    # Remove query-string size parameters common in search results
    if url.startswith("http"):
        parsed = urllib.parse.urlparse(url)
        # Reject obvious tracking/ad domains
        blocked = {"googletagmanager.com", "doubleclick.net", "google-analytics.com"}
        if any(d in parsed.netloc for d in blocked):
            return None
        # Require an image-like extension or a known image host
        ext = os.path.splitext(parsed.path.lower())[1]
        image_exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
        known_hosts = {
            "amazon.com",
            "ssl-images-amazon.com",
            "media-amazon.com",
            "walmartimages.com",
            "i5.walmartimages.com",
            "target.com",
            "scene7.com",
            "ebayimg.com",
            "ebaystatic.com",
            "costco-static.com",
            "samsclubresources.com",
            "images.openfoodfacts.org",
            "gstatic.com",
            "googleusercontent.com",
            "bing.net",
            "alicdn.com",
            "shopifycdn.net",
            "cloudinary.com",
        }
        if ext in image_exts or any(h in parsed.netloc for h in known_hosts):
            return url
    return None


def _clean_page_url(url: str) -> Optional[str]:
    """Clean and validate a product/listing page URL from web search results."""
    if not url:
        return None
    url = urllib.parse.unquote(url.strip())
    if url.startswith("//"):
        url = "https:" + url
    if url.startswith("/l/?kh=") or "uddg=" in url:
        parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        if parsed_qs.get("uddg"):
            url = parsed_qs["uddg"][0]
    if not url.startswith("http"):
        return None

    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    blocked_hosts = {
        "google.com",
        "bing.com",
        "duckduckgo.com",
        "facebook.com",
        "pinterest.com",
        "youtube.com",
        "instagram.com",
        "tiktok.com",
    }
    if any(host == blocked or host.endswith("." + blocked) for blocked in blocked_hosts):
        return None
    if any(part in parsed.path.lower() for part in ("/login", "/signin", "/cart", "/account")):
        return None
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def _extract_listing_urls(html: str, base_url: str, max_results: int) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: List[str] = []
    selectors = [
        "li.b_algo h2 a[href]",
        "ol#b_results h2 a[href]",
        "a.result__a[href]",
        "a[href]",
    ]
    anchors = []
    for selector in selectors:
        anchors.extend(soup.select(selector))
        if anchors:
            break
    for anchor in anchors:
        href = anchor.get("href") or ""
        if href.startswith("/"):
            href = urljoin(base_url, href)
        cleaned = _clean_page_url(href)
        if cleaned and cleaned not in urls:
            urls.append(cleaned)
        if len(urls) >= max_results:
            break
    return urls


def direct_listing_urls_for_upc(upc: str) -> List[str]:
    """Known retailer/database URLs worth probing directly for a UPC."""
    if not upc:
        return []
    encoded = urllib.parse.quote_plus(upc)
    return [
        f"https://www.upcitemdb.com/upc/{encoded}",
        f"https://www.barcodelookup.com/{encoded}",
        f"https://www.buycott.com/upc/{encoded}",
        f"https://go-upc.com/search?q={encoded}",
        f"https://www.ebay.com/sch/i.html?_nkw={encoded}",
        f"https://www.walmart.com/search?q={encoded}",
        f"https://www.amazon.com/s?k={encoded}",
        f"https://www.target.com/s?searchTerm={encoded}",
        f"https://www.samsclub.com/sams/search/searchResults.jsp?searchTerm={encoded}",
        f"https://www.costco.com/CatalogSearch?keyword={encoded}",
        f"https://www.kroger.com/search?query={encoded}",
        f"https://www.homedepot.com/s/{encoded}",
        f"https://www.lowes.com/search?searchTerm={encoded}",
        f"https://www.staples.com/{encoded}/directory_{encoded}",
    ]


async def _brave_image_search(client: httpx.AsyncClient, query: str, max_results: int = 10) -> List[str]:
    """Search Brave Images API."""
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        return []
    try:
        url = "https://api.search.brave.com/res/v1/images/search"
        headers = {"X-Subscription-Token": api_key, "Accept": "application/json"}
        params = {"q": query, "count": min(max_results, 50)}
        response = await client.get(url, headers=headers, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        urls = []
        for r in results:
            for key in ("image", "thumbnail", "url"):
                u = _clean_image_url(r.get(key, ""))
                if u and u not in urls:
                    urls.append(u)
                    break
        logger.info(f"Brave image search returned {len(urls)} URLs for '{query}'")
        return urls
    except Exception as e:
        logger.warning(f"Brave image search failed: {e}")
        return []


async def _serpapi_image_search(client: httpx.AsyncClient, query: str, max_results: int = 10) -> List[str]:
    """Search Google Images through SerpAPI when SERPAPI_KEY is configured."""
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        return []
    try:
        response = await client.get(
            "https://serpapi.com/search.json",
            params={"engine": "google_images", "q": query, "api_key": api_key},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        urls = []
        for item in data.get("images_results", [])[:max_results]:
            for key in ("original", "thumbnail"):
                u = _clean_image_url(item.get(key, ""))
                if u and u not in urls:
                    urls.append(u)
                    break
        logger.info("SerpAPI image search returned %s URLs for %r", len(urls), query)
        return urls
    except Exception as e:
        logger.warning(f"SerpAPI image search failed: {e}")
        return []


async def _searchapi_image_search(client: httpx.AsyncClient, query: str, max_results: int = 10) -> List[str]:
    """Search Google Images through SearchAPI.io when SEARCHAPI_KEY is configured."""
    api_key = os.environ.get("SEARCHAPI_KEY", "")
    if not api_key:
        return []
    try:
        response = await client.get(
            "https://www.searchapi.io/api/v1/search",
            params={"engine": "google_images", "q": query, "api_key": api_key},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        urls = []
        for item in data.get("images", [])[:max_results]:
            for key in ("original", "image", "thumbnail"):
                u = _clean_image_url(item.get(key, ""))
                if u and u not in urls:
                    urls.append(u)
                    break
        logger.info("SearchAPI image search returned %s URLs for %r", len(urls), query)
        return urls
    except Exception as e:
        logger.warning(f"SearchAPI image search failed: {e}")
        return []


async def _google_image_search(client: httpx.AsyncClient, query: str, max_results: int = 10) -> List[str]:
    """Search Google Custom Search for images."""
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    cx = os.environ.get("GOOGLE_CX", "")
    if not api_key or not cx:
        return []
    try:
        url = "https://www.googleapis.com/customsearch/v1"
        params = {"key": api_key, "cx": cx, "q": query, "searchType": "image", "num": min(max_results, 10)}
        response = await client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])
        urls = []
        for item in items:
            u = _clean_image_url(item.get("link", ""))
            if u and u not in urls:
                urls.append(u)
        logger.info(f"Google image search returned {len(urls)} URLs for '{query}'")
        return urls
    except Exception as e:
        logger.warning(f"Google image search failed: {e}")
        return []


async def _duckduckgo_image_search(client: httpx.AsyncClient, query: str, max_results: int = 10) -> List[str]:
    """Scrape DuckDuckGo Images (no API key required)."""
    try:
        # Step 1: get a token via the DDG IT endpoint
        token_url = "https://duckduckgo.com/"
        params = {"q": query}
        resp = await client.get(token_url, params=params, headers=DEFAULT_HEADERS, timeout=15.0)
        resp.raise_for_status()
        text = resp.text

        # Extract vqd token
        vqd_match = re.search(r"vqd=([\d-]+)&", text) or re.search(r'"vqd":"([^"]+)"', text)
        if not vqd_match:
            logger.warning("Could not extract DuckDuckGo vqd token")
            return []
        vqd = vqd_match.group(1)

        # Step 2: fetch image results
        search_url = "https://duckduckgo.com/i.js"
        search_params = {
            "q": query,
            "vqd": vqd,
            "f": ",,,",
            "p": "1",
        }
        resp = await client.get(search_url, params=search_params, headers=DEFAULT_HEADERS, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        urls = []
        for r in results[:max_results]:
            u = _clean_image_url(r.get("image", ""))
            if u and u not in urls:
                urls.append(u)
        logger.info(f"DuckDuckGo image search returned {len(urls)} URLs for '{query}'")
        return urls
    except Exception as e:
        logger.warning(f"DuckDuckGo image search failed: {e}")
        return []


async def _bing_image_search(client: httpx.AsyncClient, query: str, max_results: int = 10) -> List[str]:
    """Scrape Bing Images as a last-resort fallback."""
    try:
        url = "https://www.bing.com/images/search"
        params = {"q": query, "form": "HDRSC2", "first": "1"}
        resp = await client.get(url, params=params, headers=DEFAULT_HEADERS, timeout=15.0)
        resp.raise_for_status()
        # Bing embeds image data in murl attributes
        urls = []
        for match in re.finditer(r'murl":"(https?://[^"]+)"', resp.text):
            u = _clean_image_url(match.group(1))
            if u and u not in urls:
                urls.append(u)
            if len(urls) >= max_results:
                break
        logger.info(f"Bing image search returned {len(urls)} URLs for '{query}'")
        return urls
    except Exception as e:
        logger.warning(f"Bing image search failed: {e}")
        return []


async def _duckduckgo_listing_search(client: httpx.AsyncClient, query: str, max_results: int = 10) -> List[str]:
    """Search DuckDuckGo HTML results for product/listing pages."""
    try:
        url = "https://html.duckduckgo.com/html/"
        resp = await client.get(url, params={"q": query}, headers=DEFAULT_HEADERS, timeout=12.0)
        resp.raise_for_status()
        urls = _extract_listing_urls(resp.text, url, max_results)
        logger.info("DuckDuckGo listing search returned %s URLs for %r", len(urls), query)
        return urls
    except Exception as e:
        logger.warning(f"DuckDuckGo listing search failed: {e}")
        return []


async def _bing_listing_search(client: httpx.AsyncClient, query: str, max_results: int = 10) -> List[str]:
    """Search Bing results for product/listing pages."""
    try:
        url = "https://www.bing.com/search"
        resp = await client.get(url, params={"q": query}, headers=DEFAULT_HEADERS, timeout=12.0)
        resp.raise_for_status()
        urls = _extract_listing_urls(resp.text, url, max_results)
        logger.info("Bing listing search returned %s URLs for %r", len(urls), query)
        return urls
    except Exception as e:
        logger.warning(f"Bing listing search failed: {e}")
        return []


async def _brave_listing_search(client: httpx.AsyncClient, query: str, max_results: int = 10) -> List[str]:
    """Search web results through Brave Search API."""
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        return []
    try:
        response = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
            params={"q": query, "count": min(max_results, 20)},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        urls = []
        for item in data.get("web", {}).get("results", []):
            cleaned = _clean_page_url(item.get("url", ""))
            if cleaned and cleaned not in urls:
                urls.append(cleaned)
        logger.info("Brave listing search returned %s URLs for %r", len(urls), query)
        return urls
    except Exception as e:
        logger.warning(f"Brave listing search failed: {e}")
        return []


async def _serpapi_listing_search(client: httpx.AsyncClient, query: str, max_results: int = 10) -> List[str]:
    """Search web results through SerpAPI when SERPAPI_KEY is configured."""
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        return []
    try:
        response = await client.get(
            "https://serpapi.com/search.json",
            params={"engine": "google", "q": query, "api_key": api_key},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        urls = []
        for item in data.get("organic_results", [])[:max_results]:
            cleaned = _clean_page_url(item.get("link", ""))
            if cleaned and cleaned not in urls:
                urls.append(cleaned)
        logger.info("SerpAPI listing search returned %s URLs for %r", len(urls), query)
        return urls
    except Exception as e:
        logger.warning(f"SerpAPI listing search failed: {e}")
        return []


async def _ebay_listing_search(client: httpx.AsyncClient, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search eBay Browse API when EBAY_BEARER_TOKEN is configured."""
    token = os.environ.get("EBAY_BEARER_TOKEN", "")
    if not token:
        return []
    try:
        response = await client.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"q": query, "limit": min(max_results, 50)},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        listings = []
        for item in data.get("itemSummaries", [])[:max_results]:
            image_url = (item.get("image") or {}).get("imageUrl")
            listings.append(
                {
                    "source": "eBay Browse",
                    "source_url": item.get("itemWebUrl"),
                    "name": item.get("title"),
                    "description": item.get("shortDescription"),
                    "image_urls": [image_url] if image_url else [],
                    "attributes": {"listing_price": (item.get("price") or {}).get("value")} if item.get("price") else {},
                    "success": True,
                }
            )
        logger.info("eBay Browse search returned %s listings for %r", len(listings), query)
        return listings
    except Exception as e:
        logger.warning(f"eBay Browse search failed: {e}")
        return []


async def search_product_listing_pages(
    query: str,
    max_results: int = 8,
    client: Optional[httpx.AsyncClient] = None,
) -> List[Dict[str, Any]]:
    """Search the web for retailer/marketplace product listing pages."""
    _owned = client is None
    client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        results: List[Dict[str, Any]] = []
        seen_urls = set()
        for fn, source in [
            (_brave_listing_search, "Brave Listings"),
            (_serpapi_listing_search, "SerpAPI Listings"),
            (_duckduckgo_listing_search, "DuckDuckGo Listings"),
            (_bing_listing_search, "Bing Listings"),
        ]:
            found = await fn(client, query, max_results)
            for url in found:
                if url not in seen_urls:
                    seen_urls.add(url)
                    results.append({"url": url, "source": source})
            if len(results) >= max_results:
                break
        return results[:max_results]
    finally:
        if _owned:
            await client.aclose()


async def search_structured_marketplace_listings(
    query: str,
    max_results: int = 8,
    client: Optional[httpx.AsyncClient] = None,
) -> List[Dict[str, Any]]:
    """Search structured marketplace APIs for product listing evidence."""
    _owned = client is None
    client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        listings: List[Dict[str, Any]] = []
        for fn in [_ebay_listing_search]:
            found = await fn(client, query, max_results)
            listings.extend(found)
            if listings:
                break
        return listings[:max_results]
    finally:
        if _owned:
            await client.aclose()


def _meta_content(soup: BeautifulSoup, selector: str) -> Optional[str]:
    tag = soup.select_one(selector)
    if not tag:
        return None
    return (tag.get("content") or tag.get_text(" ", strip=True) or "").strip() or None


def _looks_like_blocked_page(title: Optional[str], description: Optional[str], html: str) -> bool:
    text = " ".join([title or "", description or "", html[:2000]]).lower()
    blocked_markers = [
        "robot or human",
        "captcha",
        "verify you are human",
        "access denied",
        "automated access",
        "blocked",
        "enable javascript",
    ]
    return any(marker in text for marker in blocked_markers)


def _jsonld_products(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            import json

            data = json.loads(raw)
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop(0)
            if not isinstance(item, dict):
                continue
            item_type = item.get("@type")
            if item_type == "Product" or (isinstance(item_type, list) and "Product" in item_type):
                products.append(item)
            graph = item.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
    return products


def _coerce_image_urls(value: Any, base_url: str) -> List[str]:
    raw_urls: List[str] = []
    if isinstance(value, str):
        raw_urls.append(value)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                raw_urls.append(item)
            elif isinstance(item, dict):
                raw_urls.append(str(item.get("url") or item.get("contentUrl") or ""))
    elif isinstance(value, dict):
        raw_urls.append(str(value.get("url") or value.get("contentUrl") or ""))

    urls: List[str] = []
    for raw_url in raw_urls:
        if not raw_url:
            continue
        absolute = urljoin(base_url, raw_url)
        cleaned = _clean_image_url(absolute)
        if cleaned and cleaned not in urls:
            urls.append(cleaned)
    return urls


async def scrape_product_listing_page(
    url: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Optional[Dict[str, Any]]:
    """Scrape product metadata from a retailer/marketplace listing page."""
    cleaned_url = _clean_page_url(url)
    if not cleaned_url:
        return None

    _owned = client is None
    client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        resp = await client.get(cleaned_url, headers=DEFAULT_HEADERS, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "").lower()
        if content_type and "html" not in content_type:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        title = (
            _meta_content(soup, "meta[property='og:title']")
            or _meta_content(soup, "meta[name='twitter:title']")
            or _meta_content(soup, "h1")
            or _meta_content(soup, "title")
        )
        description = (
            _meta_content(soup, "meta[property='og:description']")
            or _meta_content(soup, "meta[name='description']")
            or _meta_content(soup, "meta[name='twitter:description']")
        )
        if _looks_like_blocked_page(title, description, resp.text):
            return None
        images: List[str] = []
        for selector in (
            "meta[property='og:image']",
            "meta[property='og:image:secure_url']",
            "meta[name='twitter:image']",
            "meta[name='twitter:image:src']",
        ):
            image = _meta_content(soup, selector)
            for url_value in _coerce_image_urls(image, cleaned_url):
                if url_value not in images:
                    images.append(url_value)

        brand = None
        category = None
        price = None
        for product in _jsonld_products(soup):
            title = title or product.get("name")
            description = description or product.get("description")
            brand_value = product.get("brand")
            if isinstance(brand_value, dict):
                brand = brand or brand_value.get("name")
            elif isinstance(brand_value, str):
                brand = brand or brand_value
            category = category or product.get("category")
            offers = product.get("offers")
            if isinstance(offers, dict):
                price = price or offers.get("price")
            for image in _coerce_image_urls(product.get("image"), cleaned_url):
                if image not in images:
                    images.append(image)

        if not title and not description and not images:
            return None

        return {
            "source": urllib.parse.urlparse(cleaned_url).netloc,
            "source_url": cleaned_url,
            "name": title,
            "brand": brand,
            "category": category,
            "description": description,
            "image_urls": images,
            "attributes": {"listing_price": price} if price else {},
            "raw": {"listing_url": cleaned_url},
            "success": True,
        }
    except Exception as e:
        logger.info("Listing scrape failed for %s: %s", cleaned_url, e)
        return None
    finally:
        if _owned:
            await client.aclose()


async def search_product_images(
    query: str,
    max_results: int = 10,
    client: Optional[httpx.AsyncClient] = None,
) -> List[Dict[str, Any]]:
    """Search the web for product images matching a query.

    Returns a list of {"url": str, "source": str} dicts ranked by search order.
    Tries Brave, Google, DuckDuckGo, and Bing in sequence until results are found.
    """
    _owned = client is None
    client = client or httpx.AsyncClient(timeout=20.0, follow_redirects=True)
    try:
        results: List[Dict[str, Any]] = []
        seen_urls = set()
        for fn, source in [
            (_brave_image_search, "Brave Image Search"),
            (_serpapi_image_search, "SerpAPI Images"),
            (_searchapi_image_search, "SearchAPI Images"),
            (_google_image_search, "Google Image Search"),
            (_duckduckgo_image_search, "DuckDuckGo Images"),
            (_bing_image_search, "Bing Images"),
        ]:
            found = await fn(client, query, max_results)
            for u in found:
                if u not in seen_urls:
                    seen_urls.add(u)
                    results.append({"url": u, "source": source})
            if len(results) >= max_results:
                break

        return results[:max_results]
    finally:
        if _owned:
            await client.aclose()


async def search_images_for_product(
    name: str,
    brand: Optional[str] = None,
    max_results: int = 10,
    client: Optional[httpx.AsyncClient] = None,
) -> List[Dict[str, Any]]:
    """Build a search query from product name/brand and return image candidates."""
    parts = [name]
    if brand:
        parts.append(brand)
    query = " ".join(parts)
    return await search_product_images(query, max_results=max_results, client=client)
