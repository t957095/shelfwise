# ShelfWise: AI Product Portfolio Builder for Small Businesses

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)
[![Docker](https://img.shields.io/badge/docker-supported-2496ED.svg)](Dockerfile)

> **Agents League Hackathon 2026 - Reasoning Agents Track**
> Microsoft Foundry | Foundry IQ | Azure OpenAI
>
> Turn a spreadsheet of UPCs and SKUs into a complete, market-ready product catalog with verified photos, titles, and descriptions powered by multi-step reasoning and Microsoft Foundry IQ.

---

## The Problem

When someone buys a pallet of inventory, they often receive hundreds of products with nothing but UPC barcodes or internal SKUs on the packaging. Before they can sell anything online, they have to figure out what each item is — searching Google, checking marketplaces, comparing listings, finding product photos, copying specifications, and writing descriptions.

At around 8 minutes per item, a pallet with 400 products can require more than 50 hours of manual work before anything is listed for sale. For many small businesses, that work never gets done. Inventory sits in storage instead of generating revenue.

## The Solution

ShelfWise turns a spreadsheet of UPCs and SKUs into a complete, market-ready product catalog. Users upload a CSV or paste identifiers directly into the app. The system searches across the web — retailer listings, manufacturer pages, marketplaces, specialty stores, distributor catalogs, and public product databases — to gather evidence for each product.

A multi-step reasoning agent resolves conflicting names, deduplicates evidence, scores source reliability, and builds a cited product record. Verified images are ranked into a gallery of up to 5 marketplace-ready photos. The final catalog exports to Shopify, Amazon Seller Central, eBay, Facebook Marketplace, WooCommerce, Etsy, BigCommerce, DoorDash, Uber Eats, Grubhub, or generic CSV/JSON.

**Key capabilities:**
- **Web-wide evidence gathering** — 10 core sources plus a registry of 270+ additional sources, queried concurrently. Searches the broader web, not just a fixed UPC catalog.
- **Multi-step reasoning agent** — Jaccard deduplication, weighted brand/category resolution, attribute normalization, confidence scoring, and grounded citations.
- **Verified product imagery** — Downloads and scores every candidate photo for white/clean backgrounds, resolution, central product focus, sharpness, frame fill, and source validity, then returns a ranked gallery of up to 5 verified multi-angle photos per product.
- **Name-based image search fallback** — When a barcode has no public match, ShelfWise searches the web by product name/brand and verifies those images.
- **Manual upload & review** — Users can delete auto-selected images or upload their own through the image manager on each product card.
- **Foundry IQ integration** — Optional Azure OpenAI enrichment with JSON-structured responses and full citation trails.
- **Real-time SSE streaming** — Watch each UPC get processed live with progress bars.
- **11 export formats** — CSV, JSON, Shopify, Amazon, WooCommerce, eBay, Etsy, BigCommerce, DoorDash, Uber Eats, Grubhub.
- **Accessibility-first** — WCAG 2.1 AA compliant, keyboard navigation, screen reader support, reduced motion support.

## Demo Video

[Watch the 5-minute demo on YouTube](https://youtube.com/your-demo-link) *(placeholder - record and replace before submission)*

## Architecture

![Architecture](architecture.html)

Open `architecture.html` in a browser to view the full interactive architecture diagram.

### Data Flow

1. **Input** - User uploads a CSV or enters UPCs/SKUs manually
2. **Scraping** - Core sources and top-weighted registry sources queried concurrently with rotating user-agents, retry logic, circuit breakers, and health tracking
3. **Name-Based Image Search Fallback** - When no public UPC match exists, the system searches the web by product name/brand
4. **Reasoning** - ProductReasoningAgent weights sources, deduplicates names, resolves fields, merges attributes, and generates citations
5. **Image Verification** - Candidate photos are scored for white/clean backgrounds, quality, focus, sharpness, frame fill, source validity, and perceptual diversity; a ranked gallery of up to 5 verified multi-angle images is selected per product
6. **Foundry IQ** - If Azure OpenAI credentials are configured, the agent sends raw data for LLM-based enrichment
7. **Storage** - SQLite database tracks jobs and stores consolidated products
8. **Output** - Live SSE updates to frontend, product cards with verified images/citations, manual upload/review, multi-format export

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Scraping | httpx, BeautifulSoup4, async concurrency |
| Reasoning | Custom multi-step agent with Jaccard similarity |
| AI/LLM | Azure OpenAI GPT-4.1-mini (optional) |
| Database | SQLite (file-based, zero config) |
| Frontend | Vanilla JS, CSS Grid/Flexbox, SSE |
| DevOps | Docker, docker-compose, GitHub Actions |

## Quick Start

### Option 1: Local Python

```bash
# Clone the repo
git clone https://github.com/t957095/shelfwise.git
cd shelfwise

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# (Optional) Set up Azure OpenAI
# cd backend && ./setup-azure-openai.ps1  # Windows PowerShell

# Run the server
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# Open http://localhost:8000/app in your browser
```

### Option 2: Docker

```bash
docker-compose up --build

# Open http://localhost:8000/app in your browser
```

### Option 3: Windows (PowerShell)

```powershell
cd backend
.\setup-azure-openai.ps1  # Auto-provisions Azure OpenAI
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in your values:

```env
# Required for Foundry IQ integration
FOUNDRY_ENDPOINT=https://your-resource.openai.azure.com/openai/deployments/gpt-4.1-mini/chat/completions?api-version=2024-02-01
FOUNDRY_API_KEY=your-azure-openai-key
FOUNDRY_MODEL=gpt-4.1-mini

# Optional - enhances web scraping
BRAVE_API_KEY=your-brave-search-key
GOOGLE_API_KEY=your-google-api-key
GOOGLE_CX=your-programmable-search-engine-id
```

**Never commit `.env` to Git.** It is already in `.gitignore`.

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | App info and feature list |
| `/app` | GET | Web application (frontend) |
| `/api/health` | GET | Health check with feature flags |
| `/api/demo` | GET | Load 3 demo UPCs |
| `/api/batch` | POST | Submit UPCs for processing |
| `/api/upload-csv` | POST | Upload POS CSV; auto-detects UPC/EAN/SKU/PLU, accepts `max_rows` query param |
| `/api/upload-csv/preview` | POST | Preview a POS CSV: detected columns and sample UPCs |
| `/api/products` | GET | List all products |
| `/api/products/{upc}` | GET | Get single product |
| `/api/products/{upc}/images` | POST | Upload a product image |
| `/api/products/{upc}/images` | DELETE | Remove a product image by URL |
| `/api/export` | POST | Export as csv/json/shopify/amazon |
| `/api/jobs/{job_id}` | GET | Get job status |
| `/api/jobs/{job_id}/stream` | GET | SSE stream of live updates |
| `/api/stats` | GET | Portfolio analytics and statistics |
| `/api/products/{upc}/compare` | GET | Compare raw vs consolidated data |
| `/api/clear` | POST | Clear all products and jobs |

### Example: Submit UPCs

```bash
curl -X POST http://localhost:8000/api/batch \
  -H "Content-Type: application/json" \
  -d '{"upcs": ["049000050103", "022000020806"], "auto_scrape": true}'
```

### Example: Export to Shopify

```bash
curl -X POST http://localhost:8000/api/export \
  -H "Content-Type: application/json" \
  -d '{"format": "shopify"}' \
  --output shelfwise-shopify.csv
```

## Microsoft Foundry IQ Integration

ShelfWise integrates with Microsoft Foundry IQ through Azure OpenAI Service. The integration is **architecturally complete and functional**:

1. **Knowledge Retrieval** - The scraper acts as the knowledge retrieval layer, pulling structured and unstructured data from 8 public sources
2. **Citations** - Every field in the consolidated record includes source attribution with confidence scores (Foundry IQ-style grounding)
3. **LLM Enrichment** - When `FOUNDRY_ENDPOINT` and `FOUNDRY_API_KEY` are configured, the reasoning agent sends raw source data to GPT-4.1-mini for advanced consolidation, then merges the LLM output back into the final record with a +0.15 confidence boost
4. **Graceful Degradation** - If Foundry is unavailable, the deterministic local reasoning engine produces complete, high-quality results without any external dependency

Run `backend/setup-azure-openai.ps1` to automatically provision the Azure OpenAI resource and configure the connection.

## Testing

```bash
# Run linting
ruff check backend/
ruff format --check backend/

# Run tests
pytest tests/ -v

# Test health endpoint
curl http://localhost:8000/api/health
```

## Project Structure

```
shelfwise/
├── backend/
│   ├── main.py              # FastAPI app with SSE streaming
│   ├── models.py            # Pydantic data models
│   ├── database.py          # SQLite layer
│   ├── scraper.py           # Async scraper with 270+ source registry
│   ├── foundry_agent.py     # Multi-step reasoning agent + Azure OpenAI
│   ├── image_verifier.py    # Verified product photo pipeline
│   ├── setup-azure-openai.ps1  # One-click Azure provisioning
│   └── .env.example         # Environment template
├── frontend/
│   ├── index.html           # Accessible UI with ARIA labels
│   ├── styles.css           # Dark mode, responsive grid
│   └── app.js               # SSE client, product rendering, export
├── architecture.html        # Interactive architecture diagram
├── Dockerfile               # Multi-stage production build
├── docker-compose.yml       # One-command deploy
├── requirements.txt         # Python dependencies
└── .github/workflows/ci.yml # GitHub Actions CI
```

## Hackathon Submission Details

- **Track:** Reasoning Agents (Microsoft Foundry)
- **IQ Layer:** Foundry IQ (agentic knowledge retrieval + citation generation)
- **Repository:** https://github.com/t957095/shelfwise
- **Demo Video:** [YouTube link](https://youtube.com/your-demo-link)
- **Architecture Diagram:** Open `architecture.html`

## Accessibility

ShelfWise was built with accessibility as a first-class requirement:
- WCAG 2.1 AA compliant color contrast ratios
- Full keyboard navigation with visible focus indicators
- ARIA labels on all interactive elements
- Screen reader announcements for live status updates
- `prefers-reduced-motion` support
- `prefers-contrast: high` support
- Skip-to-content link for keyboard users

## License

MIT License - see [LICENSE.md](LICENSE.md)

## Contact

For questions or issues, open a GitHub issue or reach out on the [Agents League Discord](https://aka.ms/agentsleague/discord).

---

Built with ⚡ by the ShelfWise team for the Microsoft Agents League Hackathon 2026.
