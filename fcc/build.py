"""US: FCC Universal Licensing System (ULS) weekly public-access downloads, land mobile.

Run from the repository root: python3 -m fcc.build --cache DIR --out out [--download]

Reads l_LMpriv.zip (Land Mobile - Private: industrial/business, public safety) and
l_LMcomm.zip (Land Mobile - Commercial: commercial and paging) in place, without unzipping.
Joins HD (licence header: status), EN (licensee), LO (locations), FR (frequencies) and
EM (emissions) on the unique system identifier, location number and antenna number.
Keeps active licences, 136-174 and 400-470 MHz, at locations with coordinates; digital-only rows are left out.

Field positions follow the FCC's ULS public access database definitions (pa_ddef);
every table is pipe-separated with the record type in field 0.
"""

import argparse
import datetime
import io
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402

BASE = "https://data.fcc.gov/download/pub/uls/complete/"
FILES = ("l_LMpriv.zip", "l_LMcomm.zip")
PAGE = "https://www.fcc.gov/uls/transactions/daily-weekly"

LICENCE = "Public domain in the US (work of the US federal government, 17 U.S.C. § 105)"
LICENCE_URL = "https://www.usa.gov/government-copyright"
ATTRIBUTION = ("Source: US Federal Communications Commission, Universal Licensing System "
               "public access data (land mobile). Not endorsed by the FCC.")

# HD: licence header
HD_USI, HD_STATUS, HD_SERVICE = 1, 5, 6
# EN: entities (type L = licensee)
EN_USI, EN_TYPE, EN_NAME, EN_FIRST, EN_LAST = 1, 5, 7, 8, 10
# LO: locations
LO_USI, LO_NUM = 1, 8
LO_LAT = (19, 20, 21, 22)   # degrees, minutes, seconds, N/S
LO_LON = (23, 24, 25, 26)   # degrees, minutes, seconds, E/W
# FR: frequencies
FR_USI, FR_LOC, FR_ANT, FR_CLASS, FR_FREQ = 1, 6, 7, 8, 10
# EM: emissions
EM_USI, EM_LOC, EM_ANT, EM_FREQ, EM_CODE = 1, 5, 6, 7, 9


def lines(z, table):
    """The rows of one .dat table, split on '|'. Records never span lines in these files."""
    with z.open(table + ".dat") as raw:
        for line in io.TextIOWrapper(raw, encoding="latin-1", newline="\n"):
            yield line.rstrip("\r\n").split("|")


def dms(parts):
    d, m, s, h = parts
    if not d:
        return None
    try:
        v = float(d) + float(m or 0) / 60 + float(s or 0) / 3600
    except ValueError:
        return None
    return -v if h.upper() in ("S", "W") else v


def freq_key(s):
    try:
        return round(float(s) * 100000)
    except ValueError:
        return None


def source_date(z):
    """'File Creation Date: Sun Oct 25 09:20:13 EDT 2026' in the zip's counts file."""
    try:
        text = z.read("counts").decode("latin-1")
        m = re.search(r"File Creation Date:\s*\w+\s+(\w+)\s+(\d+)\s+[\d:]+\s+\w+\s+(\d{4})", text)
        if m:
            return datetime.datetime.strptime(" ".join(m.groups()), "%b %d %Y").date().isoformat()
    except KeyError:
        pass
    y, mo, d = z.infolist()[0].date_time[:3]
    return datetime.date(y, mo, d).isoformat()


def build_file(zpath, rows, stats):
    z = zipfile.ZipFile(zpath)
    active = {}
    for r in lines(z, "HD"):
        if len(r) > HD_SERVICE and r[HD_STATUS] == "A":
            active[r[HD_USI]] = r[HD_SERVICE]
    names = {}
    for r in lines(z, "EN"):
        if len(r) > EN_LAST and r[EN_TYPE] == "L" and r[EN_USI] in active:
            n = r[EN_NAME].strip() or f"{r[EN_FIRST].strip()} {r[EN_LAST].strip()}".strip()
            names[r[EN_USI]] = n
    locs = {}
    for r in lines(z, "LO"):
        if len(r) > LO_LON[3] and r[LO_USI] in active:
            lat, lon = dms([r[i] for i in LO_LAT]), dms([r[i] for i in LO_LON])
            if lat is not None and lon is not None and not (lat == 0 and lon == 0):
                locs[(r[LO_USI], r[LO_NUM])] = (lat, lon)
    picked = {}  # (usi, loc, ant, freq key) -> (name, lat, lon, kHz, mobile, category)
    for r in lines(z, "FR"):
        if len(r) <= FR_FREQ or r[FR_USI] not in active:
            continue
        try:
            mhz = float(r[FR_FREQ])
        except ValueError:
            continue
        if not common.in_band(mhz):
            continue
        usi = r[FR_USI]
        ll = locs.get((usi, r[FR_LOC]))
        if ll is None:
            stats["no_coords"] += 1
            continue
        name = names.get(usi, "")
        if not name or common.is_generic_number_name(name):
            stats["no_name"] += 1
            continue
        mobile = r[FR_CLASS].upper().startswith("MO")
        key = (usi, r[FR_LOC], r[FR_ANT], freq_key(r[FR_FREQ]))
        picked[key] = (common.smart_name(name), ll[0], ll[1], common.khz(mhz), mobile,
                       common.category(name, active[usi]))
        stats["services"][active[usi]] = stats["services"].get(active[usi], 0) + 1
    emissions = {}
    for r in lines(z, "EM"):
        if len(r) <= EM_CODE:
            continue
        key = (r[EM_USI], r[EM_LOC], r[EM_ANT], freq_key(r[EM_FREQ]))
        if key in picked:
            emissions.setdefault(key, []).append(r[EM_CODE])
    for key, (name, lat, lon, f, mobile, k) in picked.items():
        rows.add(name, lat, lon, f, common.mode(emissions.get(key, [])), mobile, k=k)
    stats["frequencies"] += len(picked)
    return source_date(z)


def build(cache, download=False):
    rows = common.Rows()
    stats = {"no_coords": 0, "no_name": 0, "frequencies": 0, "services": {}}
    dates = []
    for fn in FILES:
        zpath = common.download(BASE + fn, os.path.join(cache, fn), download)
        dates.append(build_file(zpath, rows, stats))
        print(f"fcc: {fn} done, {len(rows)} rows so far", flush=True)
    stats["digital"] = rows.drop_digital()
    print(f"fcc: {stats}", flush=True)
    meta = {
        "source": "fcc",
        "title": "US: FCC Universal Licensing System, land mobile (private and commercial)",
        "source_url": [BASE + fn for fn in FILES],
        "source_page": PAGE,
        "source_date": max(dates),
        "licence": LICENCE,
        "licence_url": LICENCE_URL,
        "attribution": ATTRIBUTION,
    }
    return rows, meta


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cache", required=True, help="folder for the zips (about 500 MB, read in place)")
    p.add_argument("--out", default="out")
    p.add_argument("--download", action="store_true", help="download again even if cached")
    a = p.parse_args()
    rows, meta = build(a.cache, a.download)
    meta["build_date"] = datetime.date.today().isoformat()
    common.write_source(a.out, "fcc", rows, meta)


if __name__ == "__main__":
    main()
