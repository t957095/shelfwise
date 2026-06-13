import json, sys, time, urllib.request

API = "http://localhost:8000"

def upc_list(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip().isdigit() and len(line.strip()) >= 10]

def batch_submit(upcs):
    payload = json.dumps({"upcs": upcs}).encode()
    req = urllib.request.Request(f"{API}/api/batch", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def poll_job(job_id, timeout=180):
    for _ in range(timeout):
        time.sleep(1)
        with urllib.request.urlopen(f"{API}/api/jobs/{job_id}") as resp:
            job = json.loads(resp.read())
            if job.get("failed", 0) > 0:
                print(f"  Job FAILED: {job}")
                return None
            if job.get("completed", 0) == job.get("total", 0):
                return job
    print("  TIMEOUT")
    return None

def export_portfolio():
    payload = json.dumps({"format": "json", "include_images": True}).encode()
    req = urllib.request.Request(f"{API}/api/export", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def main():
    if len(sys.argv) < 2:
        print("Usage: python demo_batch.py <upcs_file>")
        sys.exit(1)

    upcs = upc_list(sys.argv[1])
    print(f"Loaded {len(upcs)} UPCs from {sys.argv[1]}")

    # Batch submit in chunks of 10
    chunk_size = 10
    jobs = []
    for i in range(0, len(upcs), chunk_size):
        chunk = upcs[i:i+chunk_size]
        print(f"Submitting batch {i//chunk_size + 1}: {len(chunk)} UPCs...")
        result = batch_submit(chunk)
        jobs.append(result["job_id"])
        print(f"  Job ID: {result['job_id']}")

    # Poll all jobs
    print("\nPolling jobs...")
    for job_id in jobs:
        print(f"  Job {job_id}...", end="", flush=True)
        job = poll_job(job_id)
        if job:
            print(f" DONE ({job['completed']}/{job['total']})")

    # Export
    print("\nExporting portfolio...")
    export = export_portfolio()
    print(f"  Exported {export['count']} products")
    with open("demo_export.json", "w") as f:
        json.dump(export, f, indent=2)
    print("  Saved to demo_export.json")

    # Summary
    print("\n=== DEMO SUMMARY ===")
    print(f"Products imported: {len(upcs)}")
    print(f"Portfolio exported: {export['count']} products")
    print(f"Export file: demo_export.json")

if __name__ == "__main__":
    main()
