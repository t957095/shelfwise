# ShelfWise — Project Description

**Agents League Hackathon 2026 — Reasoning Agents Track**

ShelfWise turns a list of UPC barcodes into a complete, marketplace-ready product portfolio. It is built around a **Microsoft Foundry IQ-style reasoning layer** that gathers multi-source evidence, resolves conflicts, generates cited product records, and exports them to Shopify, Amazon, WooCommerce, eBay, Etsy, BigCommerce, DoorDash, Uber Eats, Grubhub, or CSV/JSON.

## Foundry IQ Integration

At the center of ShelfWise is a reasoning agent that mirrors Foundry IQ patterns:

- **Multi-source evidence retrieval** — queries 8 core data sources (Open Food Facts, UPCItemDB, BarcodeLookup, Go-UPC, Buycott, EANdata, Brave Search, Google Search) plus a registry of 270+ additional sources, all concurrently.
- **Source-weighted conflict resolution** — each source is weighted by historical reliability; the agent resolves disagreements across name, brand, category, description, and attributes using Jaccard deduplication and weighted voting.
- **Grounded citations** — every field in the consolidated record carries a citation with source URL, fields contributed, and confidence score, producing an auditable evidence trail.
- **LLM enrichment fallback** — when `FOUNDRY_ENDPOINT` and `FOUNDRY_API_KEY` are configured, the agent sends raw evidence to Azure OpenAI GPT-4.1-mini for advanced consolidation; when unavailable, a deterministic local engine produces complete results with no external dependency.

## Verified Product Imagery — One Hero Photo Per Product

ShelfWise does not return random product photos. A dedicated **image verification pipeline** downloads candidate images and scores them on:

- **White / clean background** — samples edge pixels to detect near-white backgrounds typical of marketplace listings.
- **Image quality** — resolution and aspect-ratio checks filter out thumbnails and banners.
- **Central product focus** — edge-density analysis favors images where the product is centered and in focus.
- **Center fill** — rewards product shots where the item fills the frame with a clean border, penalizing empty frames or tightly cropped logos.
- **Sharpness** — edge-variance filtering rejects blurry or over-compressed photos.
- **Deduplication** — perceptual hashing removes near-duplicate photos.

The pipeline selects **exactly one verified hero image** per product: the single best marketplace-ready photo. No noisy galleries, no placeholder clutter — just one clean, consistent product shot that works across Shopify, Amazon, DoorDash, Uber Eats, and Grubhub.

## End-to-End Workflow

1. A user uploads a CSV or pastes UPCs.
2. The scraper collects structured and unstructured evidence from dozens of sources in parallel.
3. The reasoning agent weights, deduplicates, and resolves the evidence into a single consolidated record.
4. A single verified hero image is selected and ranked.
5. The record is stored in SQLite, streamed to the frontend via SSE, and exported to the marketplace format of choice — including native formats for food-delivery platforms.

## Why It Matters

Restaurants, ghost kitchens, and convenience stores that list on DoorDash, Uber Eats, or Grubhub often receive CSV files from their POS system with hundreds of UPCs and no photos. Manually researching each item — finding the right name, description, and clean photo — is too slow, so menus and catalogs stay incomplete. ShelfWise automates the research, produces trustworthy, cited listings with one verified product photo each, and exports directly to the delivery platform's format — turning a POS export into a complete online catalog in minutes.
