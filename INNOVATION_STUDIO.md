# ShelfWise — Project Description

**Agents League Hackathon 2026 — Reasoning Agents Track**

ShelfWise turns a spreadsheet of UPCs and SKUs into a complete, market-ready product catalog. It uses a **Microsoft Foundry IQ-style reasoning layer** to gather multi-source evidence from across the web, resolve conflicts, generate cited product records, and export them to Shopify, Amazon Seller Central, eBay, Facebook Marketplace, WooCommerce, Etsy, BigCommerce, DoorDash, Uber Eats, Grubhub, or CSV/JSON.

## The Problem

When someone buys a pallet of inventory, they often receive hundreds of products with nothing but UPC barcodes or internal SKUs on the packaging. Before they can sell anything online, they have to figure out what each item is — searching Google, checking marketplaces, comparing listings, finding product photos, copying specifications, and writing descriptions.

At around 8 minutes per item, a pallet with 400 products can require more than 50 hours of manual work before anything is listed for sale. For many small businesses, that work never gets done. Inventory sits in storage instead of generating revenue.

## The Solution

Users upload a CSV containing UPCs or SKUs, or paste them directly into ShelfWise. The system processes each identifier and searches across the web to find product information wherever it exists. Instead of relying on a single product database, ShelfWise gathers evidence from multiple sources including retailer listings, manufacturer pages, marketplace listings, specialty stores, distributor catalogs, and other publicly available product data.

This approach allows ShelfWise to identify products that may not exist in traditional UPC databases. Niche items, discontinued inventory, liquidation stock, and specialty products can often be found because the system searches for evidence across the broader web rather than a fixed catalog.

## Foundry IQ Integration

At the center of ShelfWise is a reasoning agent that mirrors Foundry IQ patterns:

- **Multi-source evidence retrieval** — queries 10 core data sources plus a registry of 270+ additional sources, all concurrently. When a barcode has no public match, the agent searches the web by product name and brand.
- **Source-weighted conflict resolution** — each source is weighted by historical reliability; the agent resolves disagreements across name, brand, category, description, and attributes using Jaccard deduplication and weighted voting.
- **Grounded citations** — every field in the consolidated record carries a citation with source URL, fields contributed, and confidence score, producing an auditable evidence trail.
- **LLM enrichment fallback** — when `FOUNDRY_ENDPOINT` and `FOUNDRY_API_KEY` are configured, the agent sends raw evidence to Azure OpenAI for advanced consolidation; when unavailable, a deterministic local engine produces complete results with no external dependency.

## Verified Product Imagery — Multi-Angle Gallery from Verified Sources

ShelfWise does not return random product photos. A dedicated **image verification pipeline** downloads candidate images from verified sources and scores every photo on:

- **White / clean background** — samples edge pixels to detect near-white backgrounds typical of marketplace listings.
- **Image quality** — resolution and aspect-ratio checks filter out thumbnails and banners.
- **Central product focus** — edge-density analysis favors images where the product is centered and in focus.
- **Center fill** — rewards product shots where the item fills the frame with a clean border, penalizing empty frames or tightly cropped logos.
- **Sharpness** — edge-variance filtering rejects blurry or over-compressed photos.
- **Source verification** — only URLs from trusted product-data sources and public image hosts are accepted; ad/tracking domains are rejected.
- **Perceptual clustering** — images are grouped by perceptual hash so the gallery contains distinct angles and views, not five copies of the same pack shot.
- **Name-based image search** — when a barcode has no public UPC match (common for local PLUs), ShelfWise searches the web by product name + brand and runs the same verification pipeline on those results.
- **Manual upload & review** — users can open the image manager on any product card to delete auto-selected images or upload their own, keeping full control over the gallery.

The result is a **ranked gallery of up to 5 verified, marketplace-ready photos** per product: a hero image plus additional white-background angles sourced from the web or supplied by the user. The frontend renders the best shot prominently with thumbnail navigation; exports include the primary image and all verified alternates.

## End-to-End Workflow

1. A user uploads a CSV or pastes UPCs/SKUs.
2. The scraper collects structured and unstructured evidence from dozens of sources in parallel.
3. When no public UPC match exists, the system searches the web by product name/brand.
4. The reasoning agent weights, deduplicates, and resolves the evidence into a single consolidated record.
5. A ranked gallery of verified multi-angle images is selected, deduplicated, and clustered.
6. The record is stored in SQLite, streamed to the frontend via SSE, and exported to the marketplace format of choice.

## Why It Matters

Small businesses that buy liquidation pallets, wholesale lots, or estate sales often receive hundreds or thousands of items with nothing but a UPC barcode. Turning those barcodes into e-commerce-ready listings is a manual, soul-crushing process. ShelfWise automates the research, produces trustworthy, cited listings with verified multi-angle photos, and exports directly to the marketplace format of choice — turning a spreadsheet of identifiers into a complete online catalog in minutes.
