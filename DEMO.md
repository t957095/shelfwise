# ShelfWise Hackathon Demo — POS Import with Azure Foundry Enrichment

## Scenario

A small grocery store has 19 SKUs across 14 departments. They export a CSV with UPCs, quantities, and prices. ShelfWise ingests the CSV, enriches every product using Microsoft Azure Foundry LLM, and produces a polished portfolio.

## Demo Script (for video recording)

### Scene 1: The POS Export (30 sec)
Show `demo_pos_import.csv` in a spreadsheet or text editor. Point out:
- 19 SKUs from 14 departments
- Mix of well-known brands (Coca-Cola, Lay's) and unknown products
- Columns: UPC, quantity, unit_price, department

### Scene 2: Import & Enrichment (60 sec)
Run the demo script. Show terminal output:
- Batch job submission
- Real-time progress: "Progress: 5/19 (elapsed 12s)"
- Completion: "Job complete: 19/19"
- Highlight: "Azure Foundry enriched: 19/19"

### Scene 3: The Portfolio (60 sec)
Open frontend at `http://localhost:8000/frontend/index.html`
Show product cards with images, names, brands, categories. Hover to show reasoning trace.

### Scene 4: Export & Delivery (30 sec)
Show exported files: `demo_export.json`, `demo_report.md`. Mention CSV/Excel/JSON support.

### Scene 5: The Microsoft Story (30 sec)
Highlight Azure Foundry integration, cross-referencing, confidence scores 0.25 to 1.00.

## Results

| Metric | Value |
|--------|-------|
| Total SKUs | 19 |
| Fully enriched | 18 |
| Partially enriched | 1 |
| Failed | 0 |
| Azure Foundry enriched | 19 |
| Success rate | **100%** |
| Departments | 14 |
| Manufacturers | 10+ |

## Files Generated

- `demo_pos_import.csv` — POS export with 19 SKUs
- `demo_export.json` — enriched portfolio (19 products)
- `demo_report.md` — detailed enrichment report
- `scripts/demo_pos_import.py` — automated demo script

## Key Technical Wins

1. Azure Foundry LLM Integration via gpt-4o
2. Cross-manufacturer coverage (Coca-Cola, PepsiCo, Frito-Lay, Kellogg's, etc.)
3. Graceful degradation when scrapers fail (Foundry LLM fallback)
4. Real-time progress tracking
5. Multi-format export (JSON, CSV, Excel, Markdown)

## Code Changes

- `backend/foundry_agent.py`: Fixed LLM enrichment to fire even when scrapers return empty
- Added `asyncio` import for async LLM calls
- Fixed Azure SDK endpoint path
- Added `.gitignore` entries for database WAL files

## GitHub Repository

https://github.com/t957095/shelfwise
