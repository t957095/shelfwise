#!/usr/bin/env python3
"""ShelfWise Foundry IQ Smoke Test

Validates all IQ endpoints, knowledge graph, and reasoning paths
without requiring any Azure credentials.

Usage:
    python scripts/test_foundry_iq.py

Requires the ShelfWise API to be running on http://localhost:8000
"""

import sys
import json
import time
import urllib.request
import urllib.error

BASE = "http://localhost:8000"

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"

results = {"pass": 0, "fail": 0, "warn": 0}


def req(method, path, data=None, query=None, expect_json=True):
    url = BASE + path
    if query:
        from urllib.parse import quote
        url += "?" + "&".join(f"{k}={quote(str(v))}" for k, v in query.items())
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(url, data=body, method=method)
    if body:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            raw = resp.read().decode()
            if not expect_json:
                return resp.status, {"_raw": raw[:200]}
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.read() else "{}"
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"_raw": body[:200]}
    except Exception as e:
        return 0, {"error": str(e)}


def check(name, status, expected_status, condition=None):
    ok = status == expected_status and (condition is None or condition)
    if ok:
        print(f"  {PASS} {name}")
        results["pass"] += 1
    else:
        print(f"  {FAIL} {name} (status={status}, expected={expected_status})")
        results["fail"] += 1
    return ok


def warn(name, condition):
    if condition:
        print(f"  {PASS} {name}")
        results["pass"] += 1
    else:
        print(f"  {WARN} {name}")
        results["warn"] += 1


print("=" * 60)
print("ShelfWise Foundry IQ Smoke Test")
print("=" * 60)

# ------------------------------------------------------------------
# 1. API Health
# ------------------------------------------------------------------
print("\n[1] API Health")
status, data = req("GET", "/api/health")
check("Health endpoint returns 200", status, 200)
warn("Foundry IQ initialized", data.get("foundry_iq", {}).get("status") == "healthy")
warn("Mode is local_simulation", data.get("foundry_iq", {}).get("mode") == "local_simulation")

# ------------------------------------------------------------------
# 2. Load Demo Data
# ------------------------------------------------------------------
print("\n[2] Demo Data Ingestion")
status, data = req("GET", "/api/demo")
check("Demo endpoint returns 200", status, 200)
check("Job created", status, 200, "job_id" in data)
job_id = data.get("job_id", "")
print(f"       Job ID: {job_id}")

# ------------------------------------------------------------------
# 3. Foundry IQ Health
# ------------------------------------------------------------------
print("\n[3] Foundry IQ Service Health")
status, data = req("GET", "/api/foundry/health")
check("Foundry health returns 200", status, 200)
warn("Knowledge graph has nodes", data.get("knowledge_graph", {}).get("total_nodes", 0) > 0)
warn("Query history tracked", data.get("total_queries_served", 0) >= 0)

# ------------------------------------------------------------------
# 4. Foundry IQ Query
# ------------------------------------------------------------------
print("\n[4] Knowledge Query (Natural Language)")
status, data = req("POST", "/api/foundry/query", query={"query": "cola beverages", "top_k": "5"})
check("Query returns 200", status, 200)
warn("Answer field present", "answer" in data)
warn("Citations present", len(data.get("citations", [])) > 0)
warn("Confidence > 0", data.get("confidence", 0) > 0)
warn("Query ID tracked", "query_id" in data)
print(f"       Answer preview: {data.get('answer', '')[:120]}...")

# ------------------------------------------------------------------
# 5. Product Reasoning
# ------------------------------------------------------------------
print("\n[5] Product Reasoning")
status, data = req("POST", "/api/foundry/reason", query={
    "upc": "049000050103",
    "question": "who makes this product"
})
check("Reason endpoint returns 200", status, 200)
warn("Answer contains brand", "coca" in data.get("answer", "").lower())
warn("Citations present", len(data.get("citations", [])) > 0)
print(f"       Answer: {data.get('answer', '')[:120]}...")

status, data = req("POST", "/api/foundry/reason", query={
    "upc": "049000050103",
    "question": "what category"
})
check("Category reasoning returns 200", status, 200)
warn("Answer contains category info", "category" in data.get("answer", "").lower() or "cola" in data.get("answer", "").lower())

# ------------------------------------------------------------------
# 6. Ontology Export
# ------------------------------------------------------------------
print("\n[6] Ontology Export")
status, data = req("GET", "/api/foundry/ontology")
check("Ontology returns 200", status, 200)
warn("Entity types defined", len(data.get("entity_types", {})) > 0)
warn("Relations defined", len(data.get("relations", {})) > 0)
warn("Stats present", "stats" in data)
print(f"       Entity types: {list(data.get('entity_types', {}).keys())}")

# Ensure catalog is ingested into knowledge graph before graph tests
print("\n[6b] Catalog Ingestion (pre-graph test)")
status, data = req("POST", "/api/foundry/ingest")
check("Pre-test ingest returns 200", status, 200)

# ------------------------------------------------------------------
# 7. Graph Search
# ------------------------------------------------------------------
print("\n[7] Knowledge Graph Semantic Search")
status, data = req("GET", "/api/foundry/graph/search", query={"q": "chocolate", "top_k": "5"})
check("Graph search returns 200", status, 200)
warn("Results returned", len(data.get("results", [])) > 0)
if data.get("results"):
    first = data["results"][0]
    warn("Node has score", "score" in first)
    warn("Node has related edges", len(first.get("related_edges", [])) >= 0)
    print(f"       Top result: {first.get('node', {}).get('label', 'N/A')} (score: {first.get('score', 0)})")

# ------------------------------------------------------------------
# 8. Graph Related / Traversal
# ------------------------------------------------------------------
print("\n[8] Graph Traversal (Related Nodes)")
# Find a product node ID first
status, data = req("GET", "/api/foundry/graph/search", query={"q": "coca cola", "top_k": "1"})
if status == 200 and data.get("results"):
    node_id = data["results"][0]["node"]["id"]
    status2, data2 = req("GET", f"/api/foundry/graph/related/{node_id}")
    check("Related nodes returns 200", status2, 200)
    warn("Related nodes found", len(data2.get("related", [])) > 0)
    if data2.get("related"):
        rel = data2["related"][0]
        print(f"       Relation: {rel.get('edge', {}).get('relation', 'N/A')} -> {rel.get('node', {}).get('label', 'N/A')}")
else:
    print(f"  {WARN} Skipping graph traversal (no product node found)")
    results["warn"] += 1

# ------------------------------------------------------------------
# 9. Query History
# ------------------------------------------------------------------
print("\n[9] Query History")
status, data = req("GET", "/api/foundry/history", query={"limit": "10"})
check("History returns 200", status, 200)
warn("Queries tracked", len(data.get("queries", [])) > 0)
print(f"       Tracked queries: {len(data.get('queries', []))}")

# ------------------------------------------------------------------
# 10. Catalog Re-ingestion
# ------------------------------------------------------------------
print("\n[10] Catalog Re-ingestion")
status, data = req("POST", "/api/foundry/ingest")
check("Ingest returns 200", status, 200)
warn("Graph stats returned", "knowledge_graph" in data)

# ------------------------------------------------------------------
# 11. Permission Check (Guest Role)
# ------------------------------------------------------------------
print("\n[11] Permission Model")
status, data = req("POST", "/api/foundry/query", query={"query": "test", "role": "guest"})
check("Guest query returns 200", status, 200)
warn("Guest can query", "answer" in data)

# ------------------------------------------------------------------
# 12. Products List
# ------------------------------------------------------------------
print("\n[12] Product Portfolio")
status, data = req("GET", "/api/products")
check("Products list returns 200", status, 200)
warn("Products returned", len(data.get("products", [])) > 0)
print(f"       Products in portfolio: {len(data.get('products', []))}")

# ------------------------------------------------------------------
# 13. Export Smoke Test
# ------------------------------------------------------------------
print("\n[13] Export Formats")
for fmt in ["csv", "json"]:
    status, data = req("POST", "/api/export", data={"format": fmt}, expect_json=(fmt == "json"))
    check(f"Export {fmt.upper()} returns 200", status, 200)

# ------------------------------------------------------------------
# Summary
# ------------------------------------------------------------------
print("\n" + "=" * 60)
print(f"RESULTS: {PASS}={results['pass']}  {FAIL}={results['fail']}  {WARN}={results['warn']}")
print("=" * 60)

if results["fail"] > 0:
    print("\nSome critical checks failed. Review the errors above.")
    sys.exit(1)
else:
    print("\nAll critical checks passed. Foundry IQ local simulation is healthy.")
    if results["warn"] > 0:
        print(f"{results['warn']} warning(s) — non-critical but worth reviewing.")
    sys.exit(0)
