"""Satellites: the amateur satellites a 2 m / 70 cm FM handheld can work, with orbit elements and transponders.

Orbits: CelesTrak's GP elements for the amateur group (OMM JSON). Transponders and status: SatNOGS DB.
Joined by NORAD catalogue number. One small file, satellites/sats.json (not tiles: a few dozen satellites).

Run from the repository root: python3 -m satellites.build --cache DIR --out out [--download]
"""

import argparse
import datetime
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402

GP_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=json"
TX_URL = "https://db.satnogs.org/api/transmitters/?format=json"
SAT_URL = "https://db.satnogs.org/api/satellites/?format=json"
PAGE = "https://db.satnogs.org"
LICENCE = "CC BY-SA 4.0 (SatNOGS DB transponders); CelesTrak elements are public data"
LICENCE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
ATTRIBUTION = ("Satellite orbits from CelesTrak (celestrak.org). Transponder data from SatNOGS DB (db.satnogs.org), "
               "CC BY-SA 4.0; the derived satellites file is shared under the same licence.")
FILE = "sats.json"
FORMAT = "satellites-1"
LEAST = 5  # fewer satellites than this means a broken feed, not a quiet sky

# Hz: a handheld's amateur bands for satellites, 2 m and 70 cm.
BANDS = ((144_000_000, 148_000_000), (430_000_000, 440_000_000))
FM_MODES = {"FM", "FMN"}
ALIAS = re.compile(r"^[A-Z]{1,6}-?\d+[A-Z]?$")


def in_band(hz):
    return hz is not None and any(lo <= hz <= hi for lo, hi in BANDS)


def tone_of(description):
    """The CTCSS tone (Hz, as common.tone writes it) a description names ('... CTCSS 67.0 Hz'), else None.
    'no CTCSS' and a description without a tone are None."""
    d = description or ""
    if re.search(r"\bno\s+ctcss\b", d, re.I):
        return None
    m = re.search(r"(?:ctcss|pl|tone)\D{0,6}(\d{2,3}(?:\.\d)?)\s*(?:hz)?", d, re.I) \
        or re.search(r"(\d{2,3}\.\d)\s*hz\b", d, re.I)
    return common.tone(m.group(1)) if m else None


def kind(t):
    """'fm' (voice repeater or transponder), 'aprs' (1200 baud AFSK digipeater) or None, from a SatNOGS
    transmitter. Needs an uplink: a downlink-only FM or AFSK signal is a beacon, not something to work."""
    if not t.get("alive") or t.get("status") != "active" or not t.get("uplink_low"):
        return None
    mode = (t.get("mode") or "").upper()
    desc = t.get("description") or ""
    if mode in FM_MODES:
        return "fm"
    if mode == "AFSK" and t.get("type") in ("Transceiver", "Transponder") and not re.search(
            r"9k6|9600|4k8|2k4|tlm|telemetry|beacon", desc, re.I):
        return "aprs"
    return None


def usable(t):
    """Why a transmitter is left out, or None to keep it (kind, and every frequency in band)."""
    if kind(t) is None:
        return "not FM or APRS with an uplink"
    freqs = [t.get(k) for k in ("uplink_low", "uplink_high", "downlink_low", "downlink_high")]
    if not t.get("downlink_low") or not all(in_band(f) for f in freqs if f):
        return "out of band"
    return None


def transmitter(t):
    ul = t.get("uplink_low")
    dl = t.get("downlink_low")
    return {
        "desc": " ".join((t.get("description") or "").split()),
        "mode": "APRS" if kind(t) == "aprs" else "FM",
        "up": [ul, t.get("uplink_high") or ul],
        "down": [dl, t.get("downlink_high") or dl],
        "tone": tone_of(t.get("description")),
        "invert": bool(t.get("invert")),
    }


def short_name(name):
    """Up to 16 characters: the parenthesised alias when it is one (OSCAR 7 (AO-7) is AO-7), else the name
    without parentheses (ISS (ZARYA) is ISS)."""
    m = re.search(r"\(([^)]*)\)", name)
    if m and ALIAS.match(m.group(1).strip()):
        return m.group(1).strip()[:16]
    return " ".join(re.sub(r"\([^)]*\)", "", name).split())[:16]


def _checksum(line):
    return sum(int(c) if c.isdigit() else 1 if c == "-" else 0 for c in line) % 10


def _exp(v):
    """A TLE's implied-decimal field: -3.0483587e-05 is '-30484-4' (8 characters)."""
    if v == 0:
        return " 00000+0"
    e = math.floor(math.log10(abs(v))) + 1
    mant = round(abs(v) / 10 ** e * 1e5)
    if mant >= 100000:
        mant, e = mant // 10, e + 1
    return f"{'-' if v < 0 else ' '}{mant:05d}{'-' if e < 0 else '+'}{abs(e)}"


def tle_of(g):
    """The two TLE lines for an OMM record (CelesTrak's GP JSON), 69 characters each, checksums included."""
    ep = datetime.datetime.fromisoformat(g["EPOCH"])
    doy = ep.timetuple().tm_yday + (ep.hour * 3600 + ep.minute * 60 + ep.second + ep.microsecond / 1e6) / 86400
    ndot = f"{g['MEAN_MOTION_DOT']:.8f}"
    ndot = ("-" if g["MEAN_MOTION_DOT"] < 0 else " ") + ndot.lstrip("-").lstrip("0")
    year, rest = g["OBJECT_ID"].split("-")
    desig = f"{year[2:]}{rest}"
    n = g["NORAD_CAT_ID"]
    l1 = (f"1 {n:05d}{g.get('CLASSIFICATION_TYPE', 'U')} {desig:<8} {ep.year % 100:02d}{doy:012.8f} {ndot} "
          f"{_exp(g['MEAN_MOTION_DDOT'])} {_exp(g['BSTAR'])} {g.get('EPHEMERIS_TYPE', 0)} "
          f"{g.get('ELEMENT_SET_NO', 0) % 10000:4d}")
    l2 = (f"2 {n:05d} {g['INCLINATION']:8.4f} {g['RA_OF_ASC_NODE']:8.4f} {int(g['ECCENTRICITY'] * 1e7 + 1e-6):07d} "
          f"{g['ARG_OF_PERICENTER']:8.4f} {g['MEAN_ANOMALY']:8.4f} {g['MEAN_MOTION']:11.8f}"
          f"{g.get('REV_AT_EPOCH', 0) % 100000:5d}")
    return [l1 + str(_checksum(l1)), l2 + str(_checksum(l2))]


def status_of(g, newest):
    """'active' (SatNOGS: in orbit, with an alive transmitter we keep), 'unknown' when its elements are over 30
    days older than the newest in the feed (probably silent or lost track of), 'inactive' is reserved: dead
    satellites are left out of the file."""
    age = datetime.datetime.fromisoformat(newest) - datetime.datetime.fromisoformat(g["EPOCH"])
    return "unknown" if age > datetime.timedelta(days=30) else "active"


def order(x):
    """Most useful first: FM voice (a repeater with a tone, then the rest), then APRS."""
    return (x["mode"] != "FM", x["tone"] is None, x["down"], x["up"])


def elements(g):
    return {
        "epoch": g["EPOCH"], "n": g["MEAN_MOTION"], "e": g["ECCENTRICITY"], "i": g["INCLINATION"],
        "raan": g["RA_OF_ASC_NODE"], "w": g["ARG_OF_PERICENTER"], "m": g["MEAN_ANOMALY"],
        "bstar": g["BSTAR"], "ndot": g["MEAN_MOTION_DOT"], "nddot": g["MEAN_MOTION_DDOT"],
        "rev": g["REV_AT_EPOCH"],
    }


def join(gp, transmitters, satellites, report=None):
    """The satellites file's list: alive satellites (SatNOGS 'in orbit') with CelesTrak elements and at least one
    usable transmitter, by NORAD number. report (a dict) counts what is dropped and why."""
    report = {} if report is None else report

    def drop(why):
        report[why] = report.get(why, 0) + 1

    elset = {g["NORAD_CAT_ID"]: g for g in gp}
    status = {s["norad_cat_id"]: s for s in satellites}
    kept = {}
    for t in transmitters:
        n = t.get("norad_cat_id")
        why = usable(t)
        if why:
            drop(why)
        elif n not in elset:
            drop("no elements")
        elif status.get(n, {}).get("status") != "in orbit":
            drop("not in orbit")
        else:
            tx = transmitter(t)
            lst = kept.setdefault(n, [])
            if any((x["mode"], x["up"], x["down"]) == (tx["mode"], tx["up"], tx["down"]) for x in lst):
                drop("duplicate")
            else:
                lst.append(tx)
    out = []
    newest = max((g["EPOCH"] for g in gp), default="1970-01-01T00:00:00")
    for n in sorted(kept):
        g = elset[n]
        out.append({
            "id": n, "name": g["OBJECT_NAME"], "short": short_name(g["OBJECT_NAME"]),
            "status": status_of(g, newest), "tle": tle_of(g), "elements": elements(g),
            "transmitters": sorted(kept[n], key=order),
        })
    return out


def row_keys(texts):
    """What a build adds or removes, for the Changes chart: satellites and their transmitters (not element
    drift, which changes every day)."""
    keys = set()
    for text in texts:
        for s in json.loads(text)["satellites"]:
            keys.add((s["id"],))
            keys.update((s["id"], x["mode"], tuple(x["up"]), tuple(x["down"])) for x in s["transmitters"])
    return keys


def write(out_dir, source, sats, meta):
    """out/satellites/sats.json and out/satellites/index.json. Returns the index dict."""
    d = os.path.join(out_dir, source)
    os.makedirs(d, exist_ok=True)
    epochs = sorted(s["elements"]["epoch"] for s in sats)
    doc = {"format": FORMAT, "built": meta["build_date"], "licence": meta["licence"],
           "attribution": meta["attribution"], "newest_epoch": epochs[-1], "oldest_epoch": epochs[0],
           "satellites": sats}
    with open(os.path.join(d, FILE), "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"), ensure_ascii=False)
    index = dict(meta)
    index.update({"format": FORMAT, "file": FILE, "rows": len(sats), "tiles": {FILE: len(sats)},
                  "newest_epoch": epochs[-1], "oldest_epoch": epochs[0]})
    with open(os.path.join(d, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"), ensure_ascii=False)
    print(f"{source}: {len(sats)} satellites, {os.path.getsize(os.path.join(d, FILE)):,} bytes", flush=True)
    return index


def build(cache, download=False):
    paths = [common.download(u, os.path.join(cache, n), download) for u, n in (
        (GP_URL, "celestrak-amateur.json"), (TX_URL, "satnogs-transmitters.json"),
        (SAT_URL, "satnogs-satellites.json"))]
    data = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            data.append(json.load(f))  # an error page instead of JSON raises here: the last copy is kept
    gp, transmitters, satellites = data
    dropped = {}
    sats = join(gp, transmitters, satellites, dropped)
    print(f"satellites: {len(gp)} element sets, {len(transmitters)} transmitters, kept {len(sats)}, "
          f"dropped transmitters {dict(sorted(dropped.items()))}", flush=True)
    if len(sats) < LEAST:
        raise ValueError(f"only {len(sats)} satellites: the feeds look wrong")
    meta = {
        "source": "satellites",
        "title": "World: amateur satellites (CelesTrak and SatNOGS)",
        "source_url": GP_URL,
        "source_page": PAGE,
        "source_date": datetime.date.fromtimestamp(os.path.getmtime(paths[0])).isoformat(),  # live feed: the download
        "licence": LICENCE,
        "licence_url": LICENCE_URL,
        "attribution": ATTRIBUTION,
    }
    return sats, meta


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cache", required=True, help="download folder (keep it outside the repository)")
    p.add_argument("--out", default="out")
    p.add_argument("--download", action="store_true", help="download again even if cached")
    a = p.parse_args()
    sats, meta = build(a.cache, a.download)
    meta["build_date"] = datetime.date.today().isoformat()
    write(a.out, "satellites", sats, meta)


if __name__ == "__main__":
    main()
