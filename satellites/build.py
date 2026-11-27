"""Satellites: the amateur satellites a 2 m / 70 cm FM handheld can work or listen to, with orbit elements and
transponders.

Orbits: CelesTrak's GP elements for the amateur group (OMM JSON); for a curated satellite CelesTrak's group lacks,
SatNOGS DB's latest TLE (from Space-Track) when it is fresh. Transponders and status: SatNOGS DB, plus a curated
table from AMSAT's frequency pages (CURATED: receive-only SSTV and FM downlinks, satellites SatNOGS lists without a
workable transmitter) and a skip list (SKIP: satellites AMSAT doesn't list as working). Joined by NORAD catalogue
number. One small file, satellites/sats.json (not tiles: a few dozen satellites).

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
TLE_URL = "https://db.satnogs.org/api/tle/?format=json"
PAGE = "https://db.satnogs.org"
LICENCE = "CC BY-SA 4.0 (SatNOGS DB transponders); CelesTrak elements are public data"
LICENCE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
ATTRIBUTION = ("Satellite orbits from CelesTrak (celestrak.org). Transponder data from SatNOGS DB (db.satnogs.org), "
               "CC BY-SA 4.0; the derived satellites file is shared under the same licence.")
FILE = "sats.json"
FORMAT = "satellites-1"
LEAST = 5  # fewer satellites than this means a broken feed, not a quiet sky
RADIO_MAX = 32  # the radio's satellite places (ferrite-core link::SATS_MAX); Console writes the file's first 32
FRESH = datetime.timedelta(days=14)  # a SatNOGS TLE older than this (against the newest CelesTrak epoch) is left out

# Hz: a handheld's amateur bands for satellites, 2 m and 70 cm.
BANDS = ((144_000_000, 148_000_000), (430_000_000, 440_000_000))
FM_MODES = {"FM", "FMN"}
ALIAS = re.compile(r"^[A-Z]{1,6}-?\d+[A-Z]?$")

# Curated tones SatNOGS doesn't carry, keyed by (NORAD number, uplink low in Hz): the FM transponder's access
# tone (`tone`) and arming tone (`arm_tone`, sent ~2 s on the first key-up of a pass, before the access tone).
# Only tones with a solid published source; checked Nov 2026, SO-50 is the only listed FM satellite with one.
OVERRIDES = {
    # SO-50: 74.4 Hz for about 2 s arms a 10-minute timer, then 67.0 Hz for the contact.
    # AMSAT, https://www.amsat.org/two-way-satellites/so-50-satellite-information/
    (27607, 145_850_000): {"tone": "67.0", "arm_tone": "74.4"},
}


AMSAT_FM = "https://www.amsat.org/live-fm-satellites/"
AMSAT_DIGI = "https://www.amsat.org/live-digipeater-satellites/"
AMSAT_IMAGE = "https://www.amsat.org/image-transmitting-satellites/"
AMSAT_UPCOMING = "https://www.amsat.org/upcoming-satellites/"


def _fm(up, down, desc, tone=None):
    return {"desc": desc, "mode": "FM", "up": [up, up], "down": [down, down], "tone": tone, "invert": False}


def _listen(down, desc):
    """Receive only: no uplink (Console makes it a beacon the radio never transmits on, SAT-13)."""
    return {"desc": desc, "mode": "FM", "up": None, "down": [down, down], "tone": None, "invert": False}


def _aprs(f, desc="APRS digipeater 1200 baud"):
    return {"desc": desc, "mode": "APRS", "up": [f, f], "down": [f, f], "tone": None, "invert": False}


# Curated from AMSAT's frequency pages (facts only: frequencies, tones, modes), read Nov 26, 2026. By NORAD number:
# the radio's short name, the page it comes from, and transmitters added to what SatNOGS gives (one with the same
# mode and downlink as a SatNOGS one is skipped). A satellite here is kept when SatNOGS says it is in orbit and it
# has elements (CelesTrak's, else a fresh SatNOGS TLE). Discord asked for SO-131 (Nov 19, 2026).
CURATED = {
    101101: {"short": "SO-131", "src": AMSAT_FM, "tx": [  # UNNE-1B (HADES-E2)
        _fm(145_925_000, 436_888_000, "Mode V/U FM repeater; 1k2 AFSK relayed on Wednesdays")]},
    101102: {"short": "SO-132", "src": AMSAT_FM, "tx": [  # HADES-L: its uplink is on 10 m, so listen only
        _listen(436_665_000, "Mode U FM downlink (uplink 29.472 MHz, outside the radio's satellite bands)")]},
    67291: {"short": "RS95S", "src": AMSAT_FM, "tx": [  # QMR-KWT-2
        _fm(145_920_000, 436_950_000, "Mode V/U FM, CTCSS 67.0 Hz, when on; also SSTV Robot36", "67.0")]},
    40931: {"short": "IO-86", "src": AMSAT_FM, "tx": [  # LAPAN-A2: low inclination, near the equator only
        _fm(145_880_000, 435_880_000, "Mode V/U FM, CTCSS 88.5 Hz, by schedule; also SSTV PD50", "88.5"),
        _aprs(145_825_000)]},
    40908: {"short": "CAS-3H", "src": AMSAT_FM, "tx": [  # LilacSat-2
        _fm(144_350_000, 437_200_000, "Mode V/U FM, no set schedule (else a telemetry beacon)")]},
    68456: {"short": "PARUS-6U1", "src": AMSAT_UPCOMING, "tx": [_aprs(145_825_000, "APRS 1200 baud (in testing)")]},
    # SSTV (Robot36 unless said): listen only; the radio's SSTV decoder reads them.
    67279: {"short": "HC1PX", "src": AMSAT_IMAGE, "tx": [_listen(437_050_000, "SSTV Robot36, occasional")]},
    100470: {"short": "JAMX01", "src": AMSAT_IMAGE, "tx": [_listen(435_175_000, "SSTV Robot36, occasional")]},
    67290: {"short": "RS18S", "src": AMSAT_IMAGE, "tx": [_listen(437_350_000, "SSTV Robot36, occasional")]},
    57203: {"short": "RS27S", "src": AMSAT_IMAGE, "tx": [_listen(436_125_000, "SSTV Robot36, occasional")]},
    57189: {"short": "RS38S", "src": AMSAT_IMAGE, "tx": [_listen(437_825_000, "SSTV Robot36, occasional")]},
    57172: {"short": "RS40S", "src": AMSAT_IMAGE, "tx": [_listen(437_625_000, "SSTV Robot36 or music, occasional")]},
    57182: {"short": "RS57S", "src": AMSAT_IMAGE, "tx": [_listen(436_080_000, "SSTV Robot36, occasional")]},
    57180: {"short": "RS58S", "src": AMSAT_IMAGE, "tx": [_listen(435_290_000, "SSTV Robot36, occasional")]},
    67284: {"short": "RS83S", "src": AMSAT_IMAGE, "tx": [_listen(436_320_000, "SSTV, occasional")]},
    59112: {"short": "SONATE-2", "src": AMSAT_IMAGE, "tx": [_listen(145_880_000, "SSTV Martin M1, by schedule")]},
}

# Left out though SatNOGS calls them alive: not on AMSAT's live FM or digipeater lists (Nov 2026), or their owner
# says the transponders aren't reliable. Discord asked for TEVEL2 to go (Nov 19, 2026): nine places for one
# unreliable transponder.
SKIP = {
    **{n: "TEVEL2: owner reports random restarts that shut the transponders off (AMSAT live FM page)"
       for n in (63213, 63214, 63215, 63217, 63218, 63219, 63237, 63238, 63239)},
    22825: "AO-27: not on AMSAT's live FM list",
    36122: "XW-? (HOPE-1): not on AMSAT's live FM list",
}

# The names hams use (AMSAT's), where CelesTrak's name has no OSCAR alias to take.
SHORT = {43017: "AO-91", 43678: "PO-101"}

# Overrides of SatNOGS tones and arming tones, by (NORAD number, uplink low in Hz).
TONES = {
    # PO-101 (Diwata-2): 141.3 Hz, AMSAT live FM page.
    (43678, 437_500_000): {"tone": "141.3"},
}


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
    """A transmitter for the file; OVERRIDES adds an arming tone (and fixes the access tone) where curated."""
    ul = t.get("uplink_low")
    dl = t.get("downlink_low")
    out = {
        "desc": " ".join((t.get("description") or "").split()),
        "mode": "APRS" if kind(t) == "aprs" else "FM",
        "up": [ul, t.get("uplink_high") or ul],
        "down": [dl, t.get("downlink_high") or dl],
        "tone": tone_of(t.get("description")),
        "invert": bool(t.get("invert")),
    }
    if out["mode"] == "FM":
        out.update(OVERRIDES.get((t.get("norad_cat_id"), ul), {}))
        out.update(TONES.get((t.get("norad_cat_id"), ul), {}))
    return out


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
    """The two TLE lines for an OMM record (CelesTrak's GP JSON), 69 characters each, checksums included; an
    element set read from a TLE keeps its own lines (Alpha-5 numbers above 99999 included)."""
    if "_tle" in g:
        return list(g["_tle"])
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


def _alpha5(field):
    """A TLE's catalogue number: digits, or Alpha-5 (A0001 is 100001; I and O aren't used)."""
    field = field.strip()
    if field[:1].isalpha():
        return ("ABCDEFGHJKLMNPQRSTUVWXYZ".index(field[0]) + 10) * 10000 + int(field[1:])
    return int(field)


def _implied(field):
    """A TLE's implied-decimal field (' 34172-3' is 0.34172e-3)."""
    f = field.strip()
    if not f or f in ("00000-0", "00000+0", "-00000-0"):
        return 0.0
    sign = -1.0 if f[0] == "-" else 1.0
    f = f.lstrip("+-")
    mant, exp = f[:-2], f[-2:]
    return sign * float("0." + mant) * 10 ** int(exp)


def omm_of_tle(l1, l2, name):
    """An OMM-like record (the keys elements() and tle_of() read) from a TLE's two lines; None when they don't
    read (a wrong checksum or length)."""
    try:
        if len(l1) != 69 or len(l2) != 69 or int(l1[68]) != _checksum(l1[:68]) or int(l2[68]) != _checksum(l2[:68]):
            return None
        yy, doy = int(l1[18:20]), float(l1[20:32])
        year = 2000 + yy if yy < 57 else 1900 + yy
        epoch = datetime.datetime(year, 1, 1) + datetime.timedelta(days=doy - 1)
        return {
            "OBJECT_NAME": name, "NORAD_CAT_ID": _alpha5(l1[2:7]),
            "EPOCH": epoch.isoformat(timespec="microseconds"),
            "MEAN_MOTION_DOT": float(l1[33:43].replace(" ", "") or 0),
            "MEAN_MOTION_DDOT": _implied(l1[44:52]), "BSTAR": _implied(l1[53:61]),
            "INCLINATION": float(l2[8:16]), "RA_OF_ASC_NODE": float(l2[17:25]),
            "ECCENTRICITY": float("0." + l2[26:33].strip()), "ARG_OF_PERICENTER": float(l2[34:42]),
            "MEAN_ANOMALY": float(l2[43:51]), "MEAN_MOTION": float(l2[52:63]),
            "REV_AT_EPOCH": int(l2[63:68].strip() or 0),
            "_tle": [l1, l2],
        }
    except (ValueError, IndexError):
        return None


def status_of(g, newest):
    """'active' (SatNOGS: in orbit, with an alive transmitter we keep), 'unknown' when its elements are over 30
    days older than the newest in the feed (probably silent or lost track of), 'inactive' is reserved: dead
    satellites are left out of the file."""
    age = datetime.datetime.fromisoformat(newest) - datetime.datetime.fromisoformat(g["EPOCH"])
    return "unknown" if age > datetime.timedelta(days=30) else "active"


def order(x):
    """Most useful first: FM voice (a repeater with a tone, then the rest), FM to listen to, then APRS."""
    return (x["mode"] != "FM", x["up"] is None, x["tone"] is None, x["down"], x["up"] or [])


def elements(g):
    return {
        "epoch": g["EPOCH"], "n": g["MEAN_MOTION"], "e": g["ECCENTRICITY"], "i": g["INCLINATION"],
        "raan": g["RA_OF_ASC_NODE"], "w": g["ARG_OF_PERICENTER"], "m": g["MEAN_ANOMALY"],
        "bstar": g["BSTAR"], "ndot": g["MEAN_MOTION_DOT"], "nddot": g["MEAN_MOTION_DDOT"],
        "rev": g["REV_AT_EPOCH"],
    }


def two_way(txs):
    """A satellite can be worked: some transmitter has an uplink (APRS or an FM repeater)."""
    return any(t["up"] for t in txs)


def join(gp, transmitters, satellites, report=None, tles=()):
    """The satellites file's list: alive satellites (SatNOGS 'in orbit') with elements and at least one usable
    transmitter, by NORAD number; SKIP left out, CURATED's transmitters added. Elements: CelesTrak's, else (a
    curated satellite only) SatNOGS's TLE when within FRESH of the newest CelesTrak epoch. report (a dict) counts
    what is dropped and why."""
    report = {} if report is None else report

    def drop(why):
        report[why] = report.get(why, 0) + 1

    elset = {g["NORAD_CAT_ID"]: g for g in gp}
    status = {s["norad_cat_id"]: s for s in satellites}
    newest = max((g["EPOCH"] for g in gp), default="1970-01-01T00:00:00")
    for t in tles:
        n = t.get("norad_cat_id")
        if n in CURATED and n not in elset and n in status:
            g = omm_of_tle(t.get("tle1") or "", t.get("tle2") or "", status[n].get("name") or str(n))
            if g is None:
                drop("curated: TLE doesn't read")
            elif datetime.datetime.fromisoformat(newest) - datetime.datetime.fromisoformat(g["EPOCH"]) > FRESH:
                drop("curated: stale TLE")
            else:
                elset[n] = g
    kept = {}

    def add(n, tx):
        lst = kept.setdefault(n, [])
        if any((x["mode"], x["up"], x["down"]) == (tx["mode"], tx["up"], tx["down"]) for x in lst) or (
                tx["up"] is None and any(x["mode"] == tx["mode"] and x["down"] == tx["down"] for x in lst)):
            drop("duplicate")
        else:
            lst.append(tx)

    for t in transmitters:
        n = t.get("norad_cat_id")
        why = usable(t)
        if n in SKIP:
            drop("skipped (SKIP)")
        elif why:
            drop(why)
        elif n not in elset:
            drop("no elements")
        elif status.get(n, {}).get("status") != "in orbit":
            drop("not in orbit")
        else:
            add(n, transmitter(t))
    for n, c in CURATED.items():
        if n in SKIP or status.get(n, {}).get("status") != "in orbit" or n not in elset:
            drop("curated: not in orbit or no elements")
            continue
        for tx in c["tx"]:
            add(n, dict(tx))
    out = []
    # Two-way satellites first, then those only to listen to, each by NORAD number: Console 0.9.8 writes the
    # file's first RADIO_MAX with no picking, so listening can never push out a satellite to work.
    for n in sorted(kept, key=lambda n: (not two_way(kept[n]), n)):
        g = elset[n]
        short = CURATED[n]["short"] if n in CURATED else SHORT.get(n) or short_name(g["OBJECT_NAME"])
        out.append({
            "id": n, "name": g["OBJECT_NAME"], "short": short,
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
            keys.update((s["id"], x["mode"], tuple(x["up"] or ()), tuple(x["down"])) for x in s["transmitters"])
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
        (SAT_URL, "satnogs-satellites.json"), (TLE_URL, "satnogs-tle.json"))]
    data = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            data.append(json.load(f))  # an error page instead of JSON raises here: the last copy is kept
    gp, transmitters, satellites, tles = data
    dropped = {}
    sats = join(gp, transmitters, satellites, dropped, tles)
    print(f"satellites: {len(gp)} element sets, {len(transmitters)} transmitters, kept {len(sats)}, "
          f"dropped transmitters {dict(sorted(dropped.items()))}", flush=True)
    if len(sats) > RADIO_MAX:
        print(f"satellites: {len(sats)} is more than the radio's {RADIO_MAX} places: Console writes the first "
              f"{RADIO_MAX} (the two-way ones come first)", flush=True)
    if sum(two_way(s["transmitters"]) for s in sats) > RADIO_MAX:
        raise ValueError(f"more two-way satellites than the radio's {RADIO_MAX} places: trim CURATED or SKIP")
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
