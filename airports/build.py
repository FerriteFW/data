"""Airports: OurAirports' airband frequencies (108-137 MHz), one row per airport and frequency, tiled by field.

Run from the repository root: python3 -m airports.build --cache DIR --out out [--download]
"""

import argparse
import csv
import datetime
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402

BASE = "https://davidmegginson.github.io/ourairports-data/"
PAGE = "https://ourairports.com/data/"
LICENCE = "Public domain"
LICENCE_URL = "https://ourairports.com/data/"
ATTRIBUTION = "Airport data from OurAirports (ourairports.com), public domain."
LEVEL = 2  # small enough for 2-character fields

AIRBAND = (108.0, 137.0)


def rows_of(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(io.StringIO(f.read())))


def build(cache, download=False):
    ap = common.download(BASE + "airports.csv", os.path.join(cache, "ourairports-airports.csv"), download)
    fr = common.download(BASE + "airport-frequencies.csv", os.path.join(cache, "ourairports-frequencies.csv"), download)
    sites = {}
    for r in rows_of(ap):
        if r["type"] == "closed":
            continue
        try:
            lat, lon = float(r["latitude_deg"]), float(r["longitude_deg"])
        except ValueError:
            continue
        # The ICAO code where there is one (CYVR, KLAX), else the GPS or local code, else OurAirports' ident.
        name = (r["icao_code"] or r["gps_code"] or r["local_code"] or r["ident"]).strip()[:16]
        sites[r["id"]] = (name, lat, lon)
    rows = common.Rows()
    skipped = {"airport": 0, "band": 0}
    for r in rows_of(fr):
        site = sites.get(r["airport_ref"])
        if site is None:
            skipped["airport"] += 1
            continue
        try:
            mhz = float(r["frequency_mhz"])
        except ValueError:
            skipped["band"] += 1
            continue
        if not AIRBAND[0] <= mhz <= AIRBAND[1]:
            skipped["band"] += 1
            continue
        name, lat, lon = site
        rows.add(name, lat, lon, common.khz(mhz), t=r["type"].strip().upper() or None)
    print(f"airports: skipped {skipped}", flush=True)
    meta = {
        "source": "airports",
        "title": "World: airport frequencies from OurAirports",
        "source_url": BASE,
        "source_page": PAGE,
        "source_date": datetime.date.today().isoformat(),  # updated nightly; the download date
        "licence": LICENCE,
        "licence_url": LICENCE_URL,
        "attribution": ATTRIBUTION,
    }
    return rows, meta


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cache", required=True, help="download folder (keep it outside the repository)")
    p.add_argument("--out", default="out")
    p.add_argument("--download", action="store_true", help="download again even if cached")
    a = p.parse_args()
    rows, meta = build(a.cache, a.download)
    meta["build_date"] = datetime.date.today().isoformat()
    common.write_source(a.out, "airports", rows, meta, LEVEL)


if __name__ == "__main__":
    main()
