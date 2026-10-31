"""Shared pieces for the TAFL and FCC builds: bands, names, modes, tiles, downloads."""

import json
import os
import re
import subprocess
import unicodedata

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
# Category (the tiles' k column)
# -------------------------------------------------------------------------
BUSINESS, PUBLIC_SAFETY, TRANSIT, UTILITIES, MARINE, SCHOOLS, GOVERNMENT = range(7)
CATEGORY_NAMES = ("business", "public safety", "transit", "utilities", "marine", "schools", "government")

# FCC radio service codes that decide on their own: the Public Safety Pool, conventional and trunked.
# (The 700/800 MHz public-safety codes, GE/YE/SG/SY, are outside our bands.) Every other service, and the TAFL,
# which has none, goes by the licensee's name.
SERVICE_CATEGORY = {"PW": PUBLIC_SAFETY, "YW": PUBLIC_SAFETY}

# Whole words or phrases in the licensee's full name (lower case, accents and punctuation gone; a trailing * is
# any ending: fortis* takes FortisBC), tried in this order: the first category with a match wins. Government
# comes after the specific ones ("City of Vancouver Fire" is public safety) and before marine ("City of Port
# Moody" isn't a port).
CATEGORY_WORDS = (
    (PUBLIC_SAFETY, (
        "police", "fire", "wildfire", "sheriff", "sheriffs", "ems", "ambulance", "paramedic", "paramedics",
        "rcmp", "911", "e comm", "emergency", "rescue",
        "incendie", "incendies", "pompiers", "securite civile",
    )),
    (TRANSIT, (
        "transit", "translink", "rail", "railway", "railroad", "bnsf", "amtrak", "cn rail", "cpkc",
        "canadian pacific", "bus", "buslines",
    )),
    (UTILITIES, (
        "hydro", "electric", "power", "gas", "water", "utility", "utilities", "fortis*", "pud",
    )),
    (SCHOOLS, (
        "school", "schools", "sd", "university", "college", "commission scolaire", "ecole", "universite",
    )),
    (GOVERNMENT, (
        "city of", "county", "town of", "township", "municipality", "district of", "village", "regional district",
        "ministry", "state of", "province", "dept", "department", "government", "majesty",
        "ville de", "municipalite", "ministere", "gouvernement",
    )),
    (MARINE, (
        "port", "harbour", "harbor", "marine", "ferries", "ferry", "coast guard", "pilotage", "pilots",
    )),
)


def _words(words):
    """One pattern for a category's words, each matched whole."""
    return re.compile(r"\b(?:" + "|".join(re.escape(w.rstrip("*")) + (r"\w*" if w.endswith("*") else "")
                                         for w in words) + r")\b")


_CATEGORY_RE = [(k, _words(words)) for k, words in CATEGORY_WORDS]


def _plain(name):
    """Lower case, no accents, punctuation as spaces: 'E-Comm 9-1-1' -> 'e comm 911'."""
    s = unicodedata.normalize("NFKD", name.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"(?<=\d)-(?=\d)", "", s)  # 9-1-1 -> 911
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def category(name, service=None):
    """The row's category code (README's Output, `k`) from the licensee's full name and, for the FCC, its
    radio service code. 0 when nothing says otherwise."""
    if service in SERVICE_CATEGORY:
        return SERVICE_CATEGORY[service]
    plain = _plain(name)
    for k, pat in _CATEGORY_RE:
        if pat.search(plain):
            return k
    return BUSINESS


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

    def add(self, name, lat, lon, f, m=None, mobile=False, t=None, k=BUSINESS):
        lat, lon = round(lat, 5), round(lon, 5)
        key = (name, f, lat, lon)
        old = self.rows.get(key)
        if old is None:
            self.rows[key] = [m, mobile, t, k]
        else:
            old[0] = merge_mode(old[0], m)
            old[1] = old[1] and mobile  # a base listing beats a mobile one
            old[2] = old[2] or t
            old[3] = old[3] or k  # two licensees shortened alike: a category beats none

    def __len__(self):
        return len(self.rows)

    def drop_digital(self):
        """Leave out digital-only rows (Ferrite has no digital modes). Run after every add: a row's mode is only
        settled once all its listings are in (analog beats digital). Returns how many went."""
        dig = [key for key, (m, *_rest) in self.rows.items() if m == "dig"]
        for key in dig:
            del self.rows[key]
        return len(dig)

    def tiles(self, level=4):
        """Rows by tile: 4-character squares (big ones split into subsquares), or 2-character fields."""
        cell = grid2 if level == 2 else grid4
        out = {}
        for (name, f, lat, lon), (m, mobile, t, k) in self.rows.items():
            r = {"c": name, "l": [lat, lon], "f": f}
            if k:
                r["k"] = k
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
    t = {"n": names, "c": [], "a": [], "o": [], "f": [], "m": [], "s": [], "tn": types, "t": [], "k": []}
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
        t["k"].append(r.get("k", BUSINESS))
        pa, po, pf = a, o, f
    if not any(t["s"]):
        del t["s"]
    if all(m == 3 for m in t["m"]):
        del t["m"]
    if not types:
        del t["tn"], t["t"]
    if not any(t["k"]):
        del t["k"]
    return t


def write_source(out_dir, source, rows, meta, level=4):
    """Write out/<source>/<GRID>.json and out/<source>/index.json. Returns the index dict."""
    d = os.path.join(out_dir, source)
    os.makedirs(d, exist_ok=True)
    tiles = rows.tiles(level)
    listing = {}
    cats = [0] * len(CATEGORY_NAMES)
    for g in sorted(tiles):
        for r in tiles[g]:
            cats[r.get("k", BUSINESS)] += 1
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
    if any(cats[1:]):
        print(f"{source}: categories " + ", ".join(f"{n} {c}" for n, c in zip(CATEGORY_NAMES, cats)), flush=True)
    return index
