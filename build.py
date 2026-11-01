"""Build every source into out/: per-source tiles and index.json, a top-level index.json, CNAME.

python3 build.py --cache DIR [--out out] [--download] [--force] [--only tafl|fcc|airports|repeaters|satellites]
"""

import argparse
import csv
import datetime
import hashlib
import io
import json
import os
import shutil
import sys
import urllib.request
import zipfile

import common
import landing
from airports import build as airports
from fcc import build as fcc
from repeaters import build as repeaters
from satellites import build as satellites
from tafl import build as tafl

SOURCES = {"tafl": tafl, "fcc": fcc, "airports": airports, "repeaters": repeaters,
           "satellites": satellites}
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


def published_stamp(live, name):
    """The upstream stamp the live copy of a source was built from (None: no copy, or built before stamps)."""
    try:
        with urllib.request.urlopen(f"{live}/index.json", timeout=60) as r:
            entry = next((e for e in json.load(r)["sources"] if e["source"] == name), None)
    except Exception:  # noqa: BLE001: no live index means build
        return None
    return entry and entry.get("upstream")


def published_zip(live, name):
    """The live copy of a source: (its top-level index entry, its zip's bytes, checked), or None."""
    try:
        with urllib.request.urlopen(f"{live}/index.json", timeout=60) as r:
            entry = next((e for e in json.load(r)["sources"] if e["source"] == name), None)
        if entry is None:
            return None
        with urllib.request.urlopen(f"{live}/{entry['bundle']}", timeout=300) as r:
            data = r.read()
    except Exception as e:  # noqa: BLE001: no published copy is a normal answer here
        print(f"{name}: no published copy ({e})", flush=True)
        return None
    if hashlib.sha256(data).hexdigest() != entry["bundle_sha256"]:
        print(f"{name}: the published zip doesn't match its index", flush=True)
        return None
    return entry, data


def row_keys(tiles):
    """Every row of a source as (name, latitude, longitude, frequency), from its tiles' JSON texts."""
    keys = set()
    for text in tiles:
        t = json.loads(text)
        a = o = f = 0
        for c, da, do, df in zip(t["c"], t["a"], t["o"], t["f"]):
            a, o, f = a + da, o + do, f + df
            keys.add((t["n"][c], a, o, f))
    return keys


def tile_texts_dir(out, name):
    d = os.path.join(out, name)
    for fn in os.listdir(d):
        if fn.endswith(".json") and fn != "index.json":
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                yield f.read()


def tile_texts_zip(data, name):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for fn in z.namelist():
            if fn.startswith(f"{name}/") and fn.endswith(".json") and not fn.endswith("/index.json"):
                yield z.read(fn).decode("utf-8")


def changes(out, name, live, keys=None):
    """Rows added and removed against the published copy ({} when there is none to compare with)."""
    pub = published_zip(live, name)
    if not pub:
        return {}
    keys = keys or row_keys  # a one-file source (satellites) says what counts as a row
    before, now = keys(tile_texts_zip(pub[1], name)), keys(tile_texts_dir(out, name))
    print(f"{name}: {len(now - before):,} rows added, {len(before - now):,} removed since {pub[0].get('source_date', '?')}",
          flush=True)
    return {"added": len(now - before), "removed": len(before - now)}


def keep_published(out, name, live):
    """A source that failed to build, or whose upstream hasn't changed, keeps its last published copy (its zip from
    the live site, checked and unpacked into out/). Returns its top-level index entry, or None when there is none."""
    pub = published_zip(live, name)
    if not pub:
        return None
    entry, data = pub
    with open(os.path.join(out, entry["bundle"]), "wb") as f:
        f.write(data)
    with zipfile.ZipFile(os.path.join(out, entry["bundle"])) as z:
        z.extractall(out)
    print(f"{name}: kept the published copy of {entry.get('build_date', '?')}", flush=True)
    return entry


STATS = ("build_date", "source", "rows", "added", "removed", "feed_operational", "feed_max_id", "feed_entries")


def write_stats(out, top, built, feeds, live):
    """out/stats.csv: one line per source each time it is built (a kept copy adds none), the live site's earlier
    lines carried forward (none there: a fresh start). A rebuild on the same day replaces that day's lines.
    built: the sources built this run; feeds: source -> its raw feed's counts (repeaters only) and its rows added
    and removed since the published copy. Returns every line, oldest first."""
    lines = []
    try:
        with urllib.request.urlopen(f"{live}/stats.csv", timeout=60) as r:
            lines = list(csv.DictReader(io.StringIO(r.read().decode("utf-8"))))
    except Exception as e:  # noqa: BLE001: no stats yet is a normal answer
        print(f"stats.csv: starting fresh ({e})", flush=True)
    lines = [ln for ln in lines if not (ln.get("build_date") == top["build_date"] and ln.get("source") in built)]
    for s in top["sources"]:
        if s["source"] not in built:
            continue
        feed = feeds.get(s["source"], {})
        lines.append({"build_date": top["build_date"], "source": s["source"], "rows": s["rows"],
                      "added": feed.get("added", ""), "removed": feed.get("removed", ""),
                      "feed_operational": feed.get("operational", ""), "feed_max_id": feed.get("max_id", ""),
                      "feed_entries": feed.get("entries", "")})
    with open(os.path.join(out, "stats.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, STATS, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows({k: ln.get(k, "") for k in STATS} for ln in lines)
    print(f"stats.csv: {len(lines)} lines", flush=True)
    return lines


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cache", required=True, help="download folder (keep it outside the repository)")
    p.add_argument("--out", default="out")
    p.add_argument("--download", action="store_true", help="download again even if cached")
    p.add_argument("--only", choices=sorted(SOURCES), action="append")
    p.add_argument("--force", action="store_true",
                   help="build every source, even one whose upstream files haven't changed since its published copy")
    p.add_argument("--live", default="https://data.ferritefw.dev",
                   help="where a source that fails to build keeps its last published copy from")
    a = p.parse_args()
    today = datetime.date.today().isoformat()
    os.makedirs(a.out, exist_ok=True)
    top = {"build_date": today, "url": "https://data.ferritefw.dev", "sources": []}
    failed = []
    feeds = {}
    built = set()
    live = a.live.rstrip("/")
    for name in a.only or list(SOURCES):
        shutil.rmtree(os.path.join(a.out, name), ignore_errors=True)
        # A big source with dated upstream files (TAFL, the FCC) keeps its published copy until they change.
        stamp = common.upstream_stamp(SOURCES[name].UPSTREAM) if hasattr(SOURCES[name], "UPSTREAM") else None
        if stamp and not a.force and published_stamp(live, name) == stamp:
            entry = keep_published(a.out, name, live)
            if entry:
                print(f"{name}: upstream unchanged ({stamp}); kept", flush=True)
                top["sources"].append(entry)
                continue
        try:
            rows, meta = SOURCES[name].build(a.cache, a.download)
        except Exception as e:  # noqa: BLE001: one source failing (a refused download) mustn't hold back the rest
            print(f"{name}: build failed: {e!r}", flush=True)
            failed.append(name)
            entry = keep_published(a.out, name, live)
            if entry:
                top["sources"].append(entry)
            continue
        meta["build_date"] = today
        built.add(name)
        if "feed" in meta:
            feeds[name] = meta["feed"]
        if hasattr(SOURCES[name], "write"):  # not tiles: one file
            index = SOURCES[name].write(a.out, name, rows, meta)
        else:
            index = common.write_source(a.out, name, rows, meta, getattr(SOURCES[name], "LEVEL", 4))
        feeds.setdefault(name, {}).update(changes(a.out, name, live, getattr(SOURCES[name], "row_keys", None)))
        bundle = write_bundle(a.out, name)
        top["sources"].append({k: index[k] for k in (
            "source", "title", "source_date", "licence", "licence_url", "attribution", "rows")}
            | {"index": f"{name}/index.json", "tiles": len(index["tiles"])} | bundle
            | ({"upstream": stamp} if stamp else {}))
    with open(os.path.join(a.out, "index.json"), "w", encoding="utf-8") as f:
        json.dump(top, f, separators=(",", ":"), ensure_ascii=False)
    landing.write(a.out, top, write_stats(a.out, top, built, feeds, live))
    shutil.copy(os.path.join(ROOT, "CNAME"), os.path.join(a.out, "CNAME"))
    open(os.path.join(a.out, ".nojekyll"), "w").close()
    print(f"Wrote {a.out}/index.json", flush=True)
    for name in failed:
        print(f"::warning::{name} didn't build; see the log above", flush=True)  # shown on the GitHub run
    if not top["sources"]:
        sys.exit("Nothing built and nothing kept")


if __name__ == "__main__":
    main()
