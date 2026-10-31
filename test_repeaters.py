"""Tests for the repeaters source and the stats log: python3 -m unittest (from the repository root)."""

import csv
import os
import tempfile
import unittest
from unittest import mock

import build
import common
from common import columnar, tone
from repeaters import build as repeaters


def entry(**kw):
    r = {"id": 1, "callsign": "VE7RHS", "latitude": 49.26973, "longitude": -123.24992, "mode": "FM",
         "encode": "100.0", "decode": "", "frequency": 145270000, "offset": -600000, "operational": 1}
    r.update(kw)
    return r


class Tones(unittest.TestCase):
    def test_ctcss(self):
        for text, want in (("100.0", "100.0"), ("100", "100.0"), (" 88.5", "88.5"), ("151.4*", "151.4"),
                           ("100.", "100.0"), ("103", "103.5"), ("127.2", "127.3"), ("67.0/NAC770", "67.0"),
                           ("NAC293/123.0", "123.0"), ("CC1/146.2", "146.2"), ("B/71.9/88.5", "71.9")):
            self.assertEqual(tone(text), want, text)

    def test_dcs(self):
        for text, want in (("DCS023", "D023"), ("D244", "D244"), ("DCS 043", "D043"), ("DCS51", "D051"),
                           ("dpl 411", "D411"), ("DCS172.0", "D172"), ("D031*", "D031"), ("023", "D023"),
                           ("223", "D223"), ("NAC671/D411", "D411"), ("D023I", "D023I")):
            self.assertEqual(tone(text), want, text)

    def test_none(self):
        for text in ("", " ", "0", "0.00", "CC1", "COS", "1\xa0750.0", "1750.0", "DCS 740", "DCS100", "165.0", "2"):
            self.assertIsNone(tone(text), text)


class Keep(unittest.TestCase):
    def why(self, **kw):
        return repeaters.keep(entry(**kw))

    def test_keeps_operational_analog_in_band(self):
        self.assertIsNone(self.why())
        self.assertIsNone(self.why(mode="YSF/FM "))  # mixed: passes analog too
        self.assertIsNone(self.why(mode="NFM", frequency=446500000, offset=-5000000))
        self.assertIsNone(self.why(frequency=224940000, offset=-1600000))  # 1.25 m
        self.assertIsNone(self.why(frequency=219500000, offset=0))  # Canada's 1.25 m starts at 219

    def test_drops(self):
        self.assertEqual(self.why(operational=0), "not operational")
        self.assertEqual(self.why(mode="DMR"), "not analog FM")
        self.assertEqual(self.why(mode="D-STAR"), "not analog FM")
        self.assertEqual(self.why(frequency=29620000), "out of band")
        self.assertEqual(self.why(frequency=927500000), "out of band")
        self.assertEqual(self.why(frequency=146000000, offset=-94000000), "input out of band")
        self.assertEqual(self.why(latitude=0, longitude=0), "no position")
        self.assertEqual(self.why(callsign="  "), "no callsign")

    def test_rows_and_report(self):
        report = {}
        rows = repeaters.rows_of([entry(), entry(id=2), entry(operational=0), entry(mode="NFM", callsign="VE7NFM")],
                                 report)
        self.assertEqual(report, {"duplicate": 1, "not operational": 1})
        tile = rows.tiles(repeaters.LEVEL)["CN"]
        self.assertEqual([(r["c"], r["d"], r["pe"], r["pd"], r.get("m")) for r in tile],
                         [("VE7NFM", -600, "100.0", None, "nfm"), ("VE7RHS", -600, "100.0", None, None)])


class Columns(unittest.TestCase):
    def test_offset_and_tone_columns(self):
        rows = [{"c": "A", "l": [49.0, -123.0], "f": 145270, "d": -600, "pe": "100.0", "pd": None},
                {"c": "B", "l": [49.1, -123.0], "f": 443200, "d": 5000, "pe": "D023", "pd": "D023"},
                {"c": "C", "l": [49.2, -123.0], "f": 146520, "d": 0, "pe": None, "pd": None}]
        t = columnar(rows)
        self.assertEqual(t["d"], [-1200, 10000, 0])
        self.assertEqual(t["pn"], ["100.0", "D023"])
        self.assertEqual(t["pe"], [0, 1, -1])
        self.assertEqual(t["pd"], [-1, 1, -1])

    def test_left_out_for_other_sources(self):
        t = columnar([{"c": "A", "l": [49.0, -123.0], "f": 150000}])
        for k in ("d", "pn", "pe", "pd"):
            self.assertNotIn(k, t)


class Stats(unittest.TestCase):
    def run_stats(self, live_csv, built=("tafl", "repeaters")):
        top = {"build_date": "2026-11-08", "sources": [{"source": "tafl", "rows": 5}, {"source": "repeaters", "rows": 7}]}
        feeds = {"repeaters": {"entries": 30, "operational": 20, "max_id": 99}}
        with tempfile.TemporaryDirectory() as d:
            if live_csv is None:
                opener = mock.patch("urllib.request.urlopen", side_effect=OSError("404"))
            else:
                resp = mock.MagicMock()
                resp.__enter__.return_value.read.return_value = live_csv.encode()
                opener = mock.patch("urllib.request.urlopen", return_value=resp)
            with opener:
                build.write_stats(d, top, set(built), feeds, "https://example.invalid")
            with open(os.path.join(d, "stats.csv"), encoding="utf-8") as f:
                return list(csv.DictReader(f))

    def test_fresh(self):
        lines = self.run_stats(None)
        self.assertEqual([(ln["source"], ln["rows"], ln["feed_operational"], ln["feed_max_id"], ln["feed_entries"])
                          for ln in lines], [("tafl", "5", "", "", ""), ("repeaters", "7", "20", "99", "30")])

    def test_carries_forward_and_replaces_today(self):
        old = ("build_date,source,rows,feed_operational,feed_max_id,feed_entries\n"
               "2026-10-08,tafl,4,,,\n2026-11-08,tafl,3,,,\n")
        lines = self.run_stats(old)
        self.assertEqual([(ln["build_date"], ln["source"], ln["rows"]) for ln in lines],
                         [("2026-10-08", "tafl", "4"), ("2026-11-08", "tafl", "5"), ("2026-11-08", "repeaters", "7")])


    def test_kept_source_adds_no_line(self):
        lines = self.run_stats("build_date,source,rows,feed_operational,feed_max_id,feed_entries\n2026-10-08,tafl,4,,,\n",
                               built=("repeaters",))
        self.assertEqual([(ln["build_date"], ln["source"]) for ln in lines],
                         [("2026-10-08", "tafl"), ("2026-11-08", "repeaters")])


if __name__ == "__main__":
    unittest.main()
