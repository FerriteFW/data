"""Check a build before it's published: each source that's there must look whole.

python3 check.py out
"""

import json
import os
import sys

from airlines import build as airlines

# airlines: the hand-written list (517 rows at its start); fewer than this means a truncated file.
LEAST = {"tafl": 100000, "fcc": 500000, "airports": 15000, "repeaters": 8000, "satellites": 8, "airlines": 660}

top = json.load(open(f"{sys.argv[1]}/index.json"))
rows = {s["source"]: s["rows"] for s in top["sources"]}
print(rows)
assert rows, "no sources"
for name, n in rows.items():
    assert n > LEAST.get(name, 0), f"{name} looks short: {n} rows"
if "airlines" in rows:
    # Valid codes, short ASCII names, sorted by IATA, no IATA or ICAO twice.
    published = airlines.read(os.path.join(sys.argv[1], "airlines", airlines.FILE))
    bad = airlines.problems(published)
    assert not bad, f"airlines: {len(bad)} problems: {bad[:5]}"
    assert len(published) == rows["airlines"], "airlines: the index and the file disagree"
