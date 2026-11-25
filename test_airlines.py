"""Tests for the airlines source: python3 -m unittest (from the repository root)."""

import json
import os
import tempfile
import unittest

import build
from airlines import build as air

GOOD = [{"iata": "AC", "icao": "ACA", "name": "Air Canada", "country": "CA", "note": ""},
        {"iata": "QK", "icao": "JZA", "name": "Jazz", "country": "CA", "note": "regional"},
        {"iata": "W8", "icao": "CJT", "name": "Cargojet", "country": "CA", "note": "cargo"}]


def with_row(**kw):
    rows = [dict(r) for r in GOOD]
    rows[1].update(kw)
    return rows


class TheList(unittest.TestCase):
    def setUp(self):
        self.rows = air.read()

    def test_checked_in_list_is_clean(self):
        self.assertEqual(air.problems(self.rows), [])

    def test_big_enough(self):
        self.assertGreater(len(self.rows), 450)

    def test_known_rows(self):
        by = {r["iata"]: r for r in self.rows}
        self.assertEqual(by["AC"]["name"], "Air Canada")
        self.assertEqual(by["QK"]["note"], "regional")
        self.assertEqual((by["FX"]["icao"], by["FX"]["note"]), ("FDX", "cargo"))
        self.assertEqual(by["9K"]["country"], "US")

    def test_file_is_ascii(self):
        with open(air.CSV, "rb") as f:
            self.assertTrue(f.read().isascii())


class Problems(unittest.TestCase):
    def test_good(self):
        self.assertEqual(air.problems(GOOD), [])

    def test_empty_icao_is_fine(self):
        self.assertEqual(air.problems(with_row(icao="")), [])

    def test_bad_codes(self):
        for kw in ({"iata": "Q"}, {"iata": "QKX"}, {"iata": "qk"}, {"iata": "99"}, {"icao": "JZ"},
                   {"icao": "JZ1"}, {"country": "CAN"}, {"note": "freight"}):
            self.assertTrue(air.problems(with_row(**kw)), kw)

    def test_bad_names(self):
        for name in ("", "x" * 25, "Widerøe", " Jazz", "Jazz  Air"):
            self.assertTrue(air.problems(with_row(name=name)), name)
        self.assertEqual(air.problems(with_row(name="x" * 24)), [])

    def test_duplicates_and_order(self):
        self.assertTrue(air.problems(GOOD + [dict(GOOD[0])]))
        self.assertTrue(air.problems(with_row(icao="ACA")))
        self.assertTrue(air.problems(list(reversed(GOOD))))

    def test_header(self):
        with self.assertRaises(ValueError):
            air.parse("iata,name\nAC,Air Canada\n")


class Output(unittest.TestCase):
    def test_write_and_keys(self):
        meta = {"source": "airlines", "build_date": "2026-11-24", "licence": "L", "attribution": "A"}
        with tempfile.TemporaryDirectory() as d:
            index = air.write(d, "airlines", GOOD, meta)
            self.assertEqual((index["rows"], index["cargo"], index["regional"]), (3, 1, 1))
            self.assertEqual(index["format"], "airlines-1")
            self.assertEqual(index["tiles"], {"airlines.csv": 3})
            text = open(os.path.join(d, "airlines", "airlines.csv"), encoding="ascii").read()
            self.assertEqual(air.parse(text), GOOD)
            self.assertEqual(json.load(open(os.path.join(d, "airlines", "index.json")))["rows"], 3)
            keys = air.row_keys([text, '{"rows":3}'])
            self.assertIn(("QK", "JZA", "Jazz", "CA", "regional"), keys)
            self.assertEqual(len(keys), 3)

    def test_build_downloads_nothing(self):
        with tempfile.TemporaryDirectory() as cache:
            rows, meta = air.build(cache, download=True)
            self.assertEqual(os.listdir(cache), [])
        self.assertEqual(meta["source"], "airlines")
        self.assertGreater(len(rows), 450)

    def test_build_knows_the_source(self):
        self.assertIs(build.SOURCES["airlines"], air)


if __name__ == "__main__":
    unittest.main()
