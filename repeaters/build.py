"""Repeaters: HearHam's amateur repeater list, operational analog FM ones the radio covers, tiled by field.

Run from the repository root: python3 -m repeaters.build --cache DIR --out out [--download]
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402

URL = "https://hearham.com/api/repeaters/v1"
PAGE = "https://hearham.com/repeaters"
LICENCE = "Free to use in applications, per HearHam.com; no formal data licence"
LICENCE_URL = "https://hearham.com/repeaters"
ATTRIBUTION = "Repeater data from HearHam.com (user-contributed)."
LEVEL = 2  # about 10,000 rows worldwide: 2-character fields, as airports

# The radio's amateur bands, MHz: 2 m, 1.25 m (Canada's 219-225, the wider of the two plans) and 70 cm.
BANDS = ((136.0, 174.0), (219.0, 225.0), (400.0, 470.0))


def in_band(mhz):
    return any(lo <= mhz <= hi for lo, hi in BANDS)


def analog(mode):
    """'nfm', 'fm' (width not given) or None (no analog FM) from HearHam's mode. A mixed repeater that also
    passes analog ('YSF/FM', 'P25/NFM', 'DMR/FM') counts: an analog radio can use it."""
    parts = {p.strip() for p in mode.upper().split("/")}
    if "NFM" in parts:
        return "nfm"
    return "fm" if "FM" in parts else None


def name_of(callsign):
    return " ".join(callsign.split())[:16]


def keep(r):
    """Why a HearHam entry is left out, or None to keep it."""
    if r.get("operational") != 1:
        return "not operational"
    if analog(r.get("mode") or "") is None:
        return "not analog FM"
    try:
        lat, lon, hz, off = float(r["latitude"]), float(r["longitude"]), int(r["frequency"]), int(r["offset"] or 0)
    except (KeyError, TypeError, ValueError):
        return "bad record"
    if not in_band(hz / 1e6):
        return "out of band"
    if not in_band((hz + off) / 1e6):
        return "input out of band"
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return "no position"
    if not name_of(r.get("callsign") or ""):
        return "no callsign"
    return None


def rows_of(entries, report=None):
    """Rows from HearHam's list; report (a dict) counts what's dropped and why."""
    rows = common.Rows()
    report = {} if report is None else report
    for r in entries:
        why = keep(r)
        if why is None:
            m = analog(r["mode"])
            hz, off = int(r["frequency"]), int(r["offset"] or 0)
            rpt = (common.khz(off / 1e6), common.tone(r.get("encode") or ""), common.tone(r.get("decode") or ""))
            # 'fm' says nothing about width (HearHam's FM is 12.5 kHz in Europe, 20 in America): left unknown.
            if rows.add(name_of(r["callsign"]), float(r["latitude"]), float(r["longitude"]), common.khz(hz / 1e6),
                        m="nfm" if m == "nfm" else None, rpt=rpt):
                continue
            why = "duplicate"
        report[why] = report.get(why, 0) + 1
    return rows


def build(cache, download=False):
    path = common.download(URL, os.path.join(cache, "hearham-repeaters.json"), download)
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    dropped = {}
    rows = rows_of(entries, dropped)
    print(f"repeaters: {len(entries)} entries, kept {len(rows)}, dropped {dict(sorted(dropped.items()))}",
          flush=True)
    meta = {
        "source": "repeaters",
        "title": "World: amateur repeaters from HearHam",
        "source_url": URL,
        "source_page": PAGE,
        "source_date": datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat(),  # live list: the download
        "licence": LICENCE,
        "licence_url": LICENCE_URL,
        "attribution": ATTRIBUTION,
        # The raw feed, for stats.csv (build.py): how the list itself grows.
        "feed": {"entries": len(entries), "operational": sum(1 for r in entries if r.get("operational") == 1),
                 "max_id": max((r.get("id") or 0 for r in entries), default=0)},
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
    common.write_source(a.out, "repeaters", rows, meta, LEVEL)


if __name__ == "__main__":
    main()
