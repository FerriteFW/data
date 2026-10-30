"""Build every source into out/: per-source tiles and index.json, a top-level index.json, CNAME.

python3 build.py --cache DIR [--out out] [--download] [--only tafl|fcc]
"""

import argparse
import datetime
import json
import os
import shutil

import common
from fcc import build as fcc
from tafl import build as tafl

SOURCES = {"tafl": tafl, "fcc": fcc}
ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cache", required=True, help="download folder (keep it outside the repository)")
    p.add_argument("--out", default="out")
    p.add_argument("--download", action="store_true", help="download again even if cached")
    p.add_argument("--only", choices=sorted(SOURCES), action="append")
    a = p.parse_args()
    today = datetime.date.today().isoformat()
    os.makedirs(a.out, exist_ok=True)
    top = {"build_date": today, "url": "https://data.ferritefw.dev", "sources": []}
    for name in a.only or list(SOURCES):
        shutil.rmtree(os.path.join(a.out, name), ignore_errors=True)
        rows, meta = SOURCES[name].build(a.cache, a.download)
        meta["build_date"] = today
        index = common.write_source(a.out, name, rows, meta)
        top["sources"].append({k: index[k] for k in (
            "source", "title", "source_date", "licence", "licence_url", "attribution", "rows")}
            | {"index": f"{name}/index.json", "tiles": len(index["tiles"])})
    with open(os.path.join(a.out, "index.json"), "w", encoding="utf-8") as f:
        json.dump(top, f, separators=(",", ":"), ensure_ascii=False)
    shutil.copy(os.path.join(ROOT, "CNAME"), os.path.join(a.out, "CNAME"))
    open(os.path.join(a.out, ".nojekyll"), "w").close()
    print(f"Wrote {a.out}/index.json", flush=True)


if __name__ == "__main__":
    main()
