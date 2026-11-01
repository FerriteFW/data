"""Tests for the satellites source: python3 -m unittest (from the repository root).
Fixtures in fixtures/satellites/ are a few real CelesTrak and SatNOGS records, trimmed by hand."""

import json
import os
import tempfile
import unittest

import build
from satellites import build as sats

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "satellites")


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


def tx(**kw):
    t = {"alive": True, "status": "active", "type": "Transceiver", "mode": "FM", "uplink_low": 145850000,
         "uplink_high": None, "downlink_low": 436795000, "downlink_high": None, "invert": False,
         "description": "Mode V/U FM Voice"}
    t.update(kw)
    return t


class Filter(unittest.TestCase):
    def test_keeps_fm_and_aprs_in_band(self):
        self.assertIsNone(sats.usable(tx()))
        self.assertIsNone(sats.usable(tx(mode="FMN")))
        self.assertIsNone(sats.usable(tx(mode="AFSK", description="Mode V APRS", uplink_low=145825000,
                                         downlink_low=145825000)))

    def test_drops_by_mode(self):
        for mode, desc in (("USB", "Linear"), ("CW", "Beacon"), ("BPSK", "TLM"), ("GMSK", "9k6"),
                           ("AFSK", "AFSK9k6 digital data"), ("AFSK", "1k2 AFSK TLM"), ("SSTV", "")):
            self.assertIsNotNone(sats.usable(tx(mode=mode, description=desc)), mode + desc)

    def test_downlink_only_is_a_beacon(self):
        self.assertIsNotNone(sats.usable(tx(uplink_low=None, uplink_high=None)))
        self.assertIsNotNone(sats.usable(tx(type="Transmitter", mode="AFSK", uplink_low=None)))

    def test_drops_dead(self):
        self.assertIsNotNone(sats.usable(tx(alive=False)))
        self.assertIsNotNone(sats.usable(tx(status="inactive")))

    def test_band(self):
        self.assertIsNotNone(sats.usable(tx(uplink_low=1267300000)))  # L band uplink
        self.assertIsNotNone(sats.usable(tx(downlink_low=29400000)))
        self.assertIsNone(sats.usable(tx(uplink_low=144490000, downlink_low=145800000)))
        self.assertIsNotNone(sats.usable(tx(downlink_low=148500000)))


class Names(unittest.TestCase):
    def test_short(self):
        for name, want in (("OSCAR 7 (AO-7)", "AO-7"), ("ISS (ZARYA)", "ISS"), ("SAUDISAT 1C (SO-50)", "SO-50"),
                           ("DIWATA-2B", "DIWATA-2B"), ("CAS-2T & KS-1Q", "CAS-2T & KS-1Q"),
                           ("A VERY LONG SATELLITE NAME INDEED", "A VERY LONG SATE")):
            got = sats.short_name(name)
            self.assertEqual(got, want)
            self.assertLessEqual(len(got), 16)


class Tones(unittest.TestCase):
    def test_tone(self):
        for desc, want in (("Mode V/U FM Voice CTCSS 67.0 Hz", "67.0"), ("Mode V/U FM - Voice Repeater CTCSS 67.0 Hz", "67.0"),
                           ("FM, PL 141.3", "141.3"), ("Mode U/V FM Voice (no CTCSS any longer)", None),
                           ("FM Transponder", None), ("", None), (None, None), ("Mode V/V FM (crew R1)", None)):
            self.assertEqual(sats.tone_of(desc), want, desc)


class Tle(unittest.TestCase):
    def test_matches_celestrak_tle(self):
        want = open(os.path.join(FIX, "tle.txt"), encoding="utf-8").read().split("\n")[:2]
        iss = next(g for g in load("celestrak.json") if g["NORAD_CAT_ID"] == 25544)
        self.assertEqual(sats.tle_of(iss), want)

    def test_lines_are_69_characters_with_checksums(self):
        for g in load("celestrak.json"):
            for line in sats.tle_of(g):
                self.assertEqual(len(line), 69)
                self.assertEqual(int(line[-1]), sats._checksum(line[:-1]))


class Join(unittest.TestCase):
    def setUp(self):
        self.report = {}
        self.out = sats.join(load("celestrak.json"), load("satnogs-transmitters.json"),
                             load("satnogs-satellites.json"), self.report)
        self.by = {s["id"]: s for s in self.out}

    def test_who_is_kept(self):
        # ISS, SO-50, LilacSat-2 (APRS) and TEVEL2-4; AO-7 (linear/CW) and FOX-1A (FM transponder off) are not.
        self.assertEqual(sorted(self.by), [25544, 27607, 40908, 63213])

    def test_fields(self):
        so = self.by[27607]
        self.assertEqual((so["name"], so["short"], so["status"]), ("SAUDISAT 1C (SO-50)", "SO-50", "active"))
        self.assertEqual(len(so["tle"]), 2)
        t = so["transmitters"][0]
        self.assertEqual((t["mode"], t["up"], t["down"], t["tone"], t["invert"]),
                         ("FM", [145850000, 145850000], [436795000, 436795000], "67.0", False))
        self.assertIn(so["status"], ("active", "inactive", "unknown"))

    def test_iss_transmitters_ordered(self):
        modes = [t["mode"] for t in self.by[25544]["transmitters"]]
        self.assertEqual(modes, sorted(modes, key=lambda m: m != "FM"))
        first = self.by[25544]["transmitters"][0]
        self.assertEqual((first["mode"], first["tone"]), ("FM", "67.0"))  # the voice repeater first
        self.assertGreaterEqual(len(modes), 3)

    def test_no_linear_or_dead(self):
        for s in self.out:
            for t in s["transmitters"]:
                self.assertIn(t["mode"], ("FM", "APRS"))
                for hz in t["up"] + t["down"]:
                    self.assertTrue(sats.in_band(hz))

    def test_reentered_is_dropped(self):
        sat_list = load("satnogs-satellites.json")
        for s in sat_list:
            if s["norad_cat_id"] == 27607:
                s["status"] = "re-entered"
        out = sats.join(load("celestrak.json"), load("satnogs-transmitters.json"), sat_list)
        self.assertNotIn(27607, [s["id"] for s in out])

    def test_no_elements_is_dropped(self):
        gp = [g for g in load("celestrak.json") if g["NORAD_CAT_ID"] != 27607]
        out = sats.join(gp, load("satnogs-transmitters.json"), load("satnogs-satellites.json"))
        self.assertNotIn(27607, [s["id"] for s in out])

    def test_stale_elements_are_unknown(self):
        gp = load("celestrak.json")
        for g in gp:
            if g["NORAD_CAT_ID"] == 27607:
                g["EPOCH"] = "2020-01-01T00:00:00.000000"
        out = {s["id"]: s for s in sats.join(gp, load("satnogs-transmitters.json"), load("satnogs-satellites.json"))}
        self.assertEqual(out[27607]["status"], "unknown")
        self.assertEqual(out[25544]["status"], "active")


class Output(unittest.TestCase):
    def test_write_and_keys(self):
        out = sats.join(load("celestrak.json"), load("satnogs-transmitters.json"), load("satnogs-satellites.json"))
        meta = {"source": "satellites", "build_date": "2026-10-31", "licence": "L", "attribution": "A"}
        with tempfile.TemporaryDirectory() as d:
            index = sats.write(d, "satellites", out, meta)
            self.assertEqual(index["rows"], 4)
            text = open(os.path.join(d, "satellites", "sats.json"), encoding="utf-8").read()
            doc = json.loads(text)
            self.assertEqual(doc["format"], "satellites-1")
            self.assertLessEqual(doc["oldest_epoch"], doc["newest_epoch"])
            self.assertEqual(len(doc["satellites"]), 4)
            keys = sats.row_keys([text])
            self.assertIn((27607,), keys)
            self.assertGreater(len(keys), 4)

    def test_build_knows_the_source(self):
        self.assertIs(build.SOURCES["satellites"], sats)


if __name__ == "__main__":
    unittest.main()
