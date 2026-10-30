"""Build every source into out/: per-source tiles and index.json, a top-level index.json, CNAME.

python3 build.py --cache DIR [--out out] [--download] [--only tafl|fcc|airports]
"""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import zipfile

import common
from airports import build as airports
from fcc import build as fcc
from tafl import build as tafl

SOURCES = {"tafl": tafl, "fcc": fcc, "airports": airports}
ROOT = os.path.dirname(os.path.abspath(__file__))


def write_bundle(out, name):
    """out/<source>.zip: the whole source (its index and every tile) in one download, for offline use."""
    path = os.path.join(out, name + ".zip")
    d = os.path.join(out, name)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(os.listdir(d)):
            z.write(os.path.join(d, f), f"{name}/{f}")
    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    size = os.path.getsize(path)
    print(f"{name}: {name}.zip {size / 1e6:.1f} MB", flush=True)
    return {"bundle": f"{name}.zip", "bundle_bytes": size, "bundle_sha256": sha}


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
        index = common.write_source(a.out, name, rows, meta, getattr(SOURCES[name], "LEVEL", 4))
        bundle = write_bundle(a.out, name)
        top["sources"].append({k: index[k] for k in (
            "source", "title", "source_date", "licence", "licence_url", "attribution", "rows")}
            | {"index": f"{name}/index.json", "tiles": len(index["tiles"])} | bundle)
    with open(os.path.join(a.out, "index.json"), "w", encoding="utf-8") as f:
        json.dump(top, f, separators=(",", ":"), ensure_ascii=False)
    shutil.copy(os.path.join(ROOT, "CNAME"), os.path.join(a.out, "CNAME"))
    open(os.path.join(a.out, ".nojekyll"), "w").close()
    print(f"Wrote {a.out}/index.json", flush=True)


if __name__ == "__main__":
    main()
