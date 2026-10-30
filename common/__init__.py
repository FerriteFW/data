"""Shared pieces for the TAFL and FCC builds: bands, names, modes, tiles, downloads."""

import json
import os
import re
import urllib.request

# Ferrite's bands, MHz (the same as Console's TAFL tab).
BANDS = ((136.0, 174.0), (400.0, 470.0))


def in_band(mhz):
    return any(lo <= mhz <= hi for lo, hi in BANDS)


def khz(mhz):
    """MHz to kHz, keeping 6.25 kHz channels' half kHz (469.9875 MHz is 469987.5, not 469987)."""
    k = round(mhz * 1000, 2)
    return int(k) if k == int(k) else k


def download(url, path, force=False):
    """Fetch url to path unless it is already there. Returns the path."""
    if force or not os.path.exists(path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        print(f"Downloading {url}", flush=True)
        tmp = path + ".part"
        req = urllib.request.Request(url, headers={"User-Agent": "ferrite-data (https://data.ferritefw.dev)"})
        with urllib.request.urlopen(req) as r, open(tmp, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
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
def grid4(lat, lon):
    """4-character Maidenhead square ('CN89' for Vancouver)."""
    lon = min(max(lon + 180.0, 0.0), 359.999999)
    lat = min(max(lat + 90.0, 0.0), 179.999999)
    return (chr(65 + int(lon // 20)) + chr(65 + int(lat // 10))
            + str(int(lon % 20 // 2)) + str(int(lat % 10)))


class Rows:
    """Deduplicated rows: one per (name, kHz, lat, lon)."""

    def __init__(self):
        self.rows = {}

    def add(self, name, lat, lon, f, m=None, mobile=False):
        lat, lon = round(lat, 5), round(lon, 5)
        key = (name, f, lat, lon)
        old = self.rows.get(key)
        if old is None:
            self.rows[key] = [m, mobile]
        else:
            old[0] = merge_mode(old[0], m)
            old[1] = old[1] and mobile  # a base listing beats a mobile one

    def __len__(self):
        return len(self.rows)

    def tiles(self):
        out = {}
        for (name, f, lat, lon), (m, mobile) in self.rows.items():
            r = {"c": name, "l": [lat, lon], "f": f}
            if m:
                r["m"] = m
            if mobile:
                r["s"] = "m"
            out.setdefault(grid4(lat, lon), []).append(r)
        for rows in out.values():
            rows.sort(key=lambda r: (r["c"], r["f"], r["l"]))
        return out


def write_source(out_dir, source, rows, meta):
    """Write out/<source>/<GRID>.json and out/<source>/index.json. Returns the index dict."""
    d = os.path.join(out_dir, source)
    os.makedirs(d, exist_ok=True)
    tiles = rows.tiles()
    listing = {}
    for g in sorted(tiles):
        with open(os.path.join(d, g + ".json"), "w", encoding="utf-8") as f:
            json.dump(tiles[g], f, separators=(",", ":"), ensure_ascii=False)
        listing[g] = len(tiles[g])
    index = dict(meta)
    index["rows"] = sum(listing.values())
    index["tiles"] = listing
    with open(os.path.join(d, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"), ensure_ascii=False, indent=None)
    print(f"{source}: {index['rows']} rows in {len(listing)} tiles", flush=True)
    return index
