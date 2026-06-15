# ShelfWise — Project Description

**Agents League Hackathon 2026 — Reasoning Agents Track**

ShelfWise turns a list of UPC barcodes into a complete, e-commerce-ready product portfolio. It is built around a **Microsoft Foundry IQ-style reasoning layer** that gathers multi-source evidence, resolves conflicts, generates cited product records, and exports them to Shopify, Amazon, WooCommerce, eBay, Etsy, BigCommerce, or CSV/JSON.

## Foundry IQ Integration

At the center of ShelfWise is a reasoning agent that mirrors Foundry IQ patterns:

- **Multi-source evidence retrieval** — queries 8 core data sources (Open Food Facts, UPCItemDB, BarcodeLookup, Go-UPC, Buycott, EANdata, Brave Search, Google Search) plus a registry of 270+ additional sources, all concurrently.
- **Source-weighted conflict resolution** — each source is weighted by historical reliability; the agent resolves disagreements across name, brand, category, description, and attributes using Jaccard deduplication and weighted voting.
- **Grounded citations** — every field in the consolidated record carries a citation with source URL, fields contributed, and confidence score, producing an auditable evidence trail.
- **LLM enrichment fallback** — when `FOUNDRY_ENDPOINT` and `FOUNDRY_API_KEY` are configured, the agent sends raw evidence to Azure OpenAI GPT-4.1-mini for advanced consolidation; when unavailable, a deterministic local engine produces complete results with no external dependency.

## Verified Product Imagery

ShelfWise does not return random product photos. A dedicated **image verification pipeline** downloads candidate images and scores them on:

- **White / clean background** — samples edge pixels to detect near-white backgrounds typical of marketplace listings.
- **Image quality** — resolution and aspect-ratio checks filter out thumbnails and banners.
- **Central product focus** — edge-density analysis favors images where the product is centered and in focus.
- **Deduplication** — perceptual hashing removes near-duplicate photos and keeps a diverse set of verified angles.

Only images that pass verification are surfaced as the product's gallery, with the best photo selected as the primary image.

## End-to-End Workflow

1. A user uploads a CSV or pastes UPCs.
2. The scraper collects structured and unstructured evidence from dozens of sources in parallel.
3. The reasoning agent weights, deduplicates, and resolves the evidence into a single consolidated record.
4. Verified images are selected and ranked.
5. The record is stored in SQLite, streamed to the frontend via SSE, and exported to the marketplace format of choice.

## Why It Matters

Liquidation buyers, estate-sale resellers, and small wholesalers often receive pallets of items with only a UPC. Manually researching each item is too slow, so valuable inventory sits unsold. ShelfWise automates the research, produces trustworthy, cited listings, and ensures the photos are clean enough for consumer marketplaces — turning barcodes into revenue in minutes.
