"""Check a build before it's published: each source that's there must look whole.

python3 check.py out
"""

import json
import sys

LEAST = {"tafl": 100000, "fcc": 500000, "airports": 15000, "repeaters": 8000}

top = json.load(open(f"{sys.argv[1]}/index.json"))
rows = {s["source"]: s["rows"] for s in top["sources"]}
print(rows)
assert rows, "no sources"
for name, n in rows.items():
    assert n > LEAST.get(name, 0), f"{name} looks short: {n} rows"
