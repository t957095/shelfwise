#!/usr/bin/env python3
"""ShelfWise API - Main FastAPI Application (Optimized).

AI Product Portfolio Builder for Small Businesses.
"""

import os
import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from dotenv import load_dotenv
load_dotenv(_project_root / ".env")

import csv
import io
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, BackgroundTasks, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

from backend.models import ConsolidatedProduct, UPCBatchRequest, ExportRequest, JobStatus
from backend.database import (
    init_db, create_job, update_job, get_job, upsert_product, get_product,
    get_all_products, delete_all_products, get_stats, search_products, bulk_upsert_products,
)
from backend.scraper import UPCScraper, SOURCE_WEIGHTS
from backend.foundry_agent import ProductReasoningAgent
from backend.cache import upc_cache
from backend.foundry_iq import FoundryIQService, get_foundry_iq_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shelfwise")

DEMO_UPCS = ["049000050103", "022000020806", "012000001307"]
http_client: Optional[httpx.AsyncClient] = None
scraper: Optional[UPCScraper] = None
agent = ProductReasoningAgent()
foundry_iq: Optional[FoundryIQService] = None

# Request timing metrics
_request_times: List[float] = []
_scrape_times: List[float] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client, scraper, foundry_iq
    init_db()
    http_client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_connections=50, max_keepalive_connections=20))
    scraper = UPCScraper(http_client)
    foundry_iq = get_foundry_iq_service(db_path="shelfwise.db")
    logger.info("ShelfWise API started (optimized) | Foundry IQ: %s", "azure" if foundry_iq.is_real_integration else "local_simulation")
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


def get_scraper() -> UPCScraper:
    if scraper is None:
        raise RuntimeError("Scraper not initialized")
    return scraper


# ---------------------------------------------------------------------------
# Background task: process a single UPC
# ---------------------------------------------------------------------------
async def process_upc(upc: str, job_id: str):
    try:
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

        start = time.time()
        s = get_scraper()
        raw_data_list = await s.scrape_all(upc)
        scrape_elapsed = time.time() - start
        _scrape_times.append(scrape_elapsed)
        logger.info(f"UPC {upc}: scraped {len(raw_data_list)} sources in {scrape_elapsed:.2f}s")

        consolidated_dict = await agent.consolidate(upc, raw_data_list)
        logger.info(f"UPC {upc}: consolidated with confidence {consolidated_dict.get('confidence', 0)}")

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
                upc=upc, name=f"Error: {upc}",
                description=f"Failed to process UPC {upc}: {str(e)}",
                confidence=0.0, status="error",
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
        "name": "ShelfWise", "version": "1.1.0",
        "description": "AI Product Portfolio Builder for Small Businesses",
        "status": "ok",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "App info"},
            {"path": "/app", "method": "GET", "description": "Web application"},
            {"path": "/api/demo", "method": "GET", "description": "Load demo products"},
            {"path": "/api/batch", "method": "POST", "description": "Submit UPCs for processing"},
            {"path": "/api/upload-csv", "method": "POST", "description": "Upload CSV with 'upc' column"},
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
        "upc": "049000050103", "name": "Coca-Cola Classic", "brand": "Coca-Cola",
        "category": "Colas",
        "description": "Coca-Cola Classic - The original and refreshing taste. 2 liter bottle. Perfect for parties, gatherings, and everyday enjoyment.",
        "image_url": "https://images.openfoodfacts.org/images/products/004/900/005/0103/front_en.96.400.jpg",
        "images": [
            {"url": "https://images.openfoodfacts.org/images/products/004/900/005/0103/front_en.96.400.jpg", "source": "Open Food Facts", "score": 0.9},
            {"url": "https://pics.walgreens.com/prodimg/416899/450.jpg", "source": "UPCItemDB", "score": 0.85},
        ],
        "attributes": {"size": "2 Liter", "flavor": "Original", "container": "Bottle", "color": "Red"},
        "confidence": 0.95, "status": "complete",
        "citations": [
            {"source": "Open Food Facts", "source_url": "https://world.openfoodfacts.org/api/v2/product/049000050103.json", "fields": ["name", "brand", "category", "images", "attributes"], "confidence": 0.9, "note": "Primary source with full product data"},
            {"source": "UPCItemDB", "source_url": "https://api.upcitemdb.com/prod/trial/lookup?upc=049000050103", "fields": ["name", "brand", "images"], "confidence": 0.85, "note": "Confirmed name and brand"},
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
            "Status: complete"
        ]
    },
    {
        "upc": "022000020806", "name": "M&M's Milk Chocolate", "brand": "Mars",
        "category": "Candy & Chocolate",
        "description": "M&M's Milk Chocolate - Colorful candy-coated chocolates in a convenient sharing size bag. A classic American snack since 1941.",
        "image_url": "https://target.scene7.com/is/image/Target/GUEST_3d2ee4ac-ace5-4e21-86c2-575d2f5a4f11?wid=488&hei=488&fmt=pjpeg",
        "images": [
            {"url": "https://target.scene7.com/is/image/Target/GUEST_3d2ee4ac-ace5-4e21-86c2-575d2f5a4f11?wid=488&hei=488&fmt=pjpeg", "source": "Target", "score": 0.8},
            {"url": "https://i5.walmartimages.com/asr/5e0e2e2e-2e2e-2e2e-2e2e-2e2e2e2e2e2e_1.2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e.jpeg", "source": "Walmart", "score": 0.75},
        ],
        "attributes": {"size": "1.69 oz", "flavor": "Milk Chocolate", "container": "Bag", "type": "Candy"},
        "confidence": 0.92, "status": "complete",
        "citations": [
            {"source": "UPCItemDB", "source_url": "https://api.upcitemdb.com/prod/trial/lookup?upc=022000020806", "fields": ["name", "brand", "category", "images"], "confidence": 0.85, "note": "Full product record with images"},
            {"source": "Buycott", "source_url": "https://www.buycott.com/upc/022000020806", "fields": ["name", "brand"], "confidence": 0.7, "note": "Confirmed brand ownership"},
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
            "Status: complete"
        ]
    },
    {
        "upc": "012000001307", "name": "Pepsi Light", "brand": "Pepsi",
        "category": "Soda",
        "description": "Pepsi Light - Refreshing diet cola with zero sugar and zero calories. 20 fl oz bottle.",
        "image_url": "https://images.openfoodfacts.org/images/products/001/200/000/1307/front_fr.5.400.jpg",
        "images": [
            {"url": "https://images.openfoodfacts.org/images/products/001/200/000/1307/front_fr.5.400.jpg", "source": "Open Food Facts", "score": 0.9},
            {"url": "https://i5.walmartimages.com/asr/c0294df7-bb4a-4545-96a4-548993338765_1.99f18eeb42d60ab95f50a7ae7fcf25d3.jpeg", "source": "Walmart", "score": 0.85},
        ],
        "attributes": {"size": "20 fl oz", "flavor": "Diet Cola", "container": "Bottle", "calories": "0"},
        "confidence": 0.93, "status": "complete",
        "citations": [
            {"source": "Open Food Facts", "source_url": "https://world.openfoodfacts.org/api/v2/product/012000001307.json", "fields": ["name", "brand", "images", "attributes"], "confidence": 0.9, "note": "Primary source with nutrition data"},
            {"source": "UPCItemDB", "source_url": "https://api.upcitemdb.com/prod/trial/lookup?upc=012000001307", "fields": ["name", "brand", "category"], "confidence": 0.85, "note": "Confirmed category and brand"},
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
            "Status: complete"
        ]
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


@app.post("/api/upload-csv")
async def upload_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    try:
        content = await file.read()
        text = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(text))
        if 'upc' not in reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV must have a column named 'upc'")
        upcs = [row['upc'].strip() for row in reader if row['upc'].strip()]
        if not upcs:
            raise HTTPException(status_code=400, detail="No UPCs found in CSV")
        job_id = create_job(upcs)
        for upc in upcs:
            background_tasks.add_task(process_upc, upc, job_id)
        return {"message": f"Processing {len(upcs)} UPCs from CSV", "job_id": job_id, "total": len(upcs), "filename": file.filename}
    except HTTPException:
        raise
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
    else:
        rows = get_all_products()
    products = []
    for row in rows:
        try:
            data = json.loads(row["data"])
            products.append(data)
        except (json.JSONDecodeError, KeyError):
            continue
    return {"products": products, "count": len(products)}


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

    fmt = request.format.lower()

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["upc", "name", "brand", "category", "description", "image_url", "confidence", "status", "citations"])
        for p in products:
            citations_str = "; ".join(f"{c['source']}:{','.join(c['fields'])}" for c in p.get("citations", []))
            writer.writerow([p.get("upc", ""), p.get("name", ""), p.get("brand", ""), p.get("category", ""), p.get("description", ""), p.get("image_url", ""), p.get("confidence", 0), p.get("status", ""), citations_str])
        output.seek(0)
        return StreamingResponse(io.BytesIO(output.getvalue().encode('utf-8')), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=shelfwise-portfolio.csv"})

    elif fmt == "json":
        return StreamingResponse(io.BytesIO(json.dumps(products, indent=2).encode('utf-8')), media_type="application/json", headers={"Content-Disposition": "attachment; filename=shelfwise-portfolio.json"})

    elif fmt == "shopify":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Handle", "Title", "Body (HTML)", "Vendor", "Type", "Tags", "Published", "Option1 Name", "Option1 Value", "Variant SKU", "Variant Grams", "Variant Inventory Tracker", "Variant Inventory Qty", "Variant Inventory Policy", "Variant Fulfillment Service", "Variant Price", "Variant Compare At Price", "Image Src"])
        for p in products:
            handle = p.get("upc", "").lower()
            writer.writerow([handle, p.get("name", ""), p.get("description", ""), p.get("brand", ""), p.get("category", ""), f"upc-{p.get('upc', '')}, shelfwise", "TRUE", "Title", "Default Title", p.get("upc", ""), "0", "", "0", "deny", "manual", "", "", p.get("image_url", "")])
        output.seek(0)
        return StreamingResponse(io.BytesIO(output.getvalue().encode('utf-8')), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=shelfwise-shopify.csv"})

    elif fmt == "amazon":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["sku", "product-id", "product-id-type", "item-name", "brand-name", "manufacturer", "product-description", "item-type", "update-delete", "standard-price", "quantity", "main-image-url"])
        for p in products:
            writer.writerow([p.get("upc", ""), p.get("upc", ""), "3", p.get("name", ""), p.get("brand", ""), p.get("brand", ""), p.get("description", ""), p.get("category", ""), "", "", "", p.get("image_url", "")])
        output.seek(0)
        return StreamingResponse(io.BytesIO(output.getvalue().encode('utf-8')), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=shelfwise-amazon.csv"})

    elif fmt == "woocommerce":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Type", "SKU", "Name", "Published", "Description", "Short description", "Categories", "Images"])
        for p in products:
            writer.writerow(["", "simple", p.get("upc", ""), p.get("name", ""), "1", p.get("description", ""), "", p.get("category", ""), p.get("image_url", "")])
        output.seek(0)
        return StreamingResponse(io.BytesIO(output.getvalue().encode('utf-8')), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=shelfwise-woocommerce.csv"})

    elif fmt == "ebay":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["*Action(SiteID=US|Country=US|Currency=USD|Version=941|CC=ISO-8859-1)", "ItemID", "Title", "Category", "PicURL", "Description", "Format", "Duration", "StartPrice", "Quantity", "Location", "ShippingType", "ShippingService-1:Option", "ShippingService-1:Cost", "ReturnsAcceptedOption", "RefundOption", "ReturnPolicyDescription"])
        for p in products:
            writer.writerow(["Add", "", p.get("name", ""), p.get("category", ""), p.get("image_url", ""), p.get("description", ""), "FixedPrice", "GTC", "", "1", "US", "Flat", "USPSMedia", "0", "ReturnsAccepted", "MoneyBack", ""])
        output.seek(0)
        return StreamingResponse(io.BytesIO(output.getvalue().encode('utf-8')), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=shelfwise-ebay.csv"})

    elif fmt == "etsy":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["TITLE", "DESCRIPTION", "PRICE", "CATEGORY", "QUANTITY", "TAGS", "MATERIALS", "IMAGE1"])
        for p in products:
            writer.writerow([p.get("name", ""), p.get("description", ""), "", p.get("category", ""), "1", f"upc-{p.get('upc', '')}", "", p.get("image_url", "")])
        output.seek(0)
        return StreamingResponse(io.BytesIO(output.getvalue().encode('utf-8')), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=shelfwise-etsy.csv"})

    elif fmt == "bigcommerce":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Product Name", "Product Type", "Product Code/SKU", "Price", "Category", "Product Description", "Product Image URL - 1"])
        for p in products:
            writer.writerow([p.get("name", ""), "Physical", p.get("upc", ""), "", p.get("category", ""), p.get("description", ""), p.get("image_url", "")])
        output.seek(0)
        return StreamingResponse(io.BytesIO(output.getvalue().encode('utf-8')), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=shelfwise-bigcommerce.csv"})

    else:
        raise HTTPException(status_code=400, detail="Format must be one of: csv, json, shopify, amazon, woocommerce, ebay, etsy, bigcommerce")


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
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@app.get("/api/health")
async def health_check():
    fiq_health = foundry_iq.health() if foundry_iq else {"status": "unavailable"}
    return {
        "status": "healthy",
        "version": "1.2.0",
        "features": {
            "scraping": True,
            "reasoning": True,
            "foundry_integration": True,
            "foundry_mode": fiq_health.get("mode", "unknown"),
            "caching": True,
        },
        "scrapers": list(SOURCE_WEIGHTS.keys()),
        "cache": upc_cache.stats(),
        "foundry_iq": fiq_health,
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
    return {"upc": upc, "consolidated": data, "note": "This endpoint shows the final consolidated record. Raw source data is preserved in the reasoning trace and citations."}


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
    return {
        "avg_scrape_time_sec": round(avg_scrape, 3),
        "total_scrapes": len(_scrape_times),
        "cache_stats": upc_cache.stats(),
        "active_circuits": {name: cb.state for name, cb in (scraper.circuits.items() if scraper else {})},
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
