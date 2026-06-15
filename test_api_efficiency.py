import urllib.request
import json
import time

UPC = "078000083713"

req = urllib.request.Request(
    "http://localhost:8000/api/batch",
    data=json.dumps({"upcs": [UPC], "auto_scrape": True}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
job = json.loads(urllib.request.urlopen(req).read())["job_id"]
print("Job:", job)
start = time.time()

for i in range(60):
    time.sleep(2)
    status = json.loads(urllib.request.urlopen("http://localhost:8000/api/jobs/" + job).read())
    print(f"poll {i+1}: completed={status['completed']} running={status['running']} failed={status['failed']}")
    if status["completed"] + status["failed"] >= status["total"]:
        break

elapsed = time.time() - start
p = json.loads(urllib.request.urlopen("http://localhost:8000/api/products/" + UPC).read())
print(f"\nElapsed: {elapsed:.1f}s")
print("Name:", p.get("name"))
print("Brand:", p.get("brand"))
print("Category:", p.get("category"))
print("Foundry enriched:", p.get("foundry_enriched"))
print("Foundry SDK:", p.get("foundry_sdk"))
print("Confidence:", p.get("confidence"))
print("Status:", p.get("status"))
