import sys, json

data = json.load(sys.stdin)
print(f"Total products: {len(data)}")
print(f"Complete: {sum(1 for p in data if p['status'] == 'complete')}")
print(f"Error: {sum(1 for p in data if p['status'] == 'error')}")
print()
for p in data:
    name = p['name'] or 'None'
    print(f"  {p['upc']}: {p['status']:8} conf={p['confidence']:.2f} name={name}")
