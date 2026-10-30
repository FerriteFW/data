"""Shared pieces for the TAFL and FCC builds: bands, names, modes, tiles, downloads."""

import json
import os
import re
import subprocess

# Ferrite's bands, MHz (the same as Console's TAFL tab).
BANDS = ((136.0, 174.0), (400.0, 470.0))


def in_band(mhz):
    return any(lo <= mhz <= hi for lo, hi in BANDS)


def khz(mhz):
    """MHz to kHz, keeping 6.25 kHz channels' half kHz (469.9875 MHz is 469987.5, not 469987)."""
    k = round(mhz * 1000, 2)
    return int(k) if k == int(k) else k


def download(url, path, force=False):
    """Fetch url to path unless it is already there. Returns the path.

    Uses curl as itself: the FCC's servers refuse Python's urllib (HTTP 403) but serve curl."""
    if force or not os.path.exists(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        print(f"Downloading {url}", flush=True)
        tmp = path + ".part"
        subprocess.run(["curl", "-fsSL", "--retry", "3", "-o", tmp, url], check=True)
        os.replace(tmp, path)
    else:
        print(f"Using cached {path}", flush=True)
    return path


# -------------------------------------------------------------------------
# Emission designator -> mode
# -------------------------------------------------------------------------
_BW = re.compile(r"^(\d*)([HKMG])(\d*)")
_MULT = {"H": 1e-3, "K": 1.0, "M": 1e3, "G": 1e6}


def bandwidth_khz(designator):
    """Necessary bandwidth in kHz from an ITU emission designator ('11K0F3E' -> 11.0), or None."""
    m = _BW.match(designator.strip().upper())
    if not m or not (m.group(1) or m.group(3)):
        return None
    return float(f"{m.group(1) or '0'}.{m.group(3) or '0'}") * _MULT[m.group(2)]


def is_analog_voice(designator):
    """FM or PM analog telephony: F3E or G3E after the four bandwidth characters."""
    d = designator.strip().upper()
    return len(d) >= 7 and d[4:7] in ("F3E", "G3E")


def mode(designators):
    """'nfm' / 'fm' / 'dig' from a frequency's emission designators, or None if there are none.

    Any analog FM voice emission makes the channel analog: narrow (under 14 kHz, the 12.5 kHz
    channel's 11K0/11K2) is 'nfm', wider (16K0, 20K0) is 'fm'. Narrow wins when both are listed.
    Only digital or data emissions (7K60FXE DMR, 8K10F1E P25, 4K00F1E NXDN, ...) give 'dig'.
    """
    ds = [d for d in designators if d and d.strip()]
    if not ds:
        return None
    analog = [bandwidth_khz(d) for d in ds if is_analog_voice(d)]
    analog = [b for b in analog if b]
    if analog:
        return "nfm" if min(analog) < 14 else "fm"
    return "dig"


def merge_mode(a, b):
    """Two modes seen for the same row: analog beats digital, narrow beats wide."""
    order = {"nfm": 0, "fm": 1, "dig": 2, None: 3}
    return a if order[a] <= order[b] else b


# -------------------------------------------------------------------------
# Name shortening (from Console's tafldata.py, itself from NeonPlug)
# -------------------------------------------------------------------------
ABBREVIATIONS = {
    # Technical / station type
    "Broadcast": "BC",
    "Transmitter": "TX",
    "Station": "Stn",
    "Tower": "Tw",
    "Radio": "Rd",
    "FM": "FM",
    "AM": "AM",
    "Repeater": "Rpt",
    "Relay": "Rly",
    "Antenna": "Ant",
    "Base": "B",
    "Site": "St",
    "Mobile": "Mob",
    "Fixed": "FX",
    "VHF": "VHF",
    "UHF": "UHF",
    "Land Mobile": "",
    "Golf Course": "Golf",
    "Helicopter": "Heli",
    "Chemical": "Chem",
    # Geography / cities
    "Toronto": "Tor",
    "Vancouver": "Van",
    "Montreal": "Mtl",
    "Regina": "Rgn",
    "Calgary": "Cgy",
    "Edmonton": "Edm",
    "Ottawa": "Ott",
    "Winnipeg": "Wpg",
    "Quebec": "QC",
    "Saskatchewan": "SK",
    "British Columbia": "BC",
    "Nova Scotia": "NS",
    "Canada": "CAN",
    # US licensees (FCC)
    "County": "Cnty",
    "Township": "Twp",
    "Sheriff's Office": "SO",
    "Sheriffs Office": "SO",
    "School District": "SD",
    "University": "Univ",
    "Hospital": "Hosp",
}

SHORT_NAME_REMOVE_WORDS = {
    # Core technical / radio / infrastructure
    "base", "bases", "station", "stations", "site", "sites", "tower", "towers",
    "antenna", "antennas", "repeater", "repeaters", "radio", "radios",
    "vhf", "uhf", "fm", "am", "tx", "mobile", "mobiles",
    "portable", "portables", "portatifs", "fleet", "subscribers",
    # Government / public sector filler
    "service", "services", "department", "departments", "dept", "depts",
    "division", "divisions", "branch", "branches", "district", "districts",
    "municipal", "municipality", "public", "publics", "authority", "authorities",
    "agency", "agencies", "commission", "commissions",
    # Emergency / public safety: generic filler
    "operations", "operation", "ops",
    # Industrial / commercial filler
    "plant", "plants", "facility", "facilities",
    "construction", "construct", "contracting", "contractors",
    "transport", "transportation", "logistics",
    "energy", "power", "hydro", "gas", "utilities", "utility", "properties",
    # Geographic filler
    "north", "south", "east", "west", "central", "centre", "center", "centres", "centers",
    "zone", "region", "regional", "river", "lake", "lakes",
    "mountain", "mountains", "hill", "hills",
    "road", "rd", "street", "st", "avenue", "ave", "boulevard", "blvd",
    "hwy", "highway", "canada",
    # Common French equivalents
    "de", "du", "des", "la", "le", "les", "et",
    "travaux", "incendies", "répartition", "publics",
    "of", "co",
    # Corporate suffixes
    "inc", "inc.", "ltd", "ltd.", "llc", "corp", "corporation", "company", "co.",
    "limited", "solutions", "group",
    # Noise words
    "system", "systems", "control", "controls", "office", "offices",
    "project", "projects", "unit", "units", "team", "teams", "area", "areas",
    # US filler
    "the", "dba", "lp", "llp", "pc", "pllc",
}

CANONICAL_TERMS = {
    "fire department": "FD",
    "fire dept": "FD",
    "fire": "FD",
    "ems": "EMS",
    "ambulance": "EMS",
    "police": "PD",
    "rcmp": "RCMP",
}

_CANON = [(re.compile(rf"\b{re.escape(k)}\b", re.I), v) for k, v in CANONICAL_TERMS.items()]
_ABBR = [(re.compile(rf"\b{re.escape(k)}\b", re.I), v) for k, v in ABBREVIATIONS.items()]


def smart_name(name, max_len=16):
    """Compact licensee name: canonical terms, abbreviations, noise words out, 16 characters."""
    name = name.lower()
    for pat, short in _CANON:
        name = pat.sub(short, name)
    for pat, short in _ABBR:
        name = pat.sub(short, name)
    name = re.sub(r"[.,&/()]", "", name)
    words = [w for w in name.split() if w not in SHORT_NAME_REMOVE_WORDS]
    name = " ".join(words)
    name = re.sub(r"[^A-Za-z0-9_ ]", "", name)
    return name[:max_len].strip()


def is_generic_number_name(name, num_digits=4):
    """Numbered companies ('9257-0134 Québec inc.') say nothing useful: skip them."""
    return bool(re.match(rf"^\d{{{num_digits},}}", name))


# -------------------------------------------------------------------------
# Tiles
# -------------------------------------------------------------------------
def grid2(lat, lon):
    """2-character Maidenhead field ('CN' for southern B.C. and Washington): 20 x 10 degrees."""
    return grid4(lat, lon)[:2]


def grid4(lat, lon):
    """4-character Maidenhead square ('CN89' for Vancouver)."""
    lon = min(max(lon + 180.0, 0.0), 359.999999)
    lat = min(max(lat + 90.0, 0.0), 179.999999)
    return (chr(65 + int(lon // 20)) + chr(65 + int(lat // 10))
            + str(int(lon % 20 // 2)) + str(int(lat % 10)))


def grid6(lat, lon):
    """6-character Maidenhead subsquare ('CN89kg'): the square split 24 x 24, about 6 x 4.6 km here."""
    g = grid4(lat, lon)
    lon = min(max(lon + 180.0, 0.0), 359.999999)
    lat = min(max(lat + 90.0, 0.0), 179.999999)
    return g + chr(97 + int(lon % 2 * 12)) + chr(97 + int(lat % 1 * 24))


# A square with more rows than this (big cities) is published as its subsquares instead.
SPLIT = 6000


class Rows:
    """Deduplicated rows: one per (name, kHz, lat, lon)."""

    def __init__(self):
        self.rows = {}

    def add(self, name, lat, lon, f, m=None, mobile=False, t=None):
        lat, lon = round(lat, 5), round(lon, 5)
        key = (name, f, lat, lon)
        old = self.rows.get(key)
        if old is None:
            self.rows[key] = [m, mobile, t]
        else:
            old[0] = merge_mode(old[0], m)
            old[1] = old[1] and mobile  # a base listing beats a mobile one
            old[2] = old[2] or t

    def __len__(self):
        return len(self.rows)

    def tiles(self, level=4):
        """Rows by tile: 4-character squares (big ones split into subsquares), or 2-character fields."""
        cell = grid2 if level == 2 else grid4
        out = {}
        for (name, f, lat, lon), (m, mobile, t) in self.rows.items():
            r = {"c": name, "l": [lat, lon], "f": f}
            if m:
                r["m"] = m
            if mobile:
                r["s"] = "m"
            if t:
                r["t"] = t
            out.setdefault(cell(lat, lon), []).append(r)
        for g in [g for g, rows in out.items() if level == 4 and len(rows) > SPLIT]:
            for r in out.pop(g):
                out.setdefault(grid6(*r["l"]), []).append(r)
        for rows in out.values():
            rows.sort(key=lambda r: (r["c"], r["f"], r["l"]))
        return out


FORMAT = "columnar-1"
MODES = {"nfm": 0, "fm": 1, "dig": 2}  # 3: unknown


def columnar(rows):
    """A tile as columns (README's Output): names once, then per row a name index and whole-number deltas.

    Rows go in latitude, longitude, frequency order so the deltas stay small."""
    names = sorted({r["c"] for r in rows})
    ix = {n: i for i, n in enumerate(names)}
    types = sorted({r["t"] for r in rows if r.get("t")})
    tx = {n: i for i, n in enumerate(types)}
    t = {"n": names, "c": [], "a": [], "o": [], "f": [], "m": [], "s": [], "tn": types, "t": []}
    pa = po = pf = 0
    for r in sorted(rows, key=lambda r: (r["l"][0], r["l"][1], r["f"], r["c"])):
        a, o, f = round(r["l"][0] * 1e5), round(r["l"][1] * 1e5), round(r["f"] * 2)
        t["c"].append(ix[r["c"]])
        t["a"].append(a - pa)
        t["o"].append(o - po)
        t["f"].append(f - pf)
        t["m"].append(MODES.get(r.get("m"), 3))
        t["s"].append(1 if r.get("s") else 0)
        t["t"].append(tx.get(r.get("t"), -1))
        pa, po, pf = a, o, f
    if not any(t["s"]):
        del t["s"]
    if all(m == 3 for m in t["m"]):
        del t["m"]
    if not types:
        del t["tn"], t["t"]
    return t


def write_source(out_dir, source, rows, meta, level=4):
    """Write out/<source>/<GRID>.json and out/<source>/index.json. Returns the index dict."""
    d = os.path.join(out_dir, source)
    os.makedirs(d, exist_ok=True)
    tiles = rows.tiles(level)
    listing = {}
    for g in sorted(tiles):
        with open(os.path.join(d, g + ".json"), "w", encoding="utf-8") as f:
            json.dump(columnar(tiles[g]), f, separators=(",", ":"), ensure_ascii=False)
        listing[g] = len(tiles[g])
    index = dict(meta)
    index["format"] = FORMAT
    index["level"] = level
    index["rows"] = sum(listing.values())
    index["tiles"] = listing
    index["split"] = sorted({g[:4] for g in listing if len(g) == 6})
    with open(os.path.join(d, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"), ensure_ascii=False, indent=None)
    print(f"{source}: {index['rows']} rows in {len(listing)} tiles", flush=True)
    return index
