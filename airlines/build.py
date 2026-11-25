"""Airlines: Ferrite's own airline code list (IATA, ICAO, short name), for the radio's ACARS display.

Checked in as airlines/airlines.csv and written by hand: nothing is downloaded. One small file, not tiles.

Run from the repository root: python3 -m airlines.build --out out
"""

import argparse
import csv
import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "airlines.csv")
FILE = "airlines.csv"
FORMAT = "airlines-1"
COLUMNS = ["iata", "icao", "name", "country", "note"]
NOTES = ("", "cargo", "regional")
NAME_MAX = 24
LICENCE = "To be decided"
LICENCE_URL = "https://github.com/FerriteFW/data/blob/main/airlines/LICENCE-DATA.md"
ATTRIBUTION = "Airline codes compiled by Ferrite (ferritefw.dev) from general knowledge."
PAGE = "https://github.com/FerriteFW/data/tree/main/airlines"

IATA = re.compile(r"^[A-Z0-9]{2}$")
ICAO = re.compile(r"^[A-Z]{3}$")
COUNTRY = re.compile(r"^[A-Z]{2}$")


def parse(text):
    """The rows of an airlines CSV text, as dicts with the five columns. A wrong header raises ValueError."""
    r = csv.DictReader(io.StringIO(text))
    if r.fieldnames != COLUMNS:
        raise ValueError(f"header is {r.fieldnames}, wanted {COLUMNS}")
    return [{k: row[k] or "" for k in COLUMNS} for row in r]


def read(path=CSV):
    with open(path, encoding="ascii", newline="") as f:
        return parse(f.read())


def problems(rows):
    """Every way the rows break the format: bad codes, names, countries or notes, duplicates, out of order.
    Empty when they're fine."""
    out = []
    seen_iata, seen_icao = set(), set()
    last = ""
    for n, r in enumerate(rows, 2):  # line numbers, after the header
        iata, icao, name = r["iata"], r["icao"], r["name"]
        if not IATA.match(iata) or iata.isdigit():
            out.append(f"line {n}: bad IATA code {iata!r}")
        if icao and not ICAO.match(icao):
            out.append(f"line {n}: bad ICAO code {icao!r}")
        if not name or len(name) > NAME_MAX or not name.isascii() or not name.isprintable() \
                or name != name.strip() or "  " in name:
            out.append(f"line {n}: bad name {name!r} (1-{NAME_MAX} ASCII characters)")
        if not COUNTRY.match(r["country"]):
            out.append(f"line {n}: bad country {r['country']!r}")
        if r["note"] not in NOTES:
            out.append(f"line {n}: bad note {r['note']!r}")
        if iata in seen_iata:
            out.append(f"line {n}: IATA {iata} twice")
        if icao and icao in seen_icao:
            out.append(f"line {n}: ICAO {icao} twice")
        if iata < last:
            out.append(f"line {n}: {iata} is out of order (after {last})")
        seen_iata.add(iata)
        seen_icao.add(icao)
        last = max(last, iata)
    return out


def row_keys(texts):
    """Every row of the source as a tuple, from its files' texts (build.py's changes count)."""
    keys = set()
    for text in texts:
        if text.startswith("iata,"):  # the CSV, not a JSON index
            keys.update(tuple(r[k] for k in COLUMNS) for r in parse(text))
    return keys


def write(out_dir, source, rows, meta):
    """out/airlines/airlines.csv and out/airlines/index.json. Returns the index dict."""
    d = os.path.join(out_dir, source)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, FILE), "w", encoding="ascii", newline="") as f:
        w = csv.DictWriter(f, COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    index = dict(meta)
    index.update({"format": FORMAT, "file": FILE, "rows": len(rows), "tiles": {FILE: len(rows)},
                  "cargo": sum(r["note"] == "cargo" for r in rows),
                  "regional": sum(r["note"] == "regional" for r in rows)})
    with open(os.path.join(d, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"), ensure_ascii=False)
    print(f"{source}: {len(rows)} airlines, {os.path.getsize(os.path.join(d, FILE)):,} bytes", flush=True)
    return index


def build(cache=None, download=False):
    """The checked-in list, checked. cache and download are unused: nothing is downloaded."""
    rows = read()
    bad = problems(rows)
    if bad:
        raise ValueError(f"airlines.csv: {len(bad)} problems, first: {bad[0]}")
    meta = {
        "source": "airlines",
        "title": "World: airline codes (Ferrite)",
        "source_url": PAGE,
        "source_page": PAGE,
        "source_date": datetime.date.fromtimestamp(os.path.getmtime(CSV)).isoformat(),
        "licence": LICENCE,
        "licence_url": LICENCE_URL,
        "attribution": ATTRIBUTION,
    }
    return rows, meta


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", default="out")
    a = p.parse_args()
    rows, meta = build()
    meta["build_date"] = datetime.date.today().isoformat()
    write(a.out, "airlines", rows, meta)


if __name__ == "__main__":
    sys.exit(main())
