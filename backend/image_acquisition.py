"""Required image acquisition pipeline for ShelfWise products.

The scraper/agent can legitimately fail to verify a marketplace-ready photo.
This module adds a second stage whose job is stricter: every UPC gets a real
image candidate when the web returns one, with review metadata when confidence
is not high enough for automatic publishing.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx

from backend.image_search import (
    direct_listing_urls_for_upc,
    scrape_product_listing_page,
    search_product_images,
    search_product_listing_pages,
    search_structured_marketplace_listings,
)
from backend.image_verifier import select_verified_images

logger = logging.getLogger("shelfwise.image_acquisition")


GENERIC_NAME_MARKERS = {
    "unknown product",
    "product not found",
    "check digit",
    "barcode lookup",
    "upc lookup",
}


def _is_generic_name(value: Optional[str], upc: str) -> bool:
    if not value:
        return True
    normalized = value.strip().lower()
    if normalized in GENERIC_NAME_MARKERS:
        return True
    return normalized in {f"product {upc}", f"item {upc}"} or normalized.endswith(f" item {upc}")


def _is_weak_text(value: Optional[str]) -> bool:
    if not value:
        return True
    normalized = value.strip().lower()
    return (
        normalized in {"unknown", "unknown product", "n/a", "none", "product not found"}
        or normalized.startswith("no reliable")
        or normalized.startswith("no information")
        or normalized.startswith("this product's details are currently unavailable")
        or normalized.startswith("product information for upc")
    )


def _candidate_key(candidate: Dict[str, Any]) -> str:
    return str(candidate.get("url", "")).strip()


def _dedupe_candidates(candidates: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped = []
    for candidate in candidates:
        url = _candidate_key(candidate)
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(candidate)
    return deduped


def _record_acquisition_source(product: Dict[str, Any], source: str, kind: str, detail: Optional[str] = None) -> None:
    if not source:
        return
    attrs = product.setdefault("attributes", {})
    sources = attrs.setdefault("image_acquisition_sources", [])
    key = (source, kind, detail or "")
    for existing in sources:
        if (existing.get("source"), existing.get("kind"), existing.get("detail") or "") == key:
            existing["count"] = int(existing.get("count", 1)) + 1
            return
    sources.append({"source": source, "kind": kind, "detail": detail, "count": 1})


def _source_image_candidates(raw_sources: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for source in raw_sources or []:
        source_name = source.get("source") or "Source Image"
        for url in source.get("image_urls") or []:
            if url:
                candidates.append({"url": url, "source": source_name, "score": 0.75})
    return _dedupe_candidates(candidates)


def _build_image_queries(product: Dict[str, Any], seed_data: Optional[Dict[str, Any]] = None) -> List[str]:
    upc = str(product.get("upc") or "").strip()
    name = str(product.get("name") or "").strip()
    brand = str(product.get("brand") or "").strip()
    category = str(product.get("category") or "").strip()
    seed_name = str((seed_data or {}).get("name") or "").strip()

    queries: List[str] = []
    if upc:
        queries.extend(
            [
                f'"{upc}" product image',
                f'"{upc}" UPC product photo',
                f'"{upc}" package front',
                f'"{upc}" site:walmart.com OR site:target.com OR site:ebay.com',
                f'"{upc}" site:amazon.com OR site:samsclub.com OR site:costco.com',
            ]
        )
    if name and not _is_generic_name(name, upc):
        queries.append(" ".join(part for part in [brand, name, "product image"] if part))
    if seed_name and seed_name != name:
        queries.append(" ".join(part for part in [brand, seed_name, "product image"] if part))
    if category and upc:
        queries.append(f'"{upc}" {category} product package')
        queries.append(f"{category} {upc} retailer listing")

    deduped = []
    seen = set()
    for query in queries:
        normalized = " ".join(query.split())
        if normalized and normalized.lower() not in seen:
            seen.add(normalized.lower())
            deduped.append(normalized)
    return deduped[:5]


async def _search_query(
    query: str,
    client: Optional[httpx.AsyncClient],
    max_results: int,
    timeout: float,
) -> List[Dict[str, Any]]:
    try:
        results = await asyncio.wait_for(
            search_product_images(query, max_results=max_results, client=client),
            timeout=timeout,
        )
    except Exception as exc:
        logger.info("Image query failed for %r: %s", query, exc)
        return []

    candidates = []
    for idx, result in enumerate(results):
        url = result.get("url")
        if not url:
            continue
        candidates.append(
            {
                "url": url,
                "source": result.get("source") or "Image Search",
                "score": max(0.15, 0.5 - idx * 0.03),
                "query": query,
            }
        )
    return candidates


async def _scrape_listing_evidence(
    query: str,
    client: Optional[httpx.AsyncClient],
    max_pages: int,
    timeout: float,
) -> List[Dict[str, Any]]:
    try:
        pages = await asyncio.wait_for(
            search_product_listing_pages(query, max_results=max_pages, client=client),
            timeout=timeout,
        )
    except Exception as exc:
        logger.info("Listing search failed for %r: %s", query, exc)
        return []

    evidence: List[Dict[str, Any]] = []
    for page in pages[:max_pages]:
        url = page.get("url")
        if not url:
            continue
        try:
            listing = await asyncio.wait_for(scrape_product_listing_page(url, client=client), timeout=timeout)
        except Exception as exc:
            logger.info("Listing scrape failed for %s: %s", url, exc)
            continue
        if listing:
            evidence.append(listing)
    return evidence


async def _scrape_direct_upc_evidence(
    upc: str,
    client: Optional[httpx.AsyncClient],
    max_pages: int,
    timeout: float,
) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    for url in direct_listing_urls_for_upc(upc)[:max_pages]:
        try:
            listing = await asyncio.wait_for(scrape_product_listing_page(url, client=client), timeout=timeout)
        except Exception as exc:
            logger.info("Direct UPC listing scrape failed for %s: %s", url, exc)
            continue
        if listing:
            evidence.append(listing)
    return evidence


def _apply_listing_evidence(product: Dict[str, Any], evidence: List[Dict[str, Any]], trace: List[str]) -> None:
    for listing in evidence:
        source = listing.get("source") or "Listing"
        if listing.get("name") and (
            _is_weak_text(product.get("name")) or _is_generic_name(str(product.get("name") or ""), str(product.get("upc") or ""))
        ):
            product["name"] = listing["name"]
            trace.append(f"Listing evidence: title filled from {source}")
        if listing.get("brand") and _is_weak_text(product.get("brand")):
            product["brand"] = listing["brand"]
            trace.append(f"Listing evidence: brand filled from {source}")
        if listing.get("category") and _is_weak_text(product.get("category")):
            product["category"] = listing["category"]
            trace.append(f"Listing evidence: category filled from {source}")
        if listing.get("description") and _is_weak_text(product.get("description")):
            product["description"] = listing["description"]
            trace.append(f"Listing evidence: description filled from {source}")

        fields = [
            field
            for field in ("name", "brand", "category", "description", "images")
            if listing.get(field) or (field == "images" and listing.get("image_urls"))
        ]
        if fields:
            citations = product.setdefault("citations", [])
            source_url = listing.get("source_url")
            if not any(c.get("source_url") == source_url for c in citations if isinstance(c, dict)):
                citations.append(
                    {
                        "source": source,
                        "source_url": source_url,
                        "fields": fields,
                        "confidence": 0.45,
                        "note": "Retailer or marketplace listing evidence",
                    }
                )


async def acquire_required_product_images(
    product: Dict[str, Any],
    *,
    raw_sources: Optional[Iterable[Dict[str, Any]]] = None,
    seed_data: Optional[Dict[str, Any]] = None,
    client: Optional[httpx.AsyncClient] = None,
    max_images: int = 5,
    per_query_timeout: float = 8.0,
) -> Tuple[List[Dict[str, Any]], Optional[str], List[str]]:
    """Return image records, best URL, and trace lines for a product.

    The function first tries strict verification. If no image passes, it still
    returns the best real web candidates marked as `needs_review`, so the UI has
    something concrete for every UPC before generated fallback is considered.
    """
    upc = str(product.get("upc") or "")
    trace: List[str] = []

    source_candidates = _source_image_candidates(raw_sources or [])
    if source_candidates:
        trace.append(f"Image acquisition: collected {len(source_candidates)} source image candidates")
        for candidate in source_candidates:
            _record_acquisition_source(product, candidate.get("source", "Source Image"), "scraper-image", candidate.get("url"))

    search_candidates: List[Dict[str, Any]] = []
    listing_evidence: List[Dict[str, Any]] = []
    direct_evidence = await _scrape_direct_upc_evidence(upc, client, max_pages=8, timeout=per_query_timeout)
    if direct_evidence:
        trace.append(f"Image acquisition: direct UPC probes produced {len(direct_evidence)} listing evidence pages")
        listing_evidence.extend(direct_evidence)
        for listing in direct_evidence:
            _record_acquisition_source(product, listing.get("source", "Direct UPC Listing"), "direct-listing", listing.get("source_url"))
            for url in listing.get("image_urls") or []:
                search_candidates.append(
                    {
                        "url": url,
                        "source": listing.get("source") or "Direct UPC Listing",
                        "source_url": listing.get("source_url"),
                        "score": 0.66,
                        "query": upc,
                    }
                )

    for query in _build_image_queries(product, seed_data):
        try:
            structured = await asyncio.wait_for(
                search_structured_marketplace_listings(query, max_results=3, client=client),
                timeout=per_query_timeout,
            )
        except Exception as exc:
            logger.info("Structured marketplace search failed for %r: %s", query, exc)
            structured = []
        if structured:
            trace.append(f"Image acquisition: query '{query}' produced {len(structured)} structured marketplace listings")
            listing_evidence.extend(structured)
            for listing in structured:
                _record_acquisition_source(product, listing.get("source", "Structured Marketplace"), "marketplace-api", listing.get("source_url"))
                for url in listing.get("image_urls") or []:
                    search_candidates.append(
                        {
                            "url": url,
                            "source": listing.get("source") or "Marketplace Image",
                            "source_url": listing.get("source_url"),
                            "score": 0.7,
                            "query": query,
                        }
                    )

        listings = await _scrape_listing_evidence(query, client, max_pages=3, timeout=per_query_timeout)
        if listings:
            trace.append(f"Image acquisition: query '{query}' produced {len(listings)} listing evidence pages")
            listing_evidence.extend(listings)
            for listing in listings:
                _record_acquisition_source(product, listing.get("source", "Listing Search"), "listing-page", listing.get("source_url"))
                for url in listing.get("image_urls") or []:
                    search_candidates.append(
                        {
                            "url": url,
                            "source": listing.get("source") or "Listing Image",
                            "source_url": listing.get("source_url"),
                            "score": 0.62,
                            "query": query,
                        }
                    )

        found = await _search_query(query, client, max_results=max_images, timeout=per_query_timeout)
        if found:
            trace.append(f"Image acquisition: query '{query}' returned {len(found)} candidates")
            for candidate in found:
                _record_acquisition_source(product, candidate.get("source", "Image Search"), "image-search", query)
        search_candidates.extend(found)
        if len(_dedupe_candidates(source_candidates + search_candidates)) >= max_images * 2:
            break

    if listing_evidence:
        _apply_listing_evidence(product, listing_evidence, trace)

    candidates = _dedupe_candidates(source_candidates + search_candidates)
    if not candidates:
        trace.append("Image acquisition: no real image candidates found")
        return [], None, trace

    product_name = product.get("name")
    product_brand = product.get("brand")
    try:
        verified, best_url = await select_verified_images(
            candidates,
            product_name=product_name,
            product_brand=product_brand,
            max_images=max_images,
            client=client,
        )
    except Exception as exc:
        logger.info("Image verification failed for UPC %s: %s", upc, exc)
        verified, best_url = [], None

    if verified and best_url:
        trace.append(f"Image acquisition: selected {len(verified)} verified images")
        return verified, best_url, trace

    review_images = []
    for candidate in candidates[:max_images]:
        review_images.append(
            {
                "url": candidate["url"],
                "source": candidate.get("source") or "Image Search Candidate",
                "score": candidate.get("score", 0.25),
                "verified": False,
                "needs_review": True,
                "query": candidate.get("query"),
                "source_url": candidate.get("source_url"),
            }
        )

    trace.append(f"Image acquisition: attached {len(review_images)} real image candidates for review")
    return review_images, review_images[0]["url"], trace
