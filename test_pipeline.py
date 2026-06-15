"""Test the full ShelfWise CSV import -> scrape -> enrich -> export pipeline."""
import urllib.request
import json
import time
import csv
import io
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = "http://localhost:8000"


def post(path, data=None, json_data=None, headers=None):
    url = BASE + path
    h = headers or {}
    if json_data is not None:
        data = json.dumps(json_data).encode()
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    return json.loads(urllib.request.urlopen(req).read())


def get(path):
    return json.loads(urllib.request.urlopen(BASE + path).read())


def upload_csv(filepath):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    with open(filepath, "rb") as f:
        file_data = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filepath.split("/")[-1].split("\\")[-1]}"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    req = urllib.request.Request(BASE + "/api/upload-csv", data=body, headers=headers, method="POST")
    return json.loads(urllib.request.urlopen(req).read())


def main():
    print("=== 1. Clear existing data ===")
    req = urllib.request.Request(BASE + "/api/clear", method="POST")
    print(json.loads(urllib.request.urlopen(req).read()))

    print("\n=== 2. Upload CSV ===")
    result = upload_csv("sample_upcs.csv")
    print(result)
    job_id = result["job_id"]
    total = result["total"]

    print("\n=== 3. Poll job ===")
    start = time.time()
    for i in range(180):
        time.sleep(1)
        status = get("/api/jobs/" + job_id)
        done = status["completed"] + status["failed"]
        print(f"poll {i+1}: completed={status['completed']} running={status['running']} failed={status['failed']}")
        if done >= total:
            break
    print(f"Total pipeline time: {time.time() - start:.1f}s")

    print("\n=== 4. Verify products ===")
    products_resp = get("/api/products")
    print(f"Products in DB: {products_resp['count']}")
    enriched = 0
    for p in products_resp["products"]:
        print(
            f"  {p['upc']:15} | {p['name'][:35]:35} | brand={p.get('brand','N/A'):12} | "
            f"category={p.get('category','N/A'):18} | enriched={p.get('foundry_enriched')} | "
            f"sdk={p.get('foundry_sdk')} | conf={p.get('confidence')} | status={p['status']}"
        )
        if p.get("foundry_enriched"):
            enriched += 1
    print(f"Foundry enriched: {enriched}/{products_resp['count']}")

    print("\n=== 5. Export formats ===")
    for fmt in ["csv", "json", "shopify", "amazon", "woocommerce", "ebay"]:
        try:
            req = urllib.request.Request(
                BASE + "/api/export",
                data=json.dumps({"format": fmt}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            data = urllib.request.urlopen(req).read()
            print(f"  {fmt}: {len(data)} bytes")
            if fmt == "csv":
                reader = csv.DictReader(io.StringIO(data.decode("utf-8")))
                rows = list(reader)
                print(f"    CSV rows: {len(rows)}")
        except Exception as e:
            print(f"  {fmt}: ERROR {e}")

    print("\n=== 6. Stats ===")
    print(json.dumps(get("/api/stats"), indent=2))


if __name__ == "__main__":
    main()
