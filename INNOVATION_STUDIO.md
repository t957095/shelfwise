# ShelfWise — Project Description

**Agents League Hackathon 2026 — Reasoning Agents Track**

ShelfWise turns a list of UPC barcodes into a complete, marketplace-ready product portfolio. It is built around a **Microsoft Foundry IQ-style reasoning layer** that gathers multi-source evidence, resolves conflicts, generates cited product records, and exports them to Shopify, Amazon, WooCommerce, eBay, Etsy, BigCommerce, DoorDash, Uber Eats, Grubhub, or CSV/JSON.

## Foundry IQ Integration

At the center of ShelfWise is a reasoning agent that mirrors Foundry IQ patterns:

- **Multi-source evidence retrieval** — queries 8 core data sources (Open Food Facts, UPCItemDB, BarcodeLookup, Go-UPC, Buycott, EANdata, Brave Search, Google Search) plus a registry of 270+ additional sources, all concurrently.
- **Source-weighted conflict resolution** — each source is weighted by historical reliability; the agent resolves disagreements across name, brand, category, description, and attributes using Jaccard deduplication and weighted voting.
- **Grounded citations** — every field in the consolidated record carries a citation with source URL, fields contributed, and confidence score, producing an auditable evidence trail.
- **LLM enrichment fallback** — when `FOUNDRY_ENDPOINT` and `FOUNDRY_API_KEY` are configured, the agent sends raw evidence to Azure OpenAI GPT-4.1-mini for advanced consolidation; when unavailable, a deterministic local engine produces complete results with no external dependency.

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

1. A user uploads a CSV or pastes UPCs.
2. The scraper collects structured and unstructured evidence from dozens of sources in parallel.
3. The reasoning agent weights, deduplicates, and resolves the evidence into a single consolidated record.
4. A ranked gallery of verified multi-angle images is selected, deduplicated, and clustered.
5. The record is stored in SQLite, streamed to the frontend via SSE, and exported to the marketplace format of choice — including native formats for food-delivery platforms.

## Why It Matters

Restaurants, ghost kitchens, and convenience stores that list on DoorDash, Uber Eats, or Grubhub often receive CSV files from their POS system with hundreds of UPCs and no photos. Manually researching each item — finding the right name, description, and clean photo — is too slow, so menus and catalogs stay incomplete. ShelfWise automates the research, produces trustworthy, cited listings with one verified product photo each, and exports directly to the delivery platform's format — turning a POS export into a complete online catalog in minutes.
