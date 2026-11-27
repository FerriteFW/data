"""Tests for the fixed-sets source: python3 -m unittest (from the repository root)."""

import copy
import json
import os
import tempfile
import unittest

import build
from fixed import build as fx

SET = {"id": "uk-test", "name": "2m simplex", "displayName": "2 m FM simplex (UK)",
       "description": "Test set.", "category": "amateur", "defaultPower": "Low", "defaultBandwidth": "12.5kHz",
       "defaultMode": "Analog", "rxOnly": False,
       "source": [{"title": "RSGB band plan", "url": "https://rsgb.org/", "date": "2026"}],
       "frequencies": [{"name": "V40 Calling", "rx": 145.5, "tx": 145.5},
                       {"name": "Rpt RB0", "rx": 145.6, "tx": 145.0, "ctcss": 77.0}]}


def files(**kw):
    """One good file per region; kw changes the UK set's keys (None removes one)."""
    out = [{"region": r, "name": r, "sets": [], "splits": []} for r in fx.REGIONS]
    s = copy.deepcopy(SET)
    for k, v in kw.items():
        if v is None:
            s.pop(k)
        else:
            s[k] = v
    out[2]["sets"].append(s)
    return out


def freq(**kw):
    f = {"name": "V40", "rx": 145.5, "tx": 145.5}
    f.update(kw)
    return files(frequencies=[f])


class TheFiles(unittest.TestCase):
    def setUp(self):
        self.files = fx.read_all()

    def test_checked_in_files_are_clean(self):
        self.assertEqual(fx.problems(self.files), [])

    def test_every_region_has_sets(self):
        for d in self.files:
            self.assertTrue(d["sets"], d["region"])

    def test_big_enough(self):
        self.assertGreater(sum(len(d["sets"]) for d in self.files), 50)

    def test_checked_in_layout(self):
        for d in self.files:
            with open(os.path.join(fx.SRC, f"{d['region']}.json"), encoding="ascii") as f:
                self.assertEqual(f.read(), fx.canonical(d), f"{d['region']}: run python3 -m fixed.build --format")

    def test_known_channels(self):
        by = {s["id"]: s for d in self.files for s in d["sets"]}
        marine = {f["name"].split()[0]: f["rx"] for f in by["other-marine-vhf"]["frequencies"]}
        self.assertEqual(marine["CH16"], 156.8)
        pmr = by["eu-pmr446"]["frequencies"]
        self.assertEqual((pmr[0]["rx"], pmr[7]["rx"]), (446.00625, 446.09375))
        self.assertTrue(by["us-noaa-wx"]["rxOnly"])

    def test_licence_free_sets_low_power_and_transmit(self):
        for d in self.files:
            for s in d["sets"]:
                if s["category"] == "licence-free":
                    self.assertEqual((s["defaultPower"], s["rxOnly"]), ("Low", False), s["id"])


class Problems(unittest.TestCase):
    def test_good(self):
        self.assertEqual(fx.problems(files()), [])

    def test_missing_or_extra_keys(self):
        self.assertTrue(fx.problems(files(source=None)))
        self.assertTrue(fx.problems(files(colour="red")))
        self.assertTrue(fx.problems(freq(tone=88.5)))

    def test_bad_set_fields(self):
        for kw in ({"id": "us-test"}, {"id": "UK-Test"}, {"name": "x" * 17}, {"name": "café"},
                   {"category": "cb"}, {"defaultPower": "low"}, {"defaultBandwidth": "20kHz"},
                   {"defaultMode": "FM"}, {"rxOnly": "no"}, {"countries": ["GBR"]}, {"countries": []},
                   {"source": []}, {"source": [{"title": "x", "url": "rsgb.org", "date": "2026"}]},
                   {"frequencies": []}, {"description": ""}):
            self.assertTrue(fx.problems(files(**kw)), kw)
        self.assertEqual(fx.problems(files(name="x" * 16, countries=["GB", "US-AK"])), [])

    def test_licence_free_is_low_power(self):
        self.assertTrue(fx.problems(files(category="licence-free", defaultPower="High")))
        self.assertEqual(fx.problems(files(category="licence-free")), [])

    def test_bad_frequencies(self):
        for kw in ({"rx": 17.9}, {"tx": 700.0}, {"rx": "145.5"}, {"rx": True}, {"ctcss": 300},
                   {"dcs": 89}, {"dcs": 23, "ctcss": 88.5}, {"name": ""}, {"rxOnly": 1}, {"note": ""}):
            self.assertTrue(fx.problems(freq(**kw)), kw)
        self.assertEqual(fx.problems(freq(rx=1296.0, tx=1296.0, dcs=23, rxOnly=True, note="ok")), [])

    def test_id_twice(self):
        fs = files()
        fs[3]["sets"].append(dict(copy.deepcopy(SET), id="uk-test"))
        self.assertTrue(any("twice" in p for p in fx.problems(fs)))

    def test_splits(self):
        fs = files()
        good = {"country": "GB-SCT", "what": "Scotland differs", "sets": ["uk-test"], "source": SET["source"]}
        fs[2]["splits"].append(good)
        self.assertEqual(fx.problems(fs), [])
        fs[2]["splits"].append(dict(good, sets=["uk-nope"]))
        self.assertTrue(fx.problems(fs))

    def test_regions(self):
        self.assertTrue(fx.problems(files()[:-1]))
        fs = files()
        fs[0]["region"] = "XX"
        self.assertTrue(fx.problems(fs))


class Write(unittest.TestCase):
    def test_round_trip_and_index(self):
        fs, meta = fx.build()
        meta["build_date"] = "2026-11-26"
        with tempfile.TemporaryDirectory() as out:
            index = fx.write(out, "fixed", fs, meta)
            self.assertEqual(index["format"], fx.FORMAT)
            self.assertEqual(sorted(index["regions"]), sorted(fx.REGIONS))
            self.assertEqual(index["rows"], sum(len(d["sets"]) for d in fs))
            us = json.load(open(os.path.join(out, "fixed", "US.json")))
            self.assertEqual(us["format"], fx.FORMAT)
            self.assertEqual(us["sets"], fs[0]["sets"])
            keys = fx.row_keys(build.tile_texts_dir(out, "fixed"))
            self.assertEqual(len(keys), index["frequencies"] - self.dupes(fs))

    @staticmethod
    def dupes(fs):
        rows = [(s["id"], f["name"], f["rx"], f["tx"]) for d in fs for s in d["sets"] for f in s["frequencies"]]
        return len(rows) - len(set(rows))


if __name__ == "__main__":
    unittest.main()
