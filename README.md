# ShelfWise - AI Product Portfolio Builder

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE.md)
[![Docker](https://img.shields.io/badge/docker-supported-2496ED.svg)](Dockerfile)

> **Agents League Hackathon 2026 - Reasoning Agents Track**
> Microsoft Foundry | Foundry IQ | Azure OpenAI

---

## The Problem

Small businesses that buy liquidation pallets, wholesale lots, or estate sales often receive hundreds or thousands of items with nothing but a UPC barcode. Turning those barcodes into e-commerce-ready listings is a manual, soul-crushing process. Restaurants, ghost kitchens, and convenience stores that list on DoorDash, Uber Eats, or Grubhub face the same problem: POS exports full of UPCs with no photos or descriptions. Most owners give up and list only a fraction of their catalog, leaving 30-40% of potential revenue on the table.

This is not a hypothetical. Walk through any liquidation warehouse and you will see pallets sitting for months because nobody has time to look up each item, write descriptions, find images, and format listings for Shopify, Amazon, or eBay.

## The Solution

ShelfWise transforms a list of UPC codes into a complete, exportable product portfolio in minutes. It scrapes 8+ public data sources concurrently, runs a multi-step reasoning agent to consolidate conflicting information, generates cited product records, and exports directly to Shopify, Amazon, or generic CSV/JSON.

**Key capabilities:**
- **282 concurrent scrapers** - 8 core sources plus a registry of 270+ additional sources, queried in parallel and limited to the top-weighted sources for speed
- **Multi-step reasoning agent** - Jaccard deduplication, source-weighted field resolution, confidence scoring
- **Verified product imagery** - Downloads and scores every candidate photo for white/clean backgrounds, resolution, central product focus, sharpness, frame fill, and deduplication, then selects exactly one hero image per product
- **Foundry IQ integration** - Optional Azure OpenAI enrichment with JSON-structured responses and full citation trails
- **Real-time SSE streaming** - Watch each UPC get processed live with progress bars
- **11 export formats** - CSV, JSON, Shopify, Amazon, WooCommerce, eBay, Etsy, BigCommerce, DoorDash, Uber Eats, Grubhub
- **Accessibility-first** - WCAG 2.1 AA compliant, keyboard navigation, screen reader support, reduced motion support

## Demo Video

[Watch the 5-minute demo on YouTube](https://youtube.com/your-demo-link) *(placeholder - record and replace before submission)*

## Architecture

![Architecture](architecture.html)

Open `architecture.html` in a browser to view the full interactive architecture diagram.

### Data Flow

1. **Input** - User uploads CSV or enters UPCs manually
2. **Scraping** - Core sources and top-weighted registry sources queried concurrently with rotating user-agents, retry logic, and circuit breakers
3. **Reasoning** - ProductReasoningAgent weights sources, deduplicates names, resolves fields, merges attributes
4. **Image Verification** - Candidate photos are scored for white/clean backgrounds, quality, focus, sharpness, frame fill, and diversity; the single best verified hero image is selected per product
5. **Foundry IQ** - If Azure OpenAI credentials are configured, the agent sends raw data for LLM-based enrichment
6. **Storage** - SQLite database tracks jobs and stores consolidated products
7. **Output** - Live SSE updates to frontend, product cards with verified images/citations, multi-format export

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
| `/api/upload-csv` | POST | Upload CSV with 'upc' column |
| `/api/products` | GET | List all products |
| `/api/products/{upc}` | GET | Get single product |
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
