#!/usr/bin/env python3
"""
ShelfWise POS Import Demo Script

This script simulates a real retail workflow:
1. Reads UPCs from POS CSV export
2. Submits batch job to ShelfWise API
3. Polls for enrichment completion (Azure Foundry LLM)
4. Exports enriched portfolio
5. Generates summary report with enrichment highlights

Usage: python demo_pos_import.py demo_pos_import.csv
"""

import csv
import json
import sys
import time
import urllib.request
from datetime import datetime

API = "http://localhost:8000"


def read_pos_csv(path):
    """Read UPCs from POS CSV export."""
    products = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append({
                "upc": row["upc"].strip(),
                "quantity": int(row.get("quantity", 0)),
                "unit_price": float(row.get("unit_price", 0)),
                "department": row.get("department", "Unknown"),
            })
    return products


def batch_submit(upcs):
    payload = json.dumps({"upcs": upcs}).encode()
    req = urllib.request.Request(
        f"{API}/api/batch",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def poll_job(job_id, timeout=300):
    """Poll job until complete or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(2)
        with urllib.request.urlopen(f"{API}/api/jobs/{job_id}") as resp:
            job = json.loads(resp.read())
            total = job.get("total", 0)
            completed = job.get("completed", 0)
            failed = job.get("failed", 0)
            if failed > 0:
                print(f"  WARNING: {failed} items failed")
            if completed == total:
                return job
            print(f"  Progress: {completed}/{total} (elapsed {int(time.time() - start)}s)")
    print("  TIMEOUT")
    return None


def get_product(upc):
    try:
        with urllib.request.urlopen(f"{API}/api/products/{upc}") as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  Error fetching {upc}: {e}")
        return None


def export_portfolio():
    payload = json.dumps({"format": "json", "include_images": True}).encode()
    req = urllib.request.Request(
        f"{API}/api/export",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def generate_report(products, pos_data, export_data, output_path="demo_report.md"):
    """Generate markdown report with enrichment highlights."""
    # Build lookup from POS data
    pos_lookup = {p["upc"]: p for p in pos_data}

    # Build lookup from export
    export_lookup = {p["upc"]: p for p in export_data}

    total = len(products)
    complete = sum(1 for p in products if p and p.get("status") == "complete")
    partial = sum(1 for p in products if p and p.get("status") == "partial")
    error = sum(1 for p in products if p and p.get("status") == "error")
    foundry_enriched = sum(
        1
        for p in products
        if p
        and any(
            "Foundry" in t or "Microsoft" in t for t in p.get("reasoning_trace", [])
        )
    )

    lines = []
    lines.append("# ShelfWise POS Import Demo Report")
    lines.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"\n## Summary")
    lines.append(f"- Total SKUs imported: {total}")
    lines.append(f"- Fully enriched: {complete}")
    lines.append(f"- Partially enriched: {partial}")
    lines.append(f"- Failed / unknown: {error}")
    lines.append(f"- Azure Foundry LLM enriched: {foundry_enriched}")
    lines.append(f"- Success rate: {(complete + partial) / total * 100:.1f}%")

    lines.append(f"\n## Enrichment Highlights")
    lines.append(
        "\nProducts enriched by Microsoft Azure Foundry LLM (cross-referencing beyond scraper data):"
    )

    for p in products:
        if not p:
            continue
        upc = p["upc"]
        pos = pos_lookup.get(upc, {})
        has_foundry = any(
            "Foundry" in t or "Microsoft" in t for t in p.get("reasoning_trace", [])
        )
        if has_foundry:
            lines.append(f"\n### {p.get('name', 'Unknown')} (UPC: {upc})")
            lines.append(f"- **Department**: {pos.get('department', 'Unknown')}")
            lines.append(f"- **Status**: {p.get('status', 'unknown')}")
            lines.append(f"- **Confidence**: {p.get('confidence', 0):.2f}")
            lines.append(f"- **Brand**: {p.get('brand', 'Unknown')}")
            lines.append(f"- **Category**: {p.get('category', 'Unknown')}")
            if p.get("description"):
                desc = p["description"][:200]
                if len(p["description"]) > 200:
                    desc += "..."
                lines.append(f"- **Description**: {desc}")
            # Show reasoning trace steps
            trace = p.get("reasoning_trace", [])
            if trace:
                lines.append(f"- **Reasoning trace**:")
                for step in trace:
                    lines.append(f"  - {step}")
            # Show citations
            citations = p.get("citations", [])
            if citations:
                lines.append(f"- **Sources**:")
                for c in citations:
                    lines.append(
                        f"  - {c.get('source', 'Unknown')} (confidence: {c.get('confidence', 0):.2f})"
                    )

    lines.append(f"\n## Raw Data Comparison")
    lines.append(
        "\nBefore vs after enrichment — showing how Foundry LLM resolves conflicts and fills gaps:"
    )

    for p in products:
        if not p:
            continue
        upc = p["upc"]
        pos = pos_lookup.get(upc, {})
        export = export_lookup.get(upc, {})

        lines.append(f"\n### UPC {upc}")
        lines.append(f"- POS input: {pos.get('department', 'Unknown')}, Qty {pos.get('quantity', 0)}")
        lines.append(f"- Enriched name: {p.get('name', 'Unknown')}")
        lines.append(f"- Enriched brand: {p.get('brand', 'Unknown')}")
        lines.append(f"- Enriched category: {p.get('category', 'Unknown')}")
        lines.append(f"- Final status: {p.get('status', 'unknown')}")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\nReport saved to: {output_path}")
    return output_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python demo_pos_import.py <pos_csv_file>")
        sys.exit(1)

    csv_path = sys.argv[1]
    pos_data = read_pos_csv(csv_path)
    upcs = [p["upc"] for p in pos_data]

    print(f"ShelfWise POS Import Demo")
    print(f"========================")
    print(f"Loaded {len(upcs)} SKUs from {csv_path}")
    print(f"Categories: {set(p['department'] for p in pos_data)}")

    # Clear existing data
    print(f"\n[1/5] Clearing existing catalog...")
    clear_req = urllib.request.Request(
        f"{API}/api/clear", data=b"", headers={}, method="POST"
    )
    with urllib.request.urlopen(clear_req) as resp:
        print(f"  {json.loads(resp.read())['message']}")

    # Batch submit
    print(f"\n[2/5] Submitting batch job...")
    chunk_size = 10
    jobs = []
    for i in range(0, len(upcs), chunk_size):
        chunk = upcs[i : i + chunk_size]
        result = batch_submit(chunk)
        jobs.append(result["job_id"])
        print(f"  Batch {i // chunk_size + 1}: {len(chunk)} UPCs -> Job {result['job_id']}")

    # Poll all jobs
    print(f"\n[3/5] Waiting for enrichment (Azure Foundry LLM)...")
    for job_id in jobs:
        print(f"  Job {job_id}:")
        job = poll_job(job_id)
        if job:
            print(f"  Completed {job['completed']}/{job['total']}")

    # Fetch enriched products
    print(f"\n[4/5] Fetching enriched products...")
    products = []
    for upc in upcs:
        p = get_product(upc)
        products.append(p)
        if p:
            has_foundry = any(
                "Foundry" in t or "Microsoft" in t for t in p.get("reasoning_trace", [])
            )
            status_icon = "✓" if p.get("status") == "complete" else "~" if p.get("status") == "partial" else "✗"
            print(f"  {status_icon} {upc}: {p.get('status', 'unknown'):8} conf={p.get('confidence', 0):.2f} foundry={has_foundry} name={p.get('name', 'Unknown')[:35]}")
        else:
            print(f"  ✗ {upc}: FETCH FAILED")

    # Export portfolio
    print(f"\n[5/5] Exporting enriched portfolio...")
    export_data = export_portfolio()
    with open("demo_export.json", "w") as f:
        json.dump(export_data, f, indent=2)
    print(f"  Exported {len(export_data)} products to demo_export.json")

    # Generate report
    print(f"\n[6/6] Generating demo report...")
    report_path = generate_report(products, pos_data, export_data)

    # Final stats
    complete = sum(1 for p in products if p and p.get("status") == "complete")
    partial = sum(1 for p in products if p and p.get("status") == "partial")
    error = sum(1 for p in products if p and p.get("status") == "error")
    foundry_enriched = sum(
        1
        for p in products
        if p
        and any(
            "Foundry" in t or "Microsoft" in t for t in p.get("reasoning_trace", [])
        )
    )

    print(f"\n{'='*50}")
    print(f"DEMO COMPLETE")
    print(f"{'='*50}")
    print(f"Total SKUs: {len(upcs)}")
    print(f"Fully enriched: {complete}")
    print(f"Partially enriched: {partial}")
    print(f"Failed: {error}")
    print(f"Azure Foundry enriched: {foundry_enriched}")
    print(f"Success rate: {(complete + partial) / len(upcs) * 100:.1f}%")
    print(f"\nFiles generated:")
    print(f"  - demo_export.json (enriched portfolio)")
    print(f"  - {report_path} (markdown report)")
    print(f"\nNext steps for demo video:")
    print(f"  1. Open frontend: http://localhost:8000/frontend/index.html")
    print(f"  2. Show batch import from POS CSV")
    print(f"  3. Show enrichment progress with Azure Foundry")
    print(f"  4. Show final portfolio with enriched product cards")
    print(f"  5. Export to multiple formats (CSV, JSON, Excel)")


if __name__ == "__main__":
    main()
