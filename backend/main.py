#!/usr/bin/env python3
"""ShelfWise API - Main FastAPI Application (Optimized).

AI Product Portfolio Builder for Small Businesses.
"""

import os
import shutil
import sys
import uuid
from pathlib import Path as FilePath

_project_root = FilePath(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv

load_dotenv(_project_root / ".env")

import asyncio
import csv
import html
import io
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import httpx
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Path, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.cache import upc_cache
from backend.csv_parser import parse_pos_csv, preview_pos_csv
from backend.database import (
    count_products,
    create_job,
    delete_all_products,
    get_all_products,
    get_job,
    get_product,
    get_stats,
    init_db,
    search_products,
    update_job,
    upsert_product,
)
from backend.foundry_agent import ProductReasoningAgent
from backend.foundry_iq import FoundryIQService, get_foundry_iq_service
from backend.image_acquisition import acquire_required_product_images
from backend.models import ConsolidatedProduct, ExportRequest, UPCBatchRequest
from backend.scraper import SOURCE_WEIGHTS, UPCScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shelfwise")

DEMO_UPCS = ["049000050103", "022000020806", "012000001307"]
http_client: Optional[httpx.AsyncClient] = None
scraper: Optional[UPCScraper] = None
agent: Optional[ProductReasoningAgent] = None
foundry_iq: Optional[FoundryIQService] = None

# Request timing metrics
_request_times: List[float] = []
_scrape_times: List[float] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, scraper, foundry_iq, agent
    init_db()
    http_client = httpx.AsyncClient(
        timeout=30.0, limits=httpx.Limits(max_connections=300, max_keepalive_connections=100)
    )
    scraper = UPCScraper(http_client)
    foundry_iq = get_foundry_iq_service(db_path="shelfwise.db")
    agent = ProductReasoningAgent(foundry_iq_service=foundry_iq)
    logger.info(
        "ShelfWise API started (optimized) | Foundry IQ: %s",
        "azure" if foundry_iq.is_real_integration else "local_simulation",
    )
    logger.info(
        "Foundry reasoning clients | azure-ai-inference=%s azure-ai-projects=%s openai-compatible=%s",
        agent._azure_client is not None,
        agent._azure_projects_client is not None,
        agent._openai_client is not None,
    )
    yield
    if http_client:
        await http_client.aclose()
    logger.info("ShelfWise API stopped")


app = FastAPI(
    title="ShelfWise API",
    description="AI Product Portfolio Builder for Small Businesses",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:3000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/app", StaticFiles(directory=frontend_path, html=True), name="frontend")

# Uploaded product images
uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

FALLBACK_IMAGE_COLORS = {
    "baby care": ("#f5d0fe", "#7e22ce"),
    "beverages": ("#bfdbfe", "#1d4ed8"),
    "boxed meals": ("#fed7aa", "#c2410c"),
    "breakfast": ("#fde68a", "#a16207"),
    "canned goods": ("#bbf7d0", "#15803d"),
    "condiments": ("#fecaca", "#b91c1c"),
    "crackers": ("#fde68a", "#92400e"),
    "frozen": ("#cffafe", "#0e7490"),
    "household": ("#dbeafe", "#2563eb"),
    "personal care": ("#e9d5ff", "#7c3aed"),
    "pet care": ("#dcfce7", "#16a34a"),
    "snacks": ("#fef3c7", "#d97706"),
    "spreads": ("#ffedd5", "#ea580c"),
}


def get_scraper() -> UPCScraper:
    if scraper is None:
        raise RuntimeError("Scraper not initialized")
    return scraper


def _is_local_plu(upc: str) -> bool:
    """Return True for locally-assigned / variable-weight codes (e.g. starting with 2).

    GS1 prefixes 2 and 02 are typically store/department-specific PLUs, not
    globally registered products, so public UPC databases rarely have data.
    """
    return bool(upc) and upc.startswith("2")


def _fallback_image_for_product(upc: str, category: Optional[str], name: Optional[str]) -> Dict[str, Any]:
    """Create a local review-placeholder image for POS-only products."""
    category_label = (category or "Product").strip() or "Product"
    name_label = (name or f"UPC {upc}").strip() or f"UPC {upc}"
    bg, fg = FALLBACK_IMAGE_COLORS.get(category_label.lower(), ("#f5f5f7", "#1d1d1f"))
    filename = f"review-{upc}.svg"
    filepath = os.path.join(uploads_dir, filename)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900" viewBox="0 0 900 900">
  <rect width="900" height="900" rx="56" fill="{bg}"/>
  <rect x="72" y="72" width="756" height="756" rx="44" fill="#ffffff" opacity="0.88"/>
  <text x="450" y="330" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="58" font-weight="700" fill="{fg}">{html.escape(category_label)}</text>
  <text x="450" y="420" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="34" font-weight="600" fill="#1d1d1f">{html.escape(name_label[:34])}</text>
  <text x="450" y="500" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="28" fill="#6e6e73">UPC {html.escape(upc)}</text>
  <text x="450" y="590" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="25" fill="#86868b">Review image needed</text>
</svg>
"""
    FilePath(filepath).write_text(svg, encoding="utf-8")
    return {
        "url": f"/uploads/{filename}",
        "source": "ShelfWise Review Placeholder",
        "score": 0.2,
        "verified": False,
        "generated": True,
        "width": 900,
        "height": 900,
    }


def _ensure_visible_image(consolidated: Dict[str, Any]) -> None:
    """Ensure the UI has a visual card even when public sources lack product photos."""
    images = [img for img in consolidated.get("images", []) if isinstance(img, dict) and img.get("url")]
    if images or consolidated.get("image_url"):
        return
    placeholder = _fallback_image_for_product(
        str(consolidated.get("upc", "")),
        consolidated.get("category"),
        consolidated.get("name"),
    )
    consolidated["images"] = [placeholder]
    consolidated["image_url"] = placeholder["url"]
    consolidated.setdefault("reasoning_trace", []).append(
        "Added ShelfWise review placeholder because no verified public product image was found"
    )


def _build_from_seed(upc: str, seed: Dict[str, Any]) -> Dict[str, Any]:
    """Build a consolidated product directly from POS CSV seed data.

    Used for local PLUs and other codes where public sources are unlikely to
    have a match. Still produces the same record shape as scraped products.
    """
    return {
        "upc": upc,
        "name": seed.get("name") or f"Product {upc}",
        "brand": seed.get("brand"),
        "category": seed.get("category"),
        "description": seed.get("description") or f"Product information for UPC {upc}",
        "image_url": None,
        "images": [],
        "attributes": {"pos_price": seed["price"]} if "price" in seed else {},
        "confidence": 0.75,
        "status": "complete",
        "citations": [
            {
                "source": "POS Upload",
                "source_url": None,
                "fields": [k for k in ("name", "brand", "category", "description", "price") if seed.get(k)],
                "confidence": 0.75,
                "note": "Seed data from uploaded POS CSV",
            }
        ],
        "reasoning_trace": [f"Built record from POS CSV seed data for local PLU {upc}"],
        "foundry_enriched": False,
        "foundry_sdk": None,
    }


def _is_weak_product_value(value: Any) -> bool:
    """Return True for placeholder scraper/LLM values that POS seed data should replace."""
    if value is None:
        return True
    normalized = str(value).strip().lower()
    return (
        normalized in {"", "unknown", "unknown product", "n/a", "none", "check digit", "product not found"}
        or normalized.startswith("no reliable")
        or normalized.startswith("no information")
        or normalized.startswith("this product's details are currently unavailable")
    )


def _merge_seed_data(
    consolidated: Dict[str, Any],
    seed: Optional[Dict[str, Any]],
    prefer_seed: bool = False,
) -> Dict[str, Any]:
    """Merge CSV seed data into a consolidated product as fallback/enrichment.

    When prefer_seed=True (e.g. local PLUs), seed values override scraper values.
    Otherwise scraper data wins and seed fills gaps. Price is always added.
    """
    if not seed:
        return consolidated

    for field in ("name", "brand", "category", "description"):
        if seed.get(field):
            if prefer_seed or _is_weak_product_value(consolidated.get(field)):
                consolidated[field] = seed[field]

    category = seed.get("category")
    upc = consolidated.get("upc", "")
    if category and _is_weak_product_value(consolidated.get("name")):
        consolidated["name"] = f"{category} item {upc}".strip()
    if category and _is_weak_product_value(consolidated.get("description")):
        consolidated["description"] = f"{category} product imported from POS UPC {upc}."

    if "price" in seed:
        consolidated.setdefault("attributes", {})["pos_price"] = seed["price"]

    seed_fields = [k for k in ("name", "brand", "category", "description", "price") if seed.get(k)]
    if seed_fields:
        citations = consolidated.setdefault("citations", [])
        if not any(c.get("source") == "POS Upload" for c in citations if isinstance(c, dict)):
            citations.append(
                {
                    "source": "POS Upload",
                    "source_url": None,
                    "fields": seed_fields,
                    "confidence": 0.55,
                    "note": "Seed data from uploaded POS CSV",
                }
            )
        trace = consolidated.setdefault("reasoning_trace", [])
        trace.append("Merged POS CSV seed data")

    if seed.get("image_urls"):
        existing = {img.get("url") for img in consolidated.get("images", [])}
        for url in seed["image_urls"]:
            if url and url not in existing:
                consolidated.setdefault("images", []).append({"url": url, "source": "POS Upload", "score": 0.5})
                existing.add(url)

    return consolidated


# ---------------------------------------------------------------------------
# Background task: process a single UPC
# ---------------------------------------------------------------------------
async def process_upc(upc: str, job_id: str, seed_data: Optional[Dict[str, Any]] = None):
    try:
        raw_data_list: List[Dict[str, Any]] = []
        update_job(job_id, "queued", -1)
        update_job(job_id, "running", 1)

        # Check cache first
        cached = upc_cache.get(upc)
        if cached:
            logger.info(f"UPC {upc}: cache hit")
            product = ConsolidatedProduct(**cached)
            upsert_product(product)
            update_job(job_id, "running", -1)
            update_job(job_id, "completed", 1)
            return

        # Fast path for local PLUs with seed data: public UPC databases won't
        # have these, so build directly from the POS CSV to keep demos fast.
        if _is_local_plu(upc) and seed_data and seed_data.get("name"):
            logger.info(f"UPC {upc}: local PLU fast path using seed data")
            consolidated_dict = _build_from_seed(upc, seed_data)
        else:
            start = time.time()
            s = get_scraper()
            try:
                # Cap total scrape time so slow registry sources don't stall demos.
                # If we have seed data, fall back to it instead of failing.
                raw_data_list = await asyncio.wait_for(s.scrape_all(upc), timeout=15.0)
            except asyncio.TimeoutError:
                logger.warning(f"UPC {upc}: scrape timed out after 15s")
                if seed_data and seed_data.get("name"):
                    consolidated_dict = _build_from_seed(upc, seed_data)
                    consolidated_dict["reasoning_trace"].append("Scrape timed out; used POS CSV seed data")
                    logger.info(f"UPC {upc}: falling back to seed data after timeout")
                    scrape_elapsed = time.time() - start
                    _scrape_times.append(scrape_elapsed)
                    consolidated_dict = _merge_seed_data(consolidated_dict, seed_data, prefer_seed=True)
                    _ensure_visible_image(consolidated_dict)
                    logger.info(f"UPC {upc}: consolidated with confidence {consolidated_dict.get('confidence', 0)}")
                    product = ConsolidatedProduct(**consolidated_dict)
                    upsert_product(product)
                    upc_cache.set(upc, consolidated_dict)
                    update_job(job_id, "running", -1)
                    update_job(job_id, "completed", 1)
                    return
                raw_data_list = []
            scrape_elapsed = time.time() - start
            _scrape_times.append(scrape_elapsed)
            logger.info(f"UPC {upc}: scraped {len(raw_data_list)} sources in {scrape_elapsed:.2f}s")

            consolidated_dict = await agent.consolidate(upc, raw_data_list)
            consolidated_dict = _merge_seed_data(consolidated_dict, seed_data, prefer_seed=_is_local_plu(upc))

        logger.info(f"UPC {upc}: consolidated with confidence {consolidated_dict.get('confidence', 0)}")

        # Required image acquisition: source images, retailer/marketplace pages,
        # UPC image search, then review-marked real candidates before fallback.
        if not consolidated_dict.get("image_url"):
            try:
                acquired_images, best_url, image_trace = await acquire_required_product_images(
                    consolidated_dict,
                    raw_sources=raw_data_list,
                    seed_data=seed_data,
                    client=http_client,
                    max_images=5,
                )
                consolidated_dict.setdefault("reasoning_trace", []).extend(image_trace)
                if acquired_images and best_url:
                    consolidated_dict["images"] = acquired_images
                    consolidated_dict["image_url"] = best_url
                    if any(img.get("needs_review") for img in acquired_images if isinstance(img, dict)):
                        consolidated_dict.setdefault("citations", []).append(
                            {
                                "source": "Image Acquisition",
                                "source_url": best_url,
                                "fields": ["images"],
                                "confidence": 0.35,
                                "note": "Best real image candidate found; requires user review",
                            }
                        )
                    logger.info(
                        "UPC %s: acquired %s images; best=%s",
                        upc,
                        len(acquired_images),
                        best_url,
                    )
            except Exception as e:
                logger.warning(f"UPC {upc}: required image acquisition failed: {e}")

        _ensure_visible_image(consolidated_dict)

        product = ConsolidatedProduct(**consolidated_dict)
        upsert_product(product)
        upc_cache.set(upc, consolidated_dict)

        # Ingest into Foundry IQ knowledge graph
        try:
            if foundry_iq:
                foundry_iq.knowledge_graph.build_from_product(consolidated_dict)
                logger.info(f"UPC {upc}: ingested into Foundry IQ knowledge graph")
        except Exception as e:
            logger.warning(f"UPC {upc}: knowledge graph ingestion failed: {e}")

        update_job(job_id, "running", -1)
        update_job(job_id, "completed", 1)

    except Exception as e:
        logger.error(f"Error processing UPC {upc}: {e}")
        update_job(job_id, "running", -1)
        update_job(job_id, "failed", 1)
        try:
            error_product = ConsolidatedProduct(
                upc=upc,
                name=f"Error: {upc}",
                description=f"Failed to process UPC {upc}: {str(e)}",
                confidence=0.0,
                status="error",
                reasoning_trace=[f"Error during processing: {str(e)}"],
            )
            upsert_product(error_product)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------


@app.get("/")
async def root():
    return {
        "name": "ShelfWise",
        "version": "1.1.0",
        "description": "AI Product Portfolio Builder for Small Businesses",
        "status": "ok",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "App info"},
            {"path": "/app", "method": "GET", "description": "Web application"},
            {"path": "/api/demo", "method": "GET", "description": "Load demo products"},
            {"path": "/api/batch", "method": "POST", "description": "Submit UPCs for processing"},
            {
                "path": "/api/upload-csv",
                "method": "POST",
                "description": "Upload POS CSV with auto-detected UPC column",
            },
            {"path": "/api/upload-csv/preview", "method": "POST", "description": "Preview POS CSV before processing"},
            {"path": "/api/products", "method": "GET", "description": "Get all products"},
            {"path": "/api/products/{upc}", "method": "GET", "description": "Get single product"},
            {"path": "/api/export", "method": "POST", "description": "Export portfolio"},
            {"path": "/api/jobs/{job_id}", "method": "GET", "description": "Get job status"},
            {"path": "/api/stats", "method": "GET", "description": "Portfolio analytics"},
            {"path": "/api/search", "method": "GET", "description": "Search products"},
            {"path": "/api/metrics", "method": "GET", "description": "Performance metrics"},
            {"path": "/api/health", "method": "GET", "description": "Health check"},
        ],
    }


DEMO_PRODUCTS = [
    {
        "upc": "049000050103",
        "name": "Coca-Cola Classic",
        "brand": "Coca-Cola",
        "category": "Colas",
        "description": "Coca-Cola Classic - The original and refreshing taste. 2 liter bottle. Perfect for parties, gatherings, and everyday enjoyment.",
        "image_url": "https://images.openfoodfacts.org/images/products/004/900/005/0103/front_en.96.400.jpg",
        "images": [
            {
                "url": "https://images.openfoodfacts.org/images/products/004/900/005/0103/front_en.96.400.jpg",
                "source": "Open Food Facts",
                "score": 0.9,
            },
            {"url": "https://pics.walgreens.com/prodimg/416899/450.jpg", "source": "UPCItemDB", "score": 0.85},
        ],
        "attributes": {"size": "2 Liter", "flavor": "Original", "container": "Bottle", "color": "Red"},
        "confidence": 0.95,
        "status": "complete",
        "citations": [
            {
                "source": "Open Food Facts",
                "source_url": "https://world.openfoodfacts.org/api/v2/product/049000050103.json",
                "fields": ["name", "brand", "category", "images", "attributes"],
                "confidence": 0.9,
                "note": "Primary source with full product data",
            },
            {
                "source": "UPCItemDB",
                "source_url": "https://api.upcitemdb.com/prod/trial/lookup?upc=049000050103",
                "fields": ["name", "brand", "images"],
                "confidence": 0.85,
                "note": "Confirmed name and brand",
            },
        ],
        "reasoning_trace": [
            "Starting consolidation for UPC 049000050103",
            "Weighted 4 sources: Open Food Facts(0.90), UPCItemDB(0.85), Go-UPC(0.30), Buycott(0.30)",
            "Resolved name: 'Coca-Cola Classic' from ['Open Food Facts', 'UPCItemDB']",
            "Resolved brand: 'Coca-Cola' from ['Open Food Facts']",
            "Resolved category: 'Colas' from ['Open Food Facts']",
            "Merged 4 attributes from all sources",
            "Generated description (112 chars)",
            "Selected 2 images, best: True",
            "Computed confidence: 0.95",
            "Generated 2 citations",
            "Status: complete",
        ],
    },
    {
        "upc": "022000020806",
        "name": "M&M's Milk Chocolate",
        "brand": "Mars",
        "category": "Candy & Chocolate",
        "description": "M&M's Milk Chocolate - Colorful candy-coated chocolates in a convenient sharing size bag. A classic American snack since 1941.",
        "image_url": "https://target.scene7.com/is/image/Target/GUEST_3d2ee4ac-ace5-4e21-86c2-575d2f5a4f11?wid=488&hei=488&fmt=pjpeg",
        "images": [
            {
                "url": "https://target.scene7.com/is/image/Target/GUEST_3d2ee4ac-ace5-4e21-86c2-575d2f5a4f11?wid=488&hei=488&fmt=pjpeg",
                "source": "Target",
                "score": 0.8,
            },
            {
                "url": "https://i5.walmartimages.com/asr/5e0e2e2e-2e2e-2e2e-2e2e-2e2e2e2e2e2e_1.2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e.jpeg",
                "source": "Walmart",
                "score": 0.75,
            },
        ],
        "attributes": {"size": "1.69 oz", "flavor": "Milk Chocolate", "container": "Bag", "type": "Candy"},
        "confidence": 0.92,
        "status": "complete",
        "citations": [
            {
                "source": "UPCItemDB",
                "source_url": "https://api.upcitemdb.com/prod/trial/lookup?upc=022000020806",
                "fields": ["name", "brand", "category", "images"],
                "confidence": 0.85,
                "note": "Full product record with images",
            },
            {
                "source": "Buycott",
                "source_url": "https://www.buycott.com/upc/022000020806",
                "fields": ["name", "brand"],
                "confidence": 0.7,
                "note": "Confirmed brand ownership",
            },
        ],
        "reasoning_trace": [
            "Starting consolidation for UPC 022000020806",
            "Weighted 3 sources: UPCItemDB(0.85), Buycott(0.70), Go-UPC(0.30)",
            "Resolved name: 'M&M's Milk Chocolate' from ['UPCItemDB']",
            "Resolved brand: 'Mars' from ['UPCItemDB', 'Buycott']",
            "Resolved category: 'Candy & Chocolate' from ['UPCItemDB']",
            "Merged 4 attributes from all sources",
            "Generated description (108 chars)",
            "Selected 2 images, best: True",
            "Computed confidence: 0.92",
            "Generated 2 citations",
            "Status: complete",
        ],
    },
    {
        "upc": "012000001307",
        "name": "Pepsi Light",
        "brand": "Pepsi",
        "category": "Soda",
        "description": "Pepsi Light - Refreshing diet cola with zero sugar and zero calories. 20 fl oz bottle.",
        "image_url": "https://images.openfoodfacts.org/images/products/001/200/000/1307/front_fr.5.400.jpg",
        "images": [
            {
                "url": "https://images.openfoodfacts.org/images/products/001/200/000/1307/front_fr.5.400.jpg",
                "source": "Open Food Facts",
                "score": 0.9,
            },
            {
                "url": "https://i5.walmartimages.com/asr/c0294df7-bb4a-4545-96a4-548993338765_1.99f18eeb42d60ab95f50a7ae7fcf25d3.jpeg",
                "source": "Walmart",
                "score": 0.85,
            },
        ],
        "attributes": {"size": "20 fl oz", "flavor": "Diet Cola", "container": "Bottle", "calories": "0"},
        "confidence": 0.93,
        "status": "complete",
        "citations": [
            {
                "source": "Open Food Facts",
                "source_url": "https://world.openfoodfacts.org/api/v2/product/012000001307.json",
                "fields": ["name", "brand", "images", "attributes"],
                "confidence": 0.9,
                "note": "Primary source with nutrition data",
            },
            {
                "source": "UPCItemDB",
                "source_url": "https://api.upcitemdb.com/prod/trial/lookup?upc=012000001307",
                "fields": ["name", "brand", "category"],
                "confidence": 0.85,
                "note": "Confirmed category and brand",
            },
        ],
        "reasoning_trace": [
            "Starting consolidation for UPC 012000001307",
            "Weighted 4 sources: Open Food Facts(0.90), UPCItemDB(0.85), Go-UPC(0.30), Buycott(0.30)",
            "Resolved name: 'Pepsi Light' from ['Open Food Facts']",
            "Resolved brand: 'Pepsi' from ['Open Food Facts', 'UPCItemDB']",
            "Resolved category: 'Soda' from ['UPCItemDB']",
            "Merged 4 attributes from all sources",
            "Generated description (78 chars)",
            "Selected 2 images, best: True",
            "Computed confidence: 0.93",
            "Generated 2 citations",
            "Status: complete",
        ],
    },
]


@app.get("/api/demo")
async def demo(background_tasks: BackgroundTasks):
    job_id = create_job(DEMO_UPCS)
    from backend.database import _get_connection

    conn = _get_connection()
    for product_data in DEMO_PRODUCTS:
        conn.execute(
            """INSERT OR REPLACE INTO products (upc, name, brand, category, confidence, status, data, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                product_data["upc"],
                product_data["name"],
                product_data.get("brand"),
                product_data.get("category"),
                product_data.get("confidence", 0),
                product_data.get("status", "complete"),
                json.dumps(product_data),
            ),
        )
    conn.execute(
        """UPDATE jobs SET completed = ?, queued = 0, running = 0, failed = 0, updated_at = datetime('now') WHERE job_id = ?""",
        (len(DEMO_UPCS), job_id),
    )
    conn.commit()
    job = get_job(job_id)
    return {"message": "Demo products loaded", "job_id": job_id, "upcs": DEMO_UPCS, "job": job}


@app.post("/api/batch")
async def batch(request: UPCBatchRequest, background_tasks: BackgroundTasks):
    if not request.upcs:
        raise HTTPException(status_code=400, detail="No UPCs provided")
    upcs = [u.strip() for u in request.upcs if u.strip()]
    if not upcs:
        raise HTTPException(status_code=400, detail="No valid UPCs after cleaning")
    job_id = create_job(upcs)
    if request.auto_scrape:
        for upc in upcs:
            background_tasks.add_task(process_upc, upc, job_id)
    return {"message": f"Processing {len(upcs)} UPCs", "job_id": job_id, "total": len(upcs)}


@app.post("/api/upload-csv/preview")
async def upload_csv_preview(file: UploadFile = File(...), max_rows: int = Query(5, ge=1, le=20)):
    """Preview a POS CSV: show detected columns and first few UPCs."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    try:
        content = await file.read()
        preview = preview_pos_csv(content, max_rows=max_rows)
        return preview
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error previewing CSV: {str(e)}")


@app.post("/api/upload-csv")
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    max_rows: int = Query(100, ge=1, le=5000),
):
    """Upload a POS CSV export and enqueue UPCs for enrichment.

    Auto-detects UPC/EAN/SKU/PLU columns, handles quoted fields and mixed
    encodings, and accepts seed data (name, brand, category, price, public
    image URLs) to bootstrap the reasoning agent.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    try:
        content = await file.read()
        upcs, seeds, columns, truncated = parse_pos_csv(content, max_rows=max_rows)
        if not upcs:
            raise HTTPException(status_code=400, detail="No valid UPCs found in CSV")
        job_id = create_job(upcs)
        for upc, seed in zip(upcs, seeds):
            background_tasks.add_task(process_upc, upc, job_id, seed)
        return {
            "message": f"Processing {len(upcs)} UPCs from CSV",
            "job_id": job_id,
            "total": len(upcs),
            "filename": file.filename,
            "detected_columns": columns,
            "truncated": truncated,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")


@app.get("/api/products")
async def list_products(
    q: Optional[str] = Query(None, description="Search query"),
    brand: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get products with optional filtering and pagination."""
    if any([q, brand, category, status, min_confidence is not None]):
        rows = search_products(q, brand, category, status, min_confidence, limit, offset)
        total = count_products(q, brand, category, status, min_confidence)
    else:
        rows = get_all_products(limit=limit, offset=offset)
        total = count_products()
    products = []
    for row in rows:
        try:
            data = json.loads(row["data"])
            products.append(data)
        except (json.JSONDecodeError, KeyError):
            continue
    return {"products": products, "count": len(products), "total": total, "limit": limit, "offset": offset}


@app.get("/api/products/{upc}")
async def get_single_product(upc: str):
    row = get_product(upc)
    if not row:
        raise HTTPException(status_code=404, detail=f"Product not found: {upc}")
    try:
        data = json.loads(row["data"])
        return data
    except (json.JSONDecodeError, KeyError):
        raise HTTPException(status_code=500, detail="Error parsing product data")


@app.post("/api/products/{upc}/images")
async def upload_product_image(upc: str = Path(...), file: UploadFile = File(...)):
    """Upload a product image and attach it to the product record."""
    row = get_product(upc)
    if not row:
        raise HTTPException(status_code=404, detail=f"Product not found: {upc}")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        ext = ".jpg"

    filename = f"{upc}_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(uploads_dir, filename)

    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image: {e}")
    finally:
        await file.close()

    image_url = f"/uploads/{filename}"
    try:
        data = json.loads(row["data"])
        data.setdefault("images", []).append({"url": image_url, "source": "User Upload", "score": 1.0})
        if not data.get("image_url"):
            data["image_url"] = image_url
        product = ConsolidatedProduct(**data)
        upsert_product(product)
        upc_cache.set(upc, data)
        return {"upc": upc, "image_url": image_url, "images": data.get("images", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating product: {e}")


@app.delete("/api/products/{upc}/images")
async def delete_product_image(upc: str = Path(...), url: str = Query(..., description="Image URL to remove")):
    """Remove an image from a product record."""
    row = get_product(upc)
    if not row:
        raise HTTPException(status_code=404, detail=f"Product not found: {upc}")

    try:
        data = json.loads(row["data"])
        images = data.get("images", [])
        before = len(images)
        images = [img for img in images if img.get("url") != url]
        if len(images) == before:
            raise HTTPException(status_code=404, detail="Image not found on product")

        data["images"] = images
        # Update primary image if the deleted one was primary
        if data.get("image_url") == url:
            data["image_url"] = images[0]["url"] if images else None

        # Optionally delete the physical file for local uploads
        if url.startswith("/uploads/"):
            filename = os.path.basename(url)
            filepath = os.path.join(uploads_dir, filename)
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
            except Exception as e:
                logger.warning(f"Could not delete uploaded file {filepath}: {e}")

        product = ConsolidatedProduct(**data)
        upsert_product(product)
        upc_cache.set(upc, data)
        return {"upc": upc, "image_url": data.get("image_url"), "images": images}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting image: {e}")


def _filter_products_for_export(
    products: List[Dict[str, Any]],
    status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    q: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Filter products by status, confidence, and/or search query."""
    filtered = products
    if status:
        filtered = [p for p in filtered if p.get("status") == status]
    if min_confidence is not None:
        filtered = [p for p in filtered if p.get("confidence", 0) >= min_confidence]
    if q:
        query = q.lower()
        filtered = [
            p
            for p in filtered
            if query in p.get("name", "").lower()
            or query in p.get("brand", "").lower()
            or query in p.get("category", "").lower()
            or query in p.get("upc", "").lower()
        ]
    return filtered


def _get_export_image_urls(product: Dict[str, Any], max_images: int = 5) -> List[str]:
    """Collect verified image URLs for export, primary first."""
    urls = []
    generated_urls = {
        img.get("url")
        for img in product.get("images", [])
        if isinstance(img, dict) and (img.get("generated") or img.get("source") == "ShelfWise Review Placeholder")
    }
    if product.get("image_url") and product["image_url"] not in generated_urls:
        urls.append(product["image_url"])
    for img in product.get("images", []):
        if not isinstance(img, dict):
            continue
        if img.get("generated") or img.get("source") == "ShelfWise Review Placeholder":
            continue
        url = img.get("url") if isinstance(img, dict) else None
        if url and url not in urls:
            urls.append(url)
    return urls[:max_images]


@app.post("/api/export")
async def export_portfolio(request: ExportRequest):
    rows = get_all_products()
    products = []
    for row in rows:
        try:
            data = json.loads(row["data"])
            products.append(data)
        except (json.JSONDecodeError, KeyError):
            continue

    products = _filter_products_for_export(products, request.status, request.min_confidence, request.q)

    fmt = request.format.lower()

    if request.preview:
        preview_products = products[: request.preview_limit]
        return {
            "preview": True,
            "format": fmt,
            "total": len(products),
            "preview_count": len(preview_products),
            "filters": {
                "status": request.status,
                "min_confidence": request.min_confidence,
                "q": request.q,
            },
            "products": preview_products,
        }

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        header = ["upc", "name", "brand", "category", "description", "image_url", "confidence", "status", "citations"]
        for i in range(2, 6):
            header.append(f"image_{i}")
        writer.writerow(header)
        for p in products:
            citations_str = "; ".join(f"{c['source']}:{','.join(c['fields'])}" for c in p.get("citations", []))
            image_urls = _get_export_image_urls(p, max_images=5)
            row = [
                p.get("upc", ""),
                p.get("name", ""),
                p.get("brand", ""),
                p.get("category", ""),
                p.get("description", ""),
                image_urls[0] if image_urls else "",
                p.get("confidence", 0),
                p.get("status", ""),
                citations_str,
            ]
            for i in range(1, 5):
                row.append(image_urls[i] if i < len(image_urls) else "")
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shelfwise-portfolio.csv"},
        )

    elif fmt == "json":
        return StreamingResponse(
            io.BytesIO(json.dumps(products, indent=2).encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=shelfwise-portfolio.json"},
        )

    elif fmt == "shopify":
        output = io.StringIO()
        writer = csv.writer(output)
        header = [
            "Handle",
            "Title",
            "Body (HTML)",
            "Vendor",
            "Type",
            "Tags",
            "Published",
            "Option1 Name",
            "Option1 Value",
            "Variant SKU",
            "Variant Grams",
            "Variant Inventory Tracker",
            "Variant Inventory Qty",
            "Variant Inventory Policy",
            "Variant Fulfillment Service",
            "Variant Price",
            "Variant Compare At Price",
            "Image Src",
        ]
        for i in range(2, 6):
            header.append(f"Image Src {i}")
        writer.writerow(header)
        for p in products:
            handle = p.get("upc", "").lower()
            image_urls = _get_export_image_urls(p, max_images=5)
            row = [
                handle,
                p.get("name", ""),
                p.get("description", ""),
                p.get("brand", ""),
                p.get("category", ""),
                f"upc-{p.get('upc', '')}, shelfwise",
                "TRUE",
                "Title",
                "Default Title",
                p.get("upc", ""),
                "0",
                "",
                "0",
                "deny",
                "manual",
                "",
                "",
                image_urls[0] if image_urls else "",
            ]
            for i in range(1, 5):
                row.append(image_urls[i] if i < len(image_urls) else "")
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shelfwise-shopify.csv"},
        )

    elif fmt == "amazon":
        output = io.StringIO()
        writer = csv.writer(output)
        header = [
            "sku",
            "product-id",
            "product-id-type",
            "item-name",
            "brand-name",
            "manufacturer",
            "product-description",
            "item-type",
            "update-delete",
            "standard-price",
            "quantity",
            "main-image-url",
        ]
        for i in range(2, 6):
            header.append(f"other-image-url-{i - 1}")
        writer.writerow(header)
        for p in products:
            image_urls = _get_export_image_urls(p, max_images=5)
            row = [
                p.get("upc", ""),
                p.get("upc", ""),
                "3",
                p.get("name", ""),
                p.get("brand", ""),
                p.get("brand", ""),
                p.get("description", ""),
                p.get("category", ""),
                "",
                "",
                "",
                image_urls[0] if image_urls else "",
            ]
            for i in range(1, 5):
                row.append(image_urls[i] if i < len(image_urls) else "")
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shelfwise-amazon.csv"},
        )

    elif fmt == "woocommerce":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["ID", "Type", "SKU", "Name", "Published", "Description", "Short description", "Categories", "Images"]
        )
        for p in products:
            image_urls = _get_export_image_urls(p, max_images=5)
            writer.writerow(
                [
                    "",
                    "simple",
                    p.get("upc", ""),
                    p.get("name", ""),
                    "1",
                    p.get("description", ""),
                    "",
                    p.get("category", ""),
                    ",".join(image_urls),
                ]
            )
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shelfwise-woocommerce.csv"},
        )

    elif fmt == "ebay":
        output = io.StringIO()
        writer = csv.writer(output)
        header = [
            "*Action(SiteID=US|Country=US|Currency=USD|Version=941|CC=ISO-8859-1)",
            "ItemID",
            "Title",
            "Category",
            "PicURL",
            "Description",
            "Format",
            "Duration",
            "StartPrice",
            "Quantity",
            "Location",
            "ShippingType",
            "ShippingService-1:Option",
            "ShippingService-1:Cost",
            "ReturnsAcceptedOption",
            "RefundOption",
            "ReturnPolicyDescription",
        ]
        for i in range(2, 6):
            header.append(f"PicURL{i}")
        writer.writerow(header)
        for p in products:
            image_urls = _get_export_image_urls(p, max_images=5)
            row = [
                "Add",
                "",
                p.get("name", ""),
                p.get("category", ""),
                image_urls[0] if image_urls else "",
                p.get("description", ""),
                "FixedPrice",
                "GTC",
                "",
                "1",
                "US",
                "Flat",
                "USPSMedia",
                "0",
                "ReturnsAccepted",
                "MoneyBack",
                "",
            ]
            for i in range(1, 5):
                row.append(image_urls[i] if i < len(image_urls) else "")
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shelfwise-ebay.csv"},
        )

    elif fmt == "etsy":
        output = io.StringIO()
        writer = csv.writer(output)
        header = ["TITLE", "DESCRIPTION", "PRICE", "CATEGORY", "QUANTITY", "TAGS", "MATERIALS"]
        for i in range(1, 6):
            header.append(f"IMAGE{i}")
        writer.writerow(header)
        for p in products:
            image_urls = _get_export_image_urls(p, max_images=5)
            row = [
                p.get("name", ""),
                p.get("description", ""),
                "",
                p.get("category", ""),
                "1",
                f"upc-{p.get('upc', '')}",
                "",
            ]
            for i in range(5):
                row.append(image_urls[i] if i < len(image_urls) else "")
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shelfwise-etsy.csv"},
        )

    elif fmt == "bigcommerce":
        output = io.StringIO()
        writer = csv.writer(output)
        header = [
            "Product Name",
            "Product Type",
            "Product Code/SKU",
            "Price",
            "Category",
            "Product Description",
        ]
        for i in range(1, 6):
            header.append(f"Product Image URL - {i}")
        writer.writerow(header)
        for p in products:
            image_urls = _get_export_image_urls(p, max_images=5)
            row = [
                p.get("name", ""),
                "Physical",
                p.get("upc", ""),
                "",
                p.get("category", ""),
                p.get("description", ""),
            ]
            for i in range(5):
                row.append(image_urls[i] if i < len(image_urls) else "")
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shelfwise-bigcommerce.csv"},
        )

    elif fmt == "doordash":
        output = io.StringIO()
        writer = csv.writer(output)
        header = [
            "Merchant ID",
            "Item ID",
            "Item Name",
            "Description",
            "Category",
            "Price",
            "Image URL",
            "UPC",
            "Status",
        ]
        for i in range(2, 6):
            header.append(f"Image URL {i}")
        writer.writerow(header)
        for p in products:
            image_urls = _get_export_image_urls(p, max_images=5)
            row = [
                "",
                p.get("upc", ""),
                p.get("name", ""),
                p.get("description", ""),
                p.get("category", ""),
                "",
                image_urls[0] if image_urls else "",
                p.get("upc", ""),
                "Active",
            ]
            for i in range(1, 5):
                row.append(image_urls[i] if i < len(image_urls) else "")
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shelfwise-doordash.csv"},
        )

    elif fmt == "ubereats":
        output = io.StringIO()
        writer = csv.writer(output)
        header = [
            "Menu ID",
            "Section",
            "Item Name",
            "Item Description",
            "Price",
            "Image URL",
            "External ID",
            "Dietary Tags",
        ]
        for i in range(2, 6):
            header.append(f"Image URL {i}")
        writer.writerow(header)
        for p in products:
            image_urls = _get_export_image_urls(p, max_images=5)
            row = [
                "",
                p.get("category", ""),
                p.get("name", ""),
                p.get("description", ""),
                "",
                image_urls[0] if image_urls else "",
                p.get("upc", ""),
                "",
            ]
            for i in range(1, 5):
                row.append(image_urls[i] if i < len(image_urls) else "")
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shelfwise-ubereats.csv"},
        )

    elif fmt == "grubhub":
        output = io.StringIO()
        writer = csv.writer(output)
        header = [
            "Restaurant ID",
            "Menu Item ID",
            "Item Name",
            "Description",
            "Category",
            "Price",
            "Image URL",
            "UPC",
            "Enabled",
        ]
        for i in range(2, 6):
            header.append(f"Image URL {i}")
        writer.writerow(header)
        for p in products:
            image_urls = _get_export_image_urls(p, max_images=5)
            row = [
                "",
                p.get("upc", ""),
                p.get("name", ""),
                p.get("description", ""),
                p.get("category", ""),
                "",
                image_urls[0] if image_urls else "",
                p.get("upc", ""),
                "TRUE",
            ]
            for i in range(1, 5):
                row.append(image_urls[i] if i < len(image_urls) else "")
            writer.writerow(row)
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shelfwise-grubhub.csv"},
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Format must be one of: csv, json, shopify, amazon, woocommerce, ebay, etsy, bigcommerce, doordash, ubereats, grubhub",
        )


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@app.get("/api/jobs/{job_id}/stream")
async def stream_job_status(job_id: str):
    import asyncio

    async def event_generator():
        last_status = None
        for _ in range(600):
            job = get_job(job_id)
            if not job:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
                break
            current_status = json.dumps(job, sort_keys=True)
            if current_status != last_status:
                last_status = current_status
                yield f"data: {json.dumps({'type': 'update', 'job': job})}\n\n"
            total = job.get("total", 0)
            completed = job.get("completed", 0)
            failed = job.get("failed", 0)
            if total > 0 and (completed + failed) >= total:
                yield f"data: {json.dumps({'type': 'complete', 'job': job})}\n\n"
                break
            await asyncio.sleep(0.5)
        else:
            yield f"data: {json.dumps({'type': 'timeout', 'message': 'Stream timed out'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
async def health_check():
    fiq_health = foundry_iq.health() if foundry_iq else {"status": "unavailable"}
    # Dynamically count registry sources
    try:
        from backend.scraper_registry import ScraperRegistry

        registry = ScraperRegistry()
        registry_count = registry.get_source_count()
    except Exception:
        registry_count = 0
    return {
        "status": "healthy",
        "version": "1.2.0",
        "features": {
            "scraping": True,
            "reasoning": True,
            "foundry_integration": True,
            "foundry_mode": fiq_health.get("mode", "unknown"),
            "caching": True,
            "learning": True,
        },
        "scrapers": {
            "core": len(SOURCE_WEIGHTS),
            "registry": registry_count,
            "total": len(SOURCE_WEIGHTS) + registry_count,
            "names": list(SOURCE_WEIGHTS.keys())[:10],  # First 10 names
        },
        "cache": upc_cache.stats(),
        "foundry_iq": fiq_health,
    }


@app.get("/api/learning")
async def get_learning_stats():
    """Return adaptive scraper source health used for future prioritization."""
    s = get_scraper()
    return {
        "source_health": await s.health.stats(),
        "note": "ShelfWise tracks per-source success rates and latency so source selection can be tuned over time.",
    }


@app.get("/api/stats")
async def get_portfolio_stats():
    return get_stats()


@app.get("/api/products/{upc}/compare")
async def compare_product(upc: str):
    product = get_product(upc)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    try:
        data = json.loads(product["data"])
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Corrupted product data")
    return {
        "upc": upc,
        "consolidated": data,
        "note": "This endpoint shows the final consolidated record. Raw source data is preserved in the reasoning trace and citations.",
    }


@app.post("/api/clear")
async def clear_portfolio():
    delete_all_products()
    upc_cache.clear()
    return {"status": "cleared", "message": "All products and jobs have been deleted"}


@app.get("/api/search")
async def search_endpoint(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Full-text search across product names and UPCs."""
    rows = search_products(query=q, limit=limit, offset=offset)
    products = []
    for row in rows:
        try:
            data = json.loads(row["data"])
            products.append(data)
        except (json.JSONDecodeError, KeyError):
            continue
    return {"products": products, "count": len(products), "query": q}


@app.get("/api/metrics")
async def metrics():
    """Performance metrics for monitoring."""
    avg_scrape = sum(_scrape_times) / len(_scrape_times) if _scrape_times else 0
    scraper_health = await scraper.health.stats() if scraper else {}
    return {
        "avg_scrape_time_sec": round(avg_scrape, 3),
        "total_scrapes": len(_scrape_times),
        "cache_stats": upc_cache.stats(),
        "active_circuits": {name: cb.state for name, cb in (scraper.circuits.items() if scraper else {})},
        "scraper_health": scraper_health,
    }


# ---------------------------------------------------------------------------
# Foundry IQ Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/foundry/health")
async def foundry_health():
    """Foundry IQ service health and status."""
    if not foundry_iq:
        raise HTTPException(status_code=503, detail="Foundry IQ service not initialized")
    return foundry_iq.health()


@app.post("/api/foundry/query")
async def foundry_query(
    query: str = Query(..., min_length=1, description="Natural language query"),
    role: str = Query("user", description="User role: guest, user, admin"),
    top_k: int = Query(5, ge=1, le=20),
):
    """Query the Foundry IQ knowledge base with natural language.
    Returns grounded answers with citations (simulates Foundry IQ agentic retrieval).
    """
    if not foundry_iq:
        raise HTTPException(status_code=503, detail="Foundry IQ service not initialized")
    result = foundry_iq.query_knowledge(query, role=role, top_k=top_k)
    return result.to_dict()


@app.post("/api/foundry/reason")
async def foundry_reason(
    upc: str = Query(..., min_length=5, description="Product UPC"),
    question: str = Query(..., min_length=1, description="Question about the product"),
    role: str = Query("user", description="User role"),
):
    """Ask a reasoning question about a specific product.
    Uses knowledge graph traversal and ontology reasoning.
    """
    if not foundry_iq:
        raise HTTPException(status_code=503, detail="Foundry IQ service not initialized")
    result = foundry_iq.reason_over_products(upc, question, role=role)
    return result.to_dict()


@app.get("/api/foundry/ontology")
async def foundry_ontology():
    """Export the current product ontology (semantic layer).
    Simulates Foundry IQ's ontology/knowledge graph view.
    """
    if not foundry_iq:
        raise HTTPException(status_code=503, detail="Foundry IQ service not initialized")
    return foundry_iq.get_ontology()


@app.get("/api/foundry/graph/search")
async def foundry_graph_search(
    q: str = Query(..., min_length=1, description="Search query"),
    top_k: int = Query(10, ge=1, le=50),
):
    """Semantic search over the knowledge graph nodes."""
    if not foundry_iq:
        raise HTTPException(status_code=503, detail="Foundry IQ service not initialized")
    return {"results": foundry_iq.knowledge_graph.semantic_search(q, top_k=top_k)}


@app.get("/api/foundry/graph/related/{node_id}")
async def foundry_graph_related(
    node_id: str,
    relation: Optional[str] = Query(None, description="Filter by relation type"),
):
    """Get related nodes in the knowledge graph (ontology traversal)."""
    if not foundry_iq:
        raise HTTPException(status_code=503, detail="Foundry IQ service not initialized")
    return {"related": foundry_iq.knowledge_graph.get_related(node_id, relation=relation)}


@app.get("/api/foundry/history")
async def foundry_history(limit: int = Query(50, ge=1, le=200)):
    """Recent Foundry IQ queries and responses."""
    if not foundry_iq:
        raise HTTPException(status_code=503, detail="Foundry IQ service not initialized")
    return {"queries": foundry_iq.get_query_history(limit=limit)}


@app.post("/api/foundry/ingest")
async def foundry_ingest_catalog():
    """Force re-ingestion of the product catalog into the knowledge graph."""
    if not foundry_iq:
        raise HTTPException(status_code=503, detail="Foundry IQ service not initialized")
    foundry_iq.ingest_product_catalog()
    return {
        "status": "ingested",
        "knowledge_graph": foundry_iq.knowledge_graph.to_dict()["stats"],
    }
