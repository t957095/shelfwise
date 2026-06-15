"""ShelfWise UPC Scraper - Optimized.

Features:
- Circuit breaker pattern for failing sources
- Retry with exponential backoff
- Image URL validation
- Request coalescing (same UPC in-flight deduped)
- New sources: Lookify, UPCDatabase.org
- Structured logging per scrape
"""

import httpx
import os
import re
import asyncio
import logging
import time
import random
from typing import List, Dict, Optional, Any, Callable
from urllib.parse import urlparse
from bs4 import BeautifulSoup

logger = logging.getLogger("shelfwise.scraper")

# Source weights used by reasoning agent
SOURCE_WEIGHTS = {
    "Open Food Facts": 0.90,
    "UPCItemDB": 0.85,
    "BarcodeLookup": 0.75,
    "Go-UPC": 0.70,
    "Buycott": 0.65,
    "EANdata": 0.60,
    "Lookify": 0.55,
    "UPCDatabase": 0.50,
    "Brave Search": 0.45,
    "Google Search": 0.40,
}

DEFAULT_HEADERS = {
    "User-Agent": "ShelfWise/1.0 (AI Product Portfolio Builder; contact@shelfwise.local)"
}

ROTATING_HEADERS = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Linux"',
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
    },
]

# Concurrency / politeness knobs
MAX_INFLIGHT_REQUESTS = 100
MAX_PER_DOMAIN = 5
DOMAIN_DELAY_SECONDS = 0.1
MIN_SUCCESS_TO_STOP = 2
UPC_TIME_BUDGET_SECONDS = 15.0
MAX_RETRY_WAIT_SECONDS = 5.0

# Names that are not real product titles and should not count toward early stop
_BLOCKED_PRODUCT_NAMES = {
    "check digit", "product not found", "unknown product", "not found",
    "product", "unknown", "n/a", "na", "no data", "error",
}

# Circuit breaker state
CIRCUIT_FAILURE_THRESHOLD = 5
CIRCUIT_RECOVERY_TIMEOUT = 60.0


def _is_transient_error(e: Exception) -> bool:
    """Decide whether an exception should count toward the circuit breaker."""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        # 4xx client errors (except 429 rate-limit) are not transient
        if 400 <= code < 500 and code != 429:
            return False
        return True
    # Timeouts, connect errors, SSL issues, etc. are transient
    if isinstance(e, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
        return True
    return False


def _is_valid_image_url(url: str) -> bool:
    """Validate that a URL looks like an actual image."""
    if not url or not url.startswith("http"):
        return False
    parsed = urlparse(url)
    if not parsed.netloc or not parsed.path:
        return False
    # Reject common ad/tracking domains
    blocked_domains = {"googletagmanager.com", "doubleclick.net", "google-analytics.com"}
    if any(d in parsed.netloc for d in blocked_domains):
        return False
    return True


class CircuitBreaker:
    """Simple circuit breaker for external APIs."""

    def __init__(self, name: str, failure_threshold: int = CIRCUIT_FAILURE_THRESHOLD,
                 recovery_timeout: float = CIRCUIT_RECOVERY_TIMEOUT):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half_open
        self._lock = asyncio.Lock()

    async def call(self, fn: Callable, *args, **kwargs) -> Any:
        async with self._lock:
            if self.state == "open":
                if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                    self.state = "half_open"
                    logger.info(f"Circuit breaker {self.name}: entering half-open state")
                else:
                    raise Exception(f"Circuit breaker OPEN for {self.name}")

        try:
            result = await fn(*args, **kwargs)
            async with self._lock:
                if self.state == "half_open":
                    self.state = "closed"
                    self.failures = 0
                    logger.info(f"Circuit breaker {self.name}: closed")
            return result
        except Exception as e:
            async with self._lock:
                if self.state == "half_open":
                    # A single failure in half-open immediately reopens
                    self.state = "open"
                    self.last_failure_time = time.time()
                    logger.warning(f"Circuit breaker {self.name}: re-opened from half-open")
                    raise
                if _is_transient_error(e):
                    self.failures += 1
                    self.last_failure_time = time.time()
                    if self.failures >= self.failure_threshold:
                        self.state = "open"
                        logger.warning(f"Circuit breaker {self.name}: OPEN after {self.failures} transient failures")
                else:
                    # Non-transient failures don't count toward the breaker
                    logger.debug(f"Circuit breaker {self.name}: non-transient failure ignored ({e})")
            raise


class DomainLimiter:
    """Simple per-domain concurrency + delay limiter."""

    def __init__(self, max_concurrent: int = MAX_PER_DOMAIN, delay: float = DOMAIN_DELAY_SECONDS):
        self.sem = asyncio.Semaphore(max_concurrent)
        self.delay = delay
        self._last_release: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        await self.sem.acquire()
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_release
            if elapsed < self.delay:
                await asyncio.sleep(self.delay - elapsed)
            self._last_release = time.monotonic()

    def release(self):
        self.sem.release()


class UPCScraper:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.request_count = 0
        self._inflight: Dict[str, asyncio.Future] = {}
        self._inflight_lock = asyncio.Lock()
        self.circuits: Dict[str, CircuitBreaker] = {}
        self._global_sem = asyncio.Semaphore(MAX_INFLIGHT_REQUESTS)
        self._domain_limiters: Dict[str, DomainLimiter] = {}
        self._domain_lock = asyncio.Lock()
        self._dead_domains: set = set()

    def _domain_limiter(self, url: str) -> DomainLimiter:
        domain = urlparse(url).netloc.lower()
        if domain not in self._domain_limiters:
            self._domain_limiters[domain] = DomainLimiter()
        return self._domain_limiters[domain]

    def _get_circuit(self, name: str) -> CircuitBreaker:
        if name not in self.circuits:
            self.circuits[name] = CircuitBreaker(name)
        return self.circuits[name]

    def _next_headers(self) -> dict:
        headers = ROTATING_HEADERS[self.request_count % len(ROTATING_HEADERS)].copy()
        self.request_count += 1
        return headers

    def _is_dead_domain(self, url: str) -> bool:
        return urlparse(url).netloc.lower() in self._dead_domains

    async def _get_with_retry(self, url: str, timeout: float = 10.0, retries: int = 1,
                              **kwargs) -> httpx.Response:
        """GET with polite concurrency control and status-aware exponential backoff.

        Design goals:
        - Fail fast on 4xx client errors (including 429) — retrying wastes time.
        - Retry transient 5xx/server errors once with a capped wait.
        - Never retry unresolvable/dead domains or SSL cert failures.
        """
        # Build headers from kwarg or default
        headers = kwargs.pop("headers", DEFAULT_HEADERS)
        if isinstance(headers, dict):
            headers = dict(headers)  # copy
        else:
            headers = dict(DEFAULT_HEADERS)

        domain = urlparse(url).netloc.lower()
        if domain in self._dead_domains:
            raise httpx.ConnectError(f"Skipping known dead domain: {domain}")

        domain_limiter = self._domain_limiter(url)

        for attempt in range(retries + 1):
            try:
                async with self._global_sem:
                    await domain_limiter.acquire()
                    try:
                        response = await self.client.get(url, headers=headers, timeout=timeout, **kwargs)
                        response.raise_for_status()
                        return response
                    finally:
                        domain_limiter.release()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                # All 4xx (including 429) are client errors; retrying rarely helps.
                if 400 <= status < 500:
                    raise
                # 5xx and rare 3xx errors get one short retry.
                if attempt < retries:
                    wait = min(2 ** attempt + random.uniform(0, 1), MAX_RETRY_WAIT_SECONDS)
                    logger.debug(f"Retry {attempt + 1}/{retries} for {url} (HTTP {status}): sleeping {wait:.1f}s")
                    await asyncio.sleep(wait)
                else:
                    raise
            except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as e:
                err_text = str(e).lower()
                # Dead domains / bad SSL are permanent; mark and fail fast.
                if any(marker in err_text for marker in ("getaddrinfo", "name or service not known",
                                                         "nodename nor servprovided", "certificate verify failed")):
                    self._dead_domains.add(domain)
                    raise
                if attempt < retries:
                    wait = min(2 ** attempt + random.uniform(0, 1), MAX_RETRY_WAIT_SECONDS)
                    logger.debug(f"Retry {attempt + 1}/{retries} for {url}: {e}")
                    await asyncio.sleep(wait)
                else:
                    raise
            except Exception:
                # Unknown errors are not worth retrying.
                raise
        # Unreachable — each branch either returns or raises.
        raise RuntimeError("_get_with_retry exhausted without result")

    async def scrape_all(self, upc: str) -> List[Dict[str, Any]]:
        """Scrape all sources for a UPC with request coalescing.
        If another scrape for same UPC is in-flight, await that instead."""
        async with self._inflight_lock:
            if upc in self._inflight and not self._inflight[upc].done():
                logger.info(f"UPC {upc}: coalescing with in-flight request")
                return await self._inflight[upc]
            future = asyncio.get_event_loop().create_future()
            self._inflight[upc] = future

        try:
            results = await self._scrape_all_impl(upc)
            future.set_result(results)
            return results
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            async with self._inflight_lock:
                if upc in self._inflight and self._inflight[upc].done():
                    del self._inflight[upc]

    async def _scrape_all_impl(self, upc: str) -> List[Dict[str, Any]]:
        """Internal: scrape sources with bounded concurrency, politeness, and early stopping."""
        results = []
        start = time.time()

        # Core hardcoded scrapers (proven, high-quality parsers)
        core_scrapers = [
            ("Open Food Facts", self._open_food_facts, 0.90),
            ("UPCItemDB", self._upcitemdb, 0.85),
            ("BarcodeLookup", self._barcode_lookup, 0.75),
            ("Go-UPC", self._go_upc, 0.70),
            ("Buycott", self._buycott, 0.65),
            ("EANdata", self._eandata, 0.60),
            ("Lookify", self._lookify, 0.55),
            ("UPCDatabase", self._upcdatabase, 0.50),
            ("Brave Search", self._brave_search, 0.45),
            ("Google Search", self._google_search, 0.40),
        ]

        # Dynamic registry scrapers (hundreds of additional sources)
        registry_sources = self._get_registry_sources()
        registry_scrapers = [
            (src["name"], self._make_registry_scraper(src), src.get("weight", 0.30))
            for src in registry_sources
        ]

        # Deduplicate by source name (registry may duplicate core sources)
        seen_names = set()
        unique_scrapers = []
        for name, fn, weight in core_scrapers + registry_scrapers:
            if name not in seen_names:
                seen_names.add(name)
                unique_scrapers.append((name, fn, weight))

        # Sort by weight descending so high-confidence sources run first
        unique_scrapers.sort(key=lambda x: x[2], reverse=True)

        # Hard ceiling for safety
        max_sources = 300
        if len(unique_scrapers) > max_sources:
            unique_scrapers = unique_scrapers[:max_sources]

        def _is_real_success(r: Dict[str, Any]) -> bool:
            if not r.get("success"):
                return False
            name = str(r.get("name", "")).strip().lower()
            if not name or name in _BLOCKED_PRODUCT_NAMES:
                return False
            return True

        def _enough_success() -> bool:
            return sum(1 for r in results if _is_real_success(r)) >= MIN_SUCCESS_TO_STOP

        sem = asyncio.Semaphore(MAX_INFLIGHT_REQUESTS)

        async def bounded_scrape(name, fn):
            async with sem:
                return await self._safe_scrape(name, fn, upc)

        # Launch all tasks bounded by the semaphore; high-weight tasks start first
        pending = set()
        for name, fn, _ in unique_scrapers:
            task = asyncio.create_task(bounded_scrape(name, fn))
            pending.add(task)
            # Don't queue more than 2x the concurrency limit ahead of time
            if len(pending) >= MAX_INFLIGHT_REQUESTS * 2:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    r = task.result()
                    if isinstance(r, dict):
                        results.append(r)
                if _enough_success():
                    break

        # Process remaining tasks as they complete
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                r = task.result()
                if isinstance(r, dict):
                    results.append(r)

            elapsed = time.time() - start
            successful = sum(1 for r in results if r.get("success"))
            logger.debug(f"UPC {upc}: {successful}/{len(results)} successful, {elapsed:.1f}s")

            if _enough_success():
                logger.info(f"UPC {upc}: early stop after {len(results)} sources ({successful} successful)")
                for task in pending:
                    task.cancel()
                try:
                    await asyncio.gather(*pending, return_exceptions=True)
                except Exception:
                    pass
                break

            # Hard time budget for obscure products
            if elapsed > UPC_TIME_BUDGET_SECONDS:
                logger.info(f"UPC {upc}: time budget reached after {len(results)} sources")
                for task in pending:
                    task.cancel()
                try:
                    await asyncio.gather(*pending, return_exceptions=True)
                except Exception:
                    pass
                break

        elapsed = time.time() - start
        total_sources = len(results)
        successful = sum(1 for r in results if r.get("success"))
        logger.info(f"UPC {upc}: scraped {successful}/{total_sources} sources in {elapsed:.2f}s")

        return results
    
    def _get_registry_sources(self) -> List[Dict[str, Any]]:
        """Load scraper sources from registry file."""
        try:
            from backend.scraper_registry import ScraperRegistry
            registry = ScraperRegistry()
            return registry.get_enabled_sources()
        except Exception as e:
            logger.warning(f"Could not load scraper registry: {e}")
            return []
    
    def _make_registry_scraper(self, source_def: Dict[str, Any]):
        """Create a dynamic scraper function from a registry definition."""
        async def _scraper(upc: str) -> Dict[str, Any]:
            return await self._registry_scrape(source_def, upc)
        return _scraper
    
    async def _registry_scrape(self, source_def: Dict[str, Any], upc: str) -> Dict[str, Any]:
        """Dynamic scraper for registry-defined sources."""
        import json
        from bs4 import BeautifulSoup
        
        source_name = source_def.get("name", "Unknown")
        source_type = source_def.get("type", "html")
        url_template = source_def.get("url_template", "")
        method = source_def.get("method", "GET")
        timeout = source_def.get("timeout", 8)
        
        if not url_template:
            return self._fail(source_name, "", {}, "No URL template")
        
        # Build URL
        url = url_template.replace("{upc}", upc)
        
        # Handle auth placeholders
        requires_auth = source_def.get("requires_auth")
        if requires_auth and "{" in url:
            api_key = os.environ.get(requires_auth, "")
            if not api_key:
                return self._fail(source_name, url, {}, f"Auth key {requires_auth} not configured")
            url = url.replace(f"{{{requires_auth}}}", api_key)
        
        # Make request
        headers = self._next_headers()
        try:
            if method.upper() == "GET":
                response = await self._get_with_retry(url, headers=headers, timeout=timeout)
            else:
                response = await self._get_with_retry(url, headers=headers, timeout=timeout)
            
            data = response.json() if source_type == "api" else None
        except Exception as e:
            return self._fail(source_name, url, {}, str(e))
        
        # Extract data based on type
        if source_type == "api":
            return self._extract_api_data(source_def, data, upc, url)
        else:
            return self._extract_html_data(source_def, response.text, upc, url)
    
    def _extract_api_data(self, source_def: Dict[str, Any], data: Dict, upc: str, url: str) -> Dict[str, Any]:
        """Extract structured data from JSON API response."""
        source_name = source_def.get("name", "Unknown")
        extract = source_def.get("extract", {})
        
        def get_nested(data, path):
            """Safely navigate nested dict/list structure."""
            current = data
            for key in path:
                if current is None:
                    return None
                if isinstance(current, dict):
                    current = current.get(key)
                elif isinstance(current, list) and isinstance(key, int) and key < len(current):
                    current = current[key]
                else:
                    return None
            return current
        
        name = get_nested(data, extract.get("name", []))
        brand = get_nested(data, extract.get("brand", []))
        category = get_nested(data, extract.get("category", []))
        description = get_nested(data, extract.get("description", []))
        image_urls_raw = get_nested(data, extract.get("image_urls", []))
        
        # Handle image URLs (could be string, list, or dict)
        image_urls = []
        if isinstance(image_urls_raw, str):
            image_urls = [image_urls_raw] if _is_valid_image_url(image_urls_raw) else []
        elif isinstance(image_urls_raw, list):
            image_urls = [u for u in image_urls_raw if _is_valid_image_url(u)]
        elif isinstance(image_urls_raw, dict):
            # Sometimes images are in a dict with keys
            for v in image_urls_raw.values():
                if isinstance(v, str) and _is_valid_image_url(v):
                    image_urls.append(v)
        
        # Extract attributes
        attributes = {}
        attrs_def = extract.get("attributes", [])
        if attrs_def:
            attrs_data = get_nested(data, attrs_def)
            if isinstance(attrs_data, dict):
                attributes = attrs_data
        
        # Check success condition
        success_condition = source_def.get("success_condition")
        if success_condition:
            condition_field = success_condition[0]
            condition_value = success_condition[1]
            actual_value = get_nested(data, [condition_field])
            if actual_value != condition_value:
                return self._fail(source_name, url, data, f"Success condition not met: {condition_field}={actual_value}")
        
        if not name:
            return self._fail(source_name, url, data, "Product not found")
        
        return {
            "upc": upc, "source": source_name, "source_url": url,
            "name": name, "brand": brand, "category": category,
            "description": description, "image_urls": image_urls,
            "attributes": attributes, "raw": data,
            "success": True, "error": None,
        }
    
    def _extract_html_data(self, source_def: Dict[str, Any], html: str, upc: str, url: str) -> Dict[str, Any]:
        """Extract data from HTML response using CSS selectors."""
        source_name = source_def.get("name", "Unknown")
        selectors = source_def.get("selectors", {})
        
        soup = BeautifulSoup(html, "html.parser")
        
        def extract_field(selector_list):
            """Try multiple selectors until one finds content."""
            if not selector_list:
                return None
            for selector in selector_list:
                try:
                    # Handle attribute selectors like meta[property='og:title']
                    if "[" in selector and "=" in selector:
                        tag = selector.split("[")[0]
                        attr_part = selector.split("[", 1)[1].rstrip("]")
                        if "=" in attr_part:
                            attr_name, attr_value = attr_part.split("=", 1)
                            attr_value = attr_value.strip("'\"")
                            elem = soup.find(tag, {attr_name: attr_value})
                            if elem:
                                content = elem.get("content") or elem.get_text(strip=True)
                                if content:
                                    return content
                    else:
                        # Standard CSS selector
                        elem = soup.select_one(selector)
                        if elem:
                            text = elem.get_text(strip=True)
                            if text:
                                return text
                            # Try src for images
                            src = elem.get("src")
                            if src:
                                return src
                except Exception:
                    continue
            return None
        
        name = extract_field(selectors.get("name", []))
        brand = extract_field(selectors.get("brand", []))
        description = extract_field(selectors.get("description", []))
        image_url = extract_field(selectors.get("image_urls", []))
        
        image_urls = []
        if image_url and _is_valid_image_url(image_url):
            image_urls = [image_url]
        
        # Extract attributes from table rows
        attributes = {}
        attr_selectors = selectors.get("attributes", [])
        for attr_selector in attr_selectors:
            try:
                table = soup.select_one(attr_selector)
                if table:
                    for row in table.find_all("tr"):
                        cells = row.find_all(["td", "th"])
                        if len(cells) >= 2:
                            key = cells[0].get_text(strip=True).lower().replace(":", "").replace(" ", "_")
                            val = cells[1].get_text(strip=True)
                            if key and val:
                                attributes[key] = val
            except Exception:
                pass
        
        if not name:
            return self._fail(source_name, url, {}, "Product not found")
        
        return {
            "upc": upc, "source": source_name, "source_url": url,
            "name": name, "brand": brand, "category": None,
            "description": description, "image_urls": image_urls,
            "attributes": attributes, "raw": {"html_snippet": soup.get_text()[:500]},
            "success": True, "error": None,
        }

    async def _safe_scrape(self, name: str, scrape_fn, upc: str) -> Dict[str, Any]:
        """Wrap scraper in circuit breaker + try/except + timing."""
        start = time.time()
        try:
            cb = self._get_circuit(name)
            result = await cb.call(scrape_fn, upc)
            result["_elapsed_ms"] = round((time.time() - start) * 1000, 1)
            return result
        except Exception as e:
            elapsed = round((time.time() - start) * 1000, 1)
            logger.warning(f"Scraper {name} failed for {upc} ({elapsed}ms): {e}")
            return {
                "upc": upc,
                "source": name,
                "source_url": None,
                "name": None,
                "brand": None,
                "category": None,
                "description": None,
                "image_urls": [],
                "attributes": {},
                "raw": {},
                "success": False,
                "error": str(e),
                "_elapsed_ms": elapsed,
            }

    async def _open_food_facts(self, upc: str) -> Dict[str, Any]:
        url = f"https://world.openfoodfacts.org/api/v2/product/{upc}.json"
        response = await self._get_with_retry(url, timeout=12.0)
        data = response.json()

        if data.get("status") != 1 or "product" not in data:
            return self._fail("Open Food Facts", url, data, "Product not found")

        product = data["product"]
        image_urls = []
        for key in ["image_url", "image_front_url", "image_ingredients_url", "image_nutrition_url"]:
            if product.get(key) and _is_valid_image_url(product[key]):
                image_urls.append(product[key])

        category = None
        if product.get("categories"):
            cats = product["categories"].split(",")
            category = cats[0].strip() if cats else None

        attributes = {}
        for key in ["quantity", "packaging", "labels", "origins", "manufacturing_places", "ingredients_text"]:
            if product.get(key):
                attributes[key] = product[key]
        if product.get("nutriments"):
            attributes["nutriments"] = product["nutriments"]

        return {
            "upc": upc, "source": "Open Food Facts", "source_url": url,
            "name": product.get("product_name"), "brand": product.get("brands"),
            "category": category, "description": product.get("generic_name") or product.get("categories"),
            "image_urls": image_urls, "attributes": attributes, "raw": data,
            "success": True, "error": None,
        }

    async def _upcitemdb(self, upc: str) -> Dict[str, Any]:
        url = f"https://api.upcitemdb.com/prod/trial/lookup?upc={upc}"
        response = await self._get_with_retry(url, timeout=12.0)
        data = response.json()

        items = data.get("items", [])
        if not items:
            return self._fail("UPCItemDB", url, data, "No items found")

        item = items[0]
        image_urls = [u for u in item.get("images", []) if _is_valid_image_url(u)]

        attributes = {}
        for key in ["color", "size", "weight", "description", "lowest_recorded_price", "highest_recorded_price", "model", "title"]:
            if item.get(key):
                attributes[key] = item[key]

        return {
            "upc": upc, "source": "UPCItemDB", "source_url": url,
            "name": item.get("title"), "brand": item.get("brand"),
            "category": item.get("category"), "description": item.get("description"),
            "image_urls": image_urls, "attributes": attributes, "raw": data,
            "success": True, "error": None,
        }

    async def _barcode_lookup(self, upc: str) -> Dict[str, Any]:
        url = f"https://www.barcodelookup.com/{upc}"
        headers = self._next_headers()
        response = await self._get_with_retry(url, headers=headers, timeout=12.0)
        soup = BeautifulSoup(response.text, "html.parser")

        name = None
        title_tag = soup.find("h1", class_="product-name")
        if title_tag:
            name = title_tag.get_text(strip=True)
        else:
            title_tag = soup.find("title")
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                if " - " in title_text:
                    name = title_text.split(" - ")[0].strip()

        brand_tag = soup.find("span", class_="product-brand")
        brand = brand_tag.get_text(strip=True) if brand_tag else None

        desc_tag = soup.find("div", class_="product-description")
        description = desc_tag.get_text(strip=True) if desc_tag else None

        img_tag = soup.find("img", class_="product-image")
        image_urls = []
        if img_tag and img_tag.get("src") and _is_valid_image_url(img_tag["src"]):
            image_urls.append(img_tag["src"])

        attributes = {}
        details = soup.find("table", class_="product-details")
        if details:
            for row in details.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower().replace(":", "")
                    val = cells[1].get_text(strip=True)
                    if key and val:
                        attributes[key] = val

        if not name:
            return self._fail("BarcodeLookup", url, {}, "Product not found")

        return {
            "upc": upc, "source": "BarcodeLookup", "source_url": url,
            "name": name, "brand": brand, "category": None,
            "description": description, "image_urls": image_urls,
            "attributes": attributes, "raw": {"html_snippet": soup.get_text()[:500]},
            "success": True, "error": None,
        }

    async def _go_upc(self, upc: str) -> Dict[str, Any]:
        url = f"https://go-upc.com/search?q={upc}"
        headers = self._next_headers()
        response = await self._get_with_retry(url, headers=headers, timeout=12.0)
        soup = BeautifulSoup(response.text, "html.parser")

        name = None
        title_tag = soup.find("h1", class_="product-name")
        if title_tag:
            name = title_tag.get_text(strip=True)
        else:
            title_tag = soup.find("h1")
            if title_tag:
                name = title_tag.get_text(strip=True)

        brand_tag = soup.find("span", class_="product-brand")
        brand = brand_tag.get_text(strip=True) if brand_tag else None

        desc_tag = soup.find("div", class_="product-description")
        description = desc_tag.get_text(strip=True) if desc_tag else None

        img_tag = soup.find("img", class_="product-image")
        image_urls = []
        if img_tag and img_tag.get("src") and _is_valid_image_url(img_tag["src"]):
            image_urls.append(img_tag["src"])

        if not name:
            return self._fail("Go-UPC", url, {}, "Product not found")

        return {
            "upc": upc, "source": "Go-UPC", "source_url": url,
            "name": name, "brand": brand, "category": None,
            "description": description, "image_urls": image_urls,
            "attributes": {}, "raw": {"html_snippet": soup.get_text()[:500]},
            "success": True, "error": None,
        }

    async def _buycott(self, upc: str) -> Dict[str, Any]:
        url = f"https://www.buycott.com/upc/{upc}"
        headers = self._next_headers()
        response = await self._get_with_retry(url, headers=headers, timeout=12.0)
        soup = BeautifulSoup(response.text, "html.parser")

        meta_title = soup.find("meta", property="og:title")
        name = meta_title["content"].strip() if meta_title and meta_title.get("content") else None

        if not name:
            h1 = soup.find("h1")
            if h1:
                name = h1.get_text(strip=True)

        meta_desc = soup.find("meta", property="og:description")
        description = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None

        meta_img = soup.find("meta", property="og:image")
        image_urls = []
        if meta_img and meta_img.get("content") and _is_valid_image_url(meta_img["content"]):
            image_urls.append(meta_img["content"])

        brand = None
        if name:
            parts = name.split(" ", 1)
            if len(parts) > 1 and len(parts[0]) < 20:
                brand = parts[0]

        if not name or "not found" in name.lower() or "error" in name.lower():
            return self._fail("Buycott", url, {}, "Product not found")

        return {
            "upc": upc, "source": "Buycott", "source_url": url,
            "name": name, "brand": brand, "category": None,
            "description": description, "image_urls": image_urls,
            "attributes": {}, "raw": {"html_snippet": soup.get_text()[:500]},
            "success": True, "error": None,
        }

    async def _eandata(self, upc: str) -> Dict[str, Any]:
        url = f"https://eandata.com/lookup/{upc}"
        headers = self._next_headers()
        response = await self._get_with_retry(url, headers=headers, timeout=12.0)
        soup = BeautifulSoup(response.text, "html.parser")

        h1 = soup.find("h1")
        name = h1.get_text(strip=True) if h1 else None

        attributes = {}
        details = soup.find("div", class_="product-details")
        if details:
            for row in details.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower().replace(":", "")
                    val = cells[1].get_text(strip=True)
                    if key and val:
                        attributes[key] = val

        brand = attributes.get("brand") or attributes.get("manufacturer")

        if not name:
            return self._fail("EANdata", url, {}, "Product not found")

        return {
            "upc": upc, "source": "EANdata", "source_url": url,
            "name": name, "brand": brand, "category": None,
            "description": None, "image_urls": [],
            "attributes": attributes, "raw": {"html_snippet": soup.get_text()[:500]},
            "success": True, "error": None,
        }

    async def _lookify(self, upc: str) -> Dict[str, Any]:
        """Lookify barcode lookup."""
        url = f"https://lookify.io/barcode/{upc}"
        headers = self._next_headers()
        response = await self._get_with_retry(url, headers=headers, timeout=12.0)
        soup = BeautifulSoup(response.text, "html.parser")

        name = None
        title_tag = soup.find("h1")
        if title_tag:
            name = title_tag.get_text(strip=True)

        brand = None
        brand_tag = soup.find("span", class_=re.compile("brand"))
        if brand_tag:
            brand = brand_tag.get_text(strip=True)

        img_tag = soup.find("img", class_=re.compile("product|main"))
        image_urls = []
        if img_tag and img_tag.get("src") and _is_valid_image_url(img_tag["src"]):
            image_urls.append(img_tag["src"])

        if not name:
            return self._fail("Lookify", url, {}, "Product not found")

        return {
            "upc": upc, "source": "Lookify", "source_url": url,
            "name": name, "brand": brand, "category": None,
            "description": None, "image_urls": image_urls,
            "attributes": {}, "raw": {"html_snippet": soup.get_text()[:500]},
            "success": True, "error": None,
        }

    async def _upcdatabase(self, upc: str) -> Dict[str, Any]:
        """UPCDatabase.org lookup."""
        url = f"https://upcdatabase.org/code/{upc}"
        headers = self._next_headers()
        response = await self._get_with_retry(url, headers=headers, timeout=12.0)
        soup = BeautifulSoup(response.text, "html.parser")

        name = None
        title_tag = soup.find("h1")
        if title_tag:
            name = title_tag.get_text(strip=True)

        attributes = {}
        table = soup.find("table")
        if table:
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower().replace(":", "")
                    val = cells[1].get_text(strip=True)
                    if key and val:
                        attributes[key] = val

        brand = attributes.get("brand") or attributes.get("manufacturer") or attributes.get("company")

        if not name:
            return self._fail("UPCDatabase", url, {}, "Product not found")

        return {
            "upc": upc, "source": "UPCDatabase", "source_url": url,
            "name": name, "brand": brand, "category": None,
            "description": None, "image_urls": [],
            "attributes": attributes, "raw": {"html_snippet": soup.get_text()[:500]},
            "success": True, "error": None,
        }

    async def _brave_search(self, upc: str) -> Dict[str, Any]:
        api_key = os.environ.get("BRAVE_API_KEY", "")
        if api_key:
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {"X-Subscription-Token": api_key, "Accept": "application/json"}
            params = {"q": upc, "count": 5}
            response = await self._get_with_retry(url, headers=headers, params=params, timeout=10.0)
            data = response.json()
            results = data.get("web", {}).get("results", [])
            if not results:
                return self._fail("Brave Search", url, data, "No results")
            top = results[0]
            return {
                "upc": upc, "source": "Brave Search", "source_url": top.get("url"),
                "name": top.get("title", ""), "brand": None, "category": None,
                "description": top.get("description", ""), "image_urls": [],
                "attributes": {"search_results": len(results)}, "raw": data,
                "success": True, "error": None,
            }
        else:
            url = f"https://search.brave.com/search?q={upc}"
            headers = self._next_headers()
            response = await self._get_with_retry(url, headers=headers, timeout=10.0)
            soup = BeautifulSoup(response.text, "html.parser")
            result = soup.find("div", class_=re.compile("result"))
            name = description = result_url = None
            if result:
                title_tag = result.find(["h2", "h3", "a"])
                if title_tag:
                    name = title_tag.get_text(strip=True)
                snippet_tag = result.find("p")
                if snippet_tag:
                    description = snippet_tag.get_text(strip=True)
                link_tag = result.find("a", href=True)
                if link_tag:
                    result_url = link_tag["href"]
            if not name:
                return self._fail("Brave Search", url, {}, "No results")
            return {
                "upc": upc, "source": "Brave Search", "source_url": result_url or url,
                "name": name, "brand": None, "category": None,
                "description": description, "image_urls": [],
                "attributes": {}, "raw": {"html_snippet": soup.get_text()[:500]},
                "success": True, "error": None,
            }

    async def _google_search(self, upc: str) -> Dict[str, Any]:
        api_key = os.environ.get("GOOGLE_API_KEY", "")
        cx = os.environ.get("GOOGLE_CX", "")
        if api_key and cx:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {"key": api_key, "cx": cx, "q": upc, "num": 5}
            response = await self._get_with_retry(url, params=params, timeout=10.0)
            data = response.json()
            items = data.get("items", [])
            if not items:
                return self._fail("Google Search", url, data, "No results")
            top = items[0]
            return {
                "upc": upc, "source": "Google Search", "source_url": top.get("link"),
                "name": top.get("title", ""), "brand": None, "category": None,
                "description": top.get("snippet", ""), "image_urls": [],
                "attributes": {"search_results": len(items)}, "raw": data,
                "success": True, "error": None,
            }
        else:
            url = f"https://www.google.com/search?q={upc}"
            headers = self._next_headers()
            response = await self._get_with_retry(url, headers=headers, timeout=10.0)
            soup = BeautifulSoup(response.text, "html.parser")
            name = description = None
            for selector in ["h3", ".LC20lb", ".DKV0Md", "[data-ved] h3"]:
                tag = soup.select_one(selector)
                if tag:
                    name = tag.get_text(strip=True)
                    break
            for selector in [".VwiC3b", ".s3v94d", ".aCOpRe"]:
                tag = soup.select_one(selector)
                if tag:
                    description = tag.get_text(strip=True)
                    break
            if not name:
                return self._fail("Google Search", url, {}, "No results")
            return {
                "upc": upc, "source": "Google Search", "source_url": url,
                "name": name, "brand": None, "category": None,
                "description": description, "image_urls": [],
                "attributes": {}, "raw": {"html_snippet": soup.get_text()[:500]},
                "success": True, "error": None,
            }


    @staticmethod
    def _fail(source: str, url: str, raw: dict, error: str) -> Dict[str, Any]:
        return {
            "upc": None, "source": source, "source_url": url,
            "name": None, "brand": None, "category": None,
            "description": None, "image_urls": [], "attributes": {},
            "raw": raw, "success": False, "error": error,
        }
