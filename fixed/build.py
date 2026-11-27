"""Fixed sets: Ferrite's own lists of well-known channels per radio region (calling channels, licence-free
services, marine, weather and more), for Ferrite Console's library (Add from library > Fixed sets).

Checked in as fixed/src/<REGION>.json and written by hand from regulators' rules and national band plans: nothing
is downloaded. One small file per region, not tiles. The format is in fixed/README.md.

Run from the repository root: python3 -m fixed.build --out out
"""

import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
FORMAT = "fixed-1"
REGIONS = ("US", "CA", "UK", "EU", "AU", "NZ", "JP", "OTHER")  # the radio's, in its order
CATEGORIES = ("amateur", "licence-free", "marine", "weather", "aviation", "rail", "emergency", "satellite",
              "business")
POWERS = ("Low", "Mid", "High")
BANDWIDTHS = ("12.5kHz", "25kHz")
MODES = ("Analog", "AM")
NAME_MAX = 16
BANDS = ((18.0, 630.0), (756.0, 1300.0))  # what the radio tunes, MHz
FILE_KEYS = {"region", "name", "sets", "splits"}
SET_KEYS = {"id", "name", "displayName", "description", "category", "defaultPower", "defaultBandwidth",
            "defaultMode", "rxOnly", "source", "frequencies"}
SET_OPTIONAL = {"countries"}
FREQ_KEYS = {"name", "rx", "tx"}
FREQ_OPTIONAL = {"ctcss", "dcs", "rxOnly", "note"}
SPLIT_KEYS = {"country", "what", "sets", "source"}
SOURCE_KEYS = {"title", "url", "date"}
LICENCE = "CC0 1.0 (public domain dedication)"
LICENCE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
ATTRIBUTION = "Fixed channel sets compiled by Ferrite (ferritefw.dev) from regulators' rules and national band plans, each set naming its sources. CC0 1.0."
PAGE = "https://github.com/FerriteFW/data/tree/main/fixed"
CORRECTIONS = "https://github.com/FerriteFW/data/issues/new?template=fixed-set.yml"  # the issue form (.github/ISSUE_TEMPLATE/fixed-set.yml)

ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
COUNTRY = re.compile(r"^[A-Z]{2}(-[A-Z0-9]{1,3})?$")  # ISO 3166-1 alpha-2, or 3166-2 (US-AK, CA-BC)
URL = re.compile(r"^https?://\S+$")


def read(region, src=SRC):
    with open(os.path.join(src, f"{region}.json"), encoding="ascii") as f:
        return json.load(f)


def read_all(src=SRC):
    """Every region file, in the radio's order. A missing region raises FileNotFoundError."""
    return [read(r, src) for r in REGIONS]


def short_name(s):
    return isinstance(s, str) and 0 < len(s) <= NAME_MAX and s.isascii() and s.isprintable() and s == s.strip()


def text(s):
    return isinstance(s, str) and s.strip() != "" and s.isascii() and s.isprintable()


def tunable(f):
    return isinstance(f, (int, float)) and not isinstance(f, bool) and any(lo <= f <= hi for lo, hi in BANDS)


def source_problems(where, sources):
    if not isinstance(sources, list) or not sources:
        return [f"{where}: no source"]
    out = []
    for s in sources:
        if not isinstance(s, dict) or set(s) != SOURCE_KEYS:
            out.append(f"{where}: a source needs exactly {sorted(SOURCE_KEYS)}")
        elif not (text(s["title"]) and URL.match(s["url"]) and text(s["date"])):
            out.append(f"{where}: bad source {s.get('title')!r}")
    return out


def freq_problems(where, f):
    if not isinstance(f, dict) or not FREQ_KEYS <= set(f) or set(f) - FREQ_KEYS - FREQ_OPTIONAL:
        return [f"{where}: a frequency needs {sorted(FREQ_KEYS)}, may have {sorted(FREQ_OPTIONAL)}"]
    out = []
    if not short_name(f["name"]):
        out.append(f"{where}: bad name {f['name']!r} (1-{NAME_MAX} ASCII characters)")
    for k in ("rx", "tx"):
        if not tunable(f[k]):
            out.append(f"{where} {f['name']!r}: {k} {f[k]!r} is outside what the radio tunes")
    if "ctcss" in f and "dcs" in f:
        out.append(f"{where} {f['name']!r}: both CTCSS and DCS")
    if "ctcss" in f and not (isinstance(f["ctcss"], (int, float)) and 60 <= f["ctcss"] <= 260):
        out.append(f"{where} {f['name']!r}: bad CTCSS {f['ctcss']!r}")
    if "dcs" in f and not (isinstance(f["dcs"], int) and all(c in "01234567" for c in str(f["dcs"]))
                           and 0 < f["dcs"] <= 777):
        out.append(f"{where} {f['name']!r}: bad DCS {f['dcs']!r} (octal digits as an integer)")
    if "rxOnly" in f and not isinstance(f["rxOnly"], bool):
        out.append(f"{where} {f['name']!r}: rxOnly is not true or false")
    if "note" in f and not text(f["note"]):
        out.append(f"{where} {f['name']!r}: bad note")
    return out


def set_problems(region, s):
    where = f"{region} {s.get('id', '?') if isinstance(s, dict) else '?'}"
    if not isinstance(s, dict) or not SET_KEYS <= set(s) or set(s) - SET_KEYS - SET_OPTIONAL:
        return [f"{where}: a set needs {sorted(SET_KEYS)}, may have {sorted(SET_OPTIONAL)}"]
    out = []
    if not (isinstance(s["id"], str) and ID.match(s["id"]) and s["id"].startswith(region.lower() + "-")):
        out.append(f"{where}: bad id (lower case, starting {region.lower()}-)")
    if not short_name(s["name"]):
        out.append(f"{where}: bad name {s['name']!r} (1-{NAME_MAX} ASCII characters)")
    for k in ("displayName", "description"):
        if not text(s[k]):
            out.append(f"{where}: bad {k}")
    if s["category"] not in CATEGORIES:
        out.append(f"{where}: bad category {s['category']!r}")
    if s["defaultPower"] not in POWERS:
        out.append(f"{where}: bad defaultPower {s['defaultPower']!r}")
    if s["category"] == "licence-free" and s["defaultPower"] != "Low":
        out.append(f"{where}: a licence-free set defaults to Low power")
    if s["defaultBandwidth"] not in BANDWIDTHS:
        out.append(f"{where}: bad defaultBandwidth {s['defaultBandwidth']!r}")
    if s["defaultMode"] not in MODES:
        out.append(f"{where}: bad defaultMode {s['defaultMode']!r}")
    if not isinstance(s["rxOnly"], bool):
        out.append(f"{where}: rxOnly is not true or false")
    if "countries" in s and not (isinstance(s["countries"], list) and s["countries"]
                                 and all(isinstance(c, str) and COUNTRY.match(c) for c in s["countries"])):
        out.append(f"{where}: bad countries {s['countries']!r}")
    out += source_problems(where, s["source"])
    if not isinstance(s["frequencies"], list) or not s["frequencies"]:
        out.append(f"{where}: no frequencies")
    else:
        for f in s["frequencies"]:
            out += freq_problems(where, f)
    return out


def problems(files):
    """Every way the region files break the format (fixed/README.md): missing or unknown keys, bad names, ids,
    countries or frequencies, a set without a source, an id twice, a split naming a set that isn't there.
    Empty when they're fine."""
    out = []
    ids = set()
    for d in files:
        region = d.get("region") if isinstance(d, dict) else None
        if region not in REGIONS or set(d) != FILE_KEYS:
            out.append(f"{region}: a region file has exactly {sorted(FILE_KEYS)} and a radio region")
            continue
        if not text(d["name"]):
            out.append(f"{region}: bad name")
        here = set()
        for s in d["sets"]:
            out += set_problems(region, s)
            sid = s.get("id") if isinstance(s, dict) else None
            if sid in ids:
                out.append(f"{region} {sid}: id twice")
            ids.add(sid)
            here.add(sid)
        for sp in d["splits"]:
            if not isinstance(sp, dict) or set(sp) != SPLIT_KEYS:
                out.append(f"{region}: a split has exactly {sorted(SPLIT_KEYS)}")
                continue
            where = f"{region} split {sp['country']}"
            if not (isinstance(sp["country"], str) and COUNTRY.match(sp["country"])):
                out.append(f"{where}: bad country")
            if not text(sp["what"]):
                out.append(f"{where}: bad what")
            for sid in sp["sets"]:
                if sid not in here:
                    out.append(f"{where}: names {sid!r}, not a set of {region}")
            out += source_problems(where, sp["source"])
    seen = [d.get("region") for d in files if isinstance(d, dict)]
    if sorted(seen, key=str) != sorted(REGIONS):
        out.append(f"regions are {seen}, wanted each of {list(REGIONS)} once")
    return out


def canonical(d):
    """A region file's checked-in text: two-space indents, one line per frequency, source or split."""
    one = lambda x: json.dumps(x, ensure_ascii=True)
    lines = ["{", f'  "region": {one(d["region"])},', f'  "name": {one(d["name"])},', '  "sets": [']
    for i, s in enumerate(d["sets"]):
        lines.append("    {")
        keys = [k for k in s if k != "frequencies"]
        for k in keys:
            if k == "source":
                lines.append('      "source": [')
                lines += [f"        {one(x)}," for x in s[k]]
                lines[-1] = lines[-1].rstrip(",")
                lines.append("      ],")
            else:
                lines.append(f'      {one(k)}: {one(s[k])},')
        lines.append('      "frequencies": [')
        lines += [f"        {one(f)}," for f in s["frequencies"]]
        lines[-1] = lines[-1].rstrip(",")
        lines.append("      ]")
        lines.append("    }" + ("," if i < len(d["sets"]) - 1 else ""))
    lines.append("  ],")
    lines.append('  "splits": [')
    lines += [f"    {one(x)}," for x in d["splits"]]
    if d["splits"]:
        lines[-1] = lines[-1].rstrip(",")
    lines.append("  ]")
    lines.append("}")
    return "\n".join(lines) + "\n"


def counts(d):
    return {"sets": len(d["sets"]), "frequencies": sum(len(s["frequencies"]) for s in d["sets"]),
            "splits": len(d["splits"])}


def row_keys(texts):
    """Every channel of the source as a tuple, from its files' texts (build.py's changes count)."""
    keys = set()
    for t in texts:
        d = json.loads(t)
        for s in d.get("sets", ()):
            keys.update((s["id"], f["name"], f["rx"], f["tx"]) for f in s["frequencies"])
    return keys


def write(out_dir, source, files, meta):
    """out/fixed/<REGION>.json per region and out/fixed/index.json. Returns the index dict."""
    d = os.path.join(out_dir, source)
    os.makedirs(d, exist_ok=True)
    regions = {}
    for f in files:
        name = f"{f['region']}.json"
        doc = {"format": FORMAT, "built": meta["build_date"], "licence": meta["licence"],
               "attribution": meta["attribution"]}
        doc.update(f)
        with open(os.path.join(d, name), "w", encoding="utf-8") as out:
            json.dump(doc, out, separators=(",", ":"), ensure_ascii=False)
        regions[f["region"]] = dict(counts(f), file=name, name=f["name"])
    index = dict(meta)
    index.update({"format": FORMAT, "rows": sum(r["sets"] for r in regions.values()),
                  "frequencies": sum(r["frequencies"] for r in regions.values()),
                  "tiles": {r["file"]: r["sets"] for r in regions.values()}, "regions": regions})
    with open(os.path.join(d, "index.json"), "w", encoding="utf-8") as out:
        json.dump(index, out, separators=(",", ":"), ensure_ascii=False)
    print(f"{source}: {index['rows']} sets, {index['frequencies']} frequencies in {len(regions)} regions", flush=True)
    return index


def build(cache=None, download=False):
    """The checked-in region files, checked. cache and download are unused: nothing is downloaded."""
    files = read_all()
    bad = problems(files)
    if bad:
        raise ValueError(f"fixed/src: {len(bad)} problems, first: {bad[0]}")
    newest = max(os.path.getmtime(os.path.join(SRC, f"{r}.json")) for r in REGIONS)
    meta = {
        "source": "fixed",
        "title": "World: fixed channel sets by region (Ferrite)",
        "source_url": PAGE,
        "source_page": PAGE,
        "source_date": datetime.date.fromtimestamp(newest).isoformat(),
        "licence": LICENCE,
        "licence_url": LICENCE_URL,
        "attribution": ATTRIBUTION,
        "corrections": CORRECTIONS,
    }
    return files, meta


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="out")
    p.add_argument("--format", action="store_true", help="rewrite fixed/src in the checked-in layout, then stop")
    a = p.parse_args()
    if a.format:
        for d in read_all():
            with open(os.path.join(SRC, f"{d['region']}.json"), "w", encoding="ascii") as f:
                f.write(canonical(d))
        return
    files, meta = build()
    meta["build_date"] = datetime.date.today().isoformat()
    write(a.out, "fixed", files, meta)


if __name__ == "__main__":
    sys.exit(main())
