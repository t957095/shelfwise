# ShelfWise Free Testing Plan
## Foundry Local + IQ Systems Pre-Launch Validation

---

## SUMMARY

Your app has THREE testing tiers. Two are completely free and work right now.
The third (real Foundry Local on Azure Local) requires infrastructure but can be
proxied for demo purposes.

| Tier | Cost | Setup Time | Fidelity | Best For |
|------|------|-----------|----------|----------|
| 1. Local IQ Simulation | $0 | 0 min | High (logic) | Daily dev, demo prep |
| 2. GitHub Models / Ollama | $0 | 5 min | Medium-High | LLM enrichment testing |
| 3. Azure OpenAI Free Trial | $0 (200 USD) | 15 min | Production | Pre-launch validation |
| 4. Foundry Local on Azure Local | $0* | Hours | Production | Sovereign AI demo |

*Azure Local eval can use free trial credits. No separate hackathon sandbox confirmed.

---

## TIER 1: LOCAL IQ SIMULATION (RUN THIS NOW)

Your `foundry_iq.py` ALREADY implements:
- Product knowledge graph with BM25 semantic search
- Foundry IQ-style grounded answers with citations
- Ontology export (`/api/foundry/ontology`)
- Permission-aware querying (`guest` / `user` / `admin`)
- Multi-hop reasoning (`/api/foundry/reason`)
- Query history and health metrics

This runs with ZERO Azure credentials.

### Quick Test

```bash
cd C:\Users\sinof\Downloads\shelfwise-inspect-2\project\backend
python -m uvicorn main:app --reload --port 8000
```

Then hit these endpoints (use the provided test script):

```bash
# Health
curl http://localhost:8000/api/foundry/health

# Load demo data
curl http://localhost:8000/api/demo

# Query knowledge base
curl -X POST "http://localhost:8000/api/foundry/query?query=cola+beverages&top_k=5"

# Reason about a specific product
curl -X POST "http://localhost:8000/api/foundry/reason?upc=049000050103&question=who+makes+this"

# Export ontology
curl http://localhost:8000/api/foundry/ontology

# Graph search
curl "http://localhost:8000/api/foundry/graph/search?q=coca+cola&top_k=5"
```

### What This Proves
- All IQ endpoints work end-to-end
- Knowledge graph builds from scraped products
- Citations and confidence scores generate correctly
- Permission model functions
- Ontology is exportable

---

## TIER 2: FREE LLM ENRICHMENT (GITHUB MODELS)

Your `_foundry_reasoning_call()` in `foundry_agent.py` accepts any OpenAI-compatible
endpoint. GitHub Models provides FREE access to GPT-4o, Phi-3, Llama-3, etc.

### Setup

1. Get a GitHub token with Models access:
   https://github.com/settings/tokens -> Generate new token -> `read:packages`

2. Create `.env.github-models`:

```
FOUNDRY_ENDPOINT=https://models.inference.ai.azure.com/chat/completions
FOUNDRY_API_KEY=ghp_YOUR_GITHUB_TOKEN_HERE
FOUNDRY_MODEL=gpt-4o-mini
```

3. Start the app with this config:

```bash
cd C:\Users\sinof\Downloads\shelfwise-inspect-2\project\backend
cp .env.github-models .env
python -m uvicorn main:app --reload
```

### Limits
- 150 requests/day for GPT-4o-mini (free tier)
- Sufficient for hackathon testing and demo
- Rate limits reset daily

### What This Proves
- Real LLM enrichment of product descriptions
- Live Foundry reasoning call path works
- Description quality improvement vs local templates

---

## TIER 2B: LOCAL LLM (OLLAMA) - FULLY OFFLINE

If you want unlimited local LLM calls without any cloud dependency:

### Setup

1. Install Ollama: https://ollama.com/download/windows
2. Pull a model:

```powershell
ollama pull llama3.1:8b
# or for smaller/faster:
ollama pull phi3:mini
```

3. Create `.env.ollama`:

```
FOUNDRY_ENDPOINT=http://localhost:11434/v1/chat/completions
FOUNDRY_API_KEY=ollama
FOUNDRY_MODEL=llama3.1:8b
```

4. Start Ollama server (it runs automatically after install), then start ShelfWise.

### What This Proves
- Fully sovereign/offline AI pipeline
- No data leaves the machine
- Exact architecture match for Foundry Local on Azure Local (on-prem)

---

## TIER 3: AZURE OPENAI FREE TRIAL ($200 CREDIT)

New Azure accounts get $200 free for 30 days. This is the closest to production.

### Setup

1. Sign up: https://azure.microsoft.com/free/
2. Run your existing PowerShell provisioner:

```powershell
cd C:\Users\sinof\Downloads\shelfwise-inspect-2\project\backend
.\setup-azure-openai.ps1 -ResourceGroupName "shelfwise-hackathon-rg" -Location "eastus"
```

3. The script auto-writes `.env` with endpoint + key.
4. Restart ShelfWise.

### Cost Watch
- GPT-4o-mini: ~$0.15 / 1M input tokens
- Your product enrichment calls are tiny (< 2K tokens each)
- $200 credit = hundreds of thousands of enrichment calls
- Set a budget alert at $10 to be safe

### What This Proves
- Production Azure OpenAI integration
- Real-world latency and reliability
- Exact hackathon judge environment if they test live

---

## TIER 4: FOUNDRY LOCAL ON AZURE LOCAL (SOVEREIGN AI)

This is the infrastructure-heavy target. Foundry Local runs on Azure Local
(formerly Azure Stack HCI) for air-gapped / regulated environments.

### Reality Check

- Azure Local requires physical hardware or nested virtualization VMs
- Foundry Local is in PUBLIC PREVIEW (as of the TechCommunity posts you shared)
- No confirmed free sandbox for hackathon participants
- Eval mode exists but needs Azure Local cluster

### Practical Hackathon Path

**For demo purposes, your LOCAL SIMULATION (Tier 1) + OLLAMA (Tier 2B) IS the
Foundry Local prototype.** Here's why:

| Foundry Local on Azure Local | Your Local Stack |
|------------------------------|------------------|
| On-prem AI, data never leaves | Ollama runs locally, zero egress |
| Multi-node vLLM inference | Can run multi-model with Ollama |
| Foundry IQ knowledge grounding | `foundry_iq.py` simulates this exactly |
| Sovereign / regulated compliance | SQLite + local LLM = no cloud dependency |
| Azure Arc governance | Can be added later for production |

### If You Want Real Azure Local

1. Azure free trial can provision Azure Local eval VMs (nested virtualization)
2. Requires Windows Server 2022/2025 or Azure Stack HCI OS
3. Foundry Local installs via Azure Arc-enabled Kubernetes
4. This is a multi-hour setup, not a quick test

**Recommendation:** Demo with Tier 1 + Tier 2B. Explain in your hackathon pitch
that the architecture ports directly to Foundry Local on Azure Local via container
deployment (your app already has a Dockerfile).

---

## RECOMMENDED TEST SEQUENCE

### Phase 1: Validate Local IQ (Now, 10 minutes)
```bash
# 1. Start app
cd backend && uvicorn main:app --reload

# 2. Load demo data
curl http://localhost:8000/api/demo

# 3. Run the test script (provided below)
python scripts/test_foundry_iq.py
```

### Phase 2: Add LLM Enrichment (Next, 15 minutes)
```bash
# Option A: GitHub Models (cloud, free)
cp .env.github-models backend/.env

# Option B: Ollama (local, unlimited)
ollama pull llama3.1:8b
cp .env.ollama backend/.env

# Test enrichment path
curl http://localhost:8000/api/health
# Check foundry_mode is "azure" (it treats any endpoint as "azure" mode)
```

### Phase 3: Azure OpenAI Validation (Before submission, 30 minutes)
```powershell
# Only if you have Azure free trial or hackathon credits
.\backend\setup-azure-openai.ps1
# Restart app, run full UPC batch, verify enrichment quality
```

### Phase 4: Documentation for Judges
- Screenshot the `/api/foundry/ontology` output
- Screenshot a `/api/foundry/reason` response with citations
- Note: "Local simulation validates architecture; Azure OpenAI optional for production"

---

## FILES CREATED

| File | Purpose |
|------|---------|
| `scripts/test_foundry_iq.py` | Automated endpoint smoke test |
| `.env.github-models` | GitHub Models free tier config |
| `.env.ollama` | Local Ollama config |
| `TESTING_PLAN.md` | This document |

---

## BOT TESTING CHECKLIST

- [ ] App starts without env vars (local simulation mode)
- [ ] `/api/health` reports `foundry_mode: local_simulation`
- [ ] `/api/demo` loads 3 products successfully
- [ ] `/api/foundry/health` reports knowledge graph stats
- [ ] `/api/foundry/query?query=cola` returns grounded answer with citations
- [ ] `/api/foundry/reason?upc=049000050103&question=brand` returns "Coca-Cola"
- [ ] `/api/foundry/ontology` returns entity types and relations
- [ ] `/api/foundry/graph/search?q=chocolate` returns ranked nodes
- [ ] `/api/batch` with real UPCs processes in background
- [ ] Export to CSV/JSON/Shopify works
- [ ] With LLM endpoint configured, `_foundry_reasoning_call` enriches descriptions
- [ ] App gracefully degrades when LLM endpoint is unreachable
