# ShelfWise Demo Video Script
## Agents League Hackathon 2026 - 5 Minute Demo

---

## Setup (Do this before recording)

1. Start the server: `cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000`
2. Open Chrome in full screen: `http://localhost:8000/app/`
3. Clear any existing data: `curl -X POST http://localhost:8000/api/clear`
4. Have this script open on a second monitor

---

## Scene 1: The Problem (0:00 - 0:45)

**Visual:** Show the empty ShelfWise dashboard. Then cut to a quick shot of a messy warehouse or liquidation pallet (stock footage or photo).

**Script:**
> "Small businesses that buy liquidation pallets, wholesale lots, or estate sales get hundreds of items with nothing but a UPC barcode. Turning those barcodes into e-commerce listings is manual and painful. Most owners give up and sell bulk-only, leaving 30 to 40 percent of revenue on the table."

**Transition:** Cut back to ShelfWise dashboard.

---

## Scene 2: The Solution Intro (0:45 - 1:15)

**Visual:** Type "ShelfWise" in the browser address bar, hit Enter. Show the app loading with the dark theme.

**Script:**
> "ShelfWise is an AI product portfolio builder. You feed it UPC codes, it scrapes the internet across eight public data sources, runs a multi-step reasoning agent to consolidate conflicting information, and exports directly to Shopify, Amazon, or CSV."

**Action:** Point cursor at the header, hover over the badge "Microsoft Foundry Powered."

---

## Scene 3: Live Processing Demo (1:15 - 2:45)

**Visual:** Click "Load Demo" button. Watch the SSE stream in real-time.

**Script:**
> "Let's process three real UPCs live. Coca-Cola, M-and-M's, and Pepsi. Watch the progress bar update in real-time as each source responds."

**Action:**
1. Click "Load Demo"
2. Watch the status section appear with progress bar
3. Narrate as numbers change: "Open Food Facts responded first... UPCItemDB found images... Go-UPC confirmed the name..."
4. Wait for all 3 to complete (about 10-15 seconds)

**Script (while waiting):**
> "The scraper uses rotating user agents and respects rate limits. Each source gets a confidence weight based on historical accuracy. Open Food Facts is weighted at ninety percent, Google Search at forty."

---

## Scene 4: Product Cards (2:45 - 3:30)

**Visual:** Scroll through the product cards.

**Script:**
> "Here's what we got. Coca-Cola: complete record with brand, category, description, and eight images from multiple sources. Confidence: one hundred percent."

**Action:**
1. Hover over the Coca-Cola card
2. Click the "Reasoning" button
3. Walk through the reasoning trace modal step by step

**Script:**
> "Click into the reasoning trace and you can see exactly how the agent decided each field. It weighted four sources, deduplicated names using Jaccard similarity, merged ten attributes, and computed a confidence score. Every field has source attribution with citations."

**Action:** Close modal, scroll to Pepsi card, show it also has 100% confidence.

---

## Scene 5: Portfolio Analytics (3:30 - 3:50)

**Visual:** Scroll up to the Portfolio Analytics section.

**Script:**
> "The analytics dashboard shows portfolio-level stats: average confidence, quality distribution, category breakdown, and which data sources contributed the most."

**Action:** Point at each stat briefly.

---

## Scene 6: Export (3:50 - 4:20)

**Visual:** Scroll to Export Portfolio section.

**Script:**
> "Now export to any format. CSV for spreadsheets, JSON for developers, Shopify product import, or Amazon flat file. One click and it's done."

**Action:**
1. Click "Shopify" export button
2. Show the downloaded file in Downloads folder
3. Open it briefly to show the columns

---

## Scene 7: Architecture & Tech Stack (4:20 - 4:50)

**Visual:** Switch to the architecture diagram (open `architecture.html` in a new tab).

**Script:**
> "Under the hood: FastAPI backend, eight concurrent scrapers with httpx, a custom multi-step reasoning agent, optional Azure OpenAI enrichment through Microsoft Foundry IQ, SQLite database, and a vanilla JavaScript frontend with SSE streaming, dark mode, and full WCAG accessibility compliance."

**Action:** Pan across the diagram, pointing at each layer.

---

## Scene 8: Closing (4:50 - 5:00)

**Visual:** Cut back to the ShelfWise dashboard showing all three products.

**Script:**
> "ShelfWise. From barcode to business-ready listings in minutes. Built for the Microsoft Agents League Hackathon 2026."

**End card:** Show GitHub repo URL and your name.

---

## Recording Tips

- Use OBS or similar to capture the browser tab
- Record at 1920x1080, 60fps
- Use a clean browser profile (no extensions visible)
- Speak clearly and at a normal pace
- If a scraper is slow, narrate through it - don't leave dead air
- Have the demo pre-loaded as backup in case of network issues
- Total target: 4:30 - 5:00 minutes
