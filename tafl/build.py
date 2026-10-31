"""Canada: ISED's Spectrum Management System authorization data extract (the TAFL).

Run from the repository root: python3 -m tafl.build --cache DIR --out out [--download]

Keeps granted transmit records in 136-174 and 400-470 MHz with coordinates; digital-only ones are left out.
Column numbers are the field codes in ISED's field description
(https://www.ic.gc.ca/engineering/SMS_TAFL_Files/tafl_description_ltaf.pdf); the CSV puts
TX/RX in column 0, so code N is column N.
"""

import argparse
import csv
import datetime
import io
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402

URL = "https://www.ic.gc.ca/engineering/SMS_TAFL_Files/TAFL_LTAF.zip"
UPSTREAM = (URL,)  # rebuilt only when ISED publishes a new extract (build.py)
PAGE = "https://ised-isde.canada.ca/site/spectrum-management-system/en/download-sms-data"

LICENCE = "Open Government Licence – Canada 2.0"
LICENCE_URL = "https://open.canada.ca/en/open-government-licence-canada"
ATTRIBUTION = ("Contains information licensed under the Open Government Licence – Canada. "
               "Source: Innovation, Science and Economic Development Canada, "
               "Spectrum Management System authorization data extract.")

# Columns (field codes)
C_TXRX, C_FREQ, C_AD, C_BW, C_EMISSION = 0, 1, 9, 10, 11
C_ITU_CLASS, C_LAT, C_LON, C_STATUS, C_LICENSEE = 35, 40, 41, 51, 54

GRANTED = {"G", "11"}  # Granted, Authorized
MOBILE_CLASSES = {"ML", "MO"}  # land mobile / mobile station


def row_mode(row):
    m = common.mode([row[C_EMISSION]])
    if m is None and row[C_AD] == "D":
        return "dig"
    return m


def build(cache, download=False):
    zpath = common.download(URL, os.path.join(cache, "TAFL_LTAF.zip"), download)
    z = zipfile.ZipFile(zpath)
    name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    source_date = datetime.date(*z.getinfo(name).date_time[:3]).isoformat()
    rows = common.Rows()
    skipped = {"status": 0, "numbered": 0, "coords": 0}
    with z.open(name) as raw:
        f = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="ignore", newline="")
        for row in csv.reader(f):
            if len(row) <= C_LICENSEE or row[C_TXRX] != "TX":
                continue
            try:
                mhz = float(row[C_FREQ])
            except ValueError:
                continue
            if not common.in_band(mhz):
                continue
            if row[C_STATUS] not in GRANTED:
                skipped["status"] += 1
                continue
            licensee = row[C_LICENSEE].strip()
            if common.is_generic_number_name(licensee):
                skipped["numbered"] += 1
                continue
            try:
                lat, lon = float(row[C_LAT]), float(row[C_LON])
            except ValueError:
                skipped["coords"] += 1
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
                skipped["coords"] += 1
                continue
            rows.add(common.smart_name(licensee), lat, lon, common.khz(mhz),
                     row_mode(row), row[C_ITU_CLASS] in MOBILE_CLASSES, k=common.category(licensee))
    skipped["digital"] = rows.drop_digital()
    print(f"tafl: skipped {skipped}", flush=True)
    meta = {
        "source": "tafl",
        "title": "Canada: ISED Spectrum Management System authorization data (TAFL)",
        "source_url": URL,
        "source_page": PAGE,
        "source_date": source_date,
        "licence": LICENCE,
        "licence_url": LICENCE_URL,
        "attribution": ATTRIBUTION,
    }
    return rows, meta


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--cache", required=True, help="folder for the 64 MB zip (read in place, never unzipped)")
    p.add_argument("--out", default="out")
    p.add_argument("--download", action="store_true", help="download again even if cached")
    a = p.parse_args()
    rows, meta = build(a.cache, a.download)
    meta["build_date"] = datetime.date.today().isoformat()
    common.write_source(a.out, "tafl", rows, meta)


if __name__ == "__main__":
    main()
