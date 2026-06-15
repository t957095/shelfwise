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
from typing import Any, Dict, List, Optional

import httpx

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
        known_hosts = {"amazon.com", "walmartimages.com", "target.com", "i5.walmartimages.com"}
        if ext in image_exts or any(h in parsed.netloc for h in known_hosts):
            return url
    return None


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
        urls: List[str] = []
        for fn, source in [
            (_brave_image_search, "Brave Image Search"),
            (_google_image_search, "Google Image Search"),
            (_duckduckgo_image_search, "DuckDuckGo Images"),
            (_bing_image_search, "Bing Images"),
        ]:
            found = await fn(client, query, max_results)
            for u in found:
                if u not in urls:
                    urls.append(u)
            if urls:
                logger.info(f"Image search for '{query}' succeeded via {source}")
                break

        return [{"url": u, "source": "Image Search"} for u in urls[:max_results]]
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
