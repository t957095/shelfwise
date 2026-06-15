import asyncio
import httpx
import time
import sys
sys.path.insert(0, '.')
from backend.scraper import UPCScraper

async def main():
    async with httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_connections=100, max_keepalive_connections=50)) as client:
        scraper = UPCScraper(client)
        upc = "049000050103"
        start = time.time()
        results = await scraper.scrape_all(upc)
        elapsed = time.time() - start
        success = [r for r in results if r.get('success')]
        print(f"Elapsed: {elapsed:.1f}s")
        print(f"Total results: {len(results)}")
        print(f"Successful: {len(success)}")
        for r in success[:5]:
            print(f"  {r['source']:25} | {r.get('name','N/A')[:30]:30} | {r.get('brand','N/A')}")

asyncio.run(main())
