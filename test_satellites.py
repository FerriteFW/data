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
        # ISS, SO-50 and LilacSat-2 (APRS, and the curated FM transponder); AO-7 (linear/CW), FOX-1A (FM
        # transponder off) and TEVEL2-4 (SKIP: unreliable) are not.
        self.assertEqual(sorted(self.by), [25544, 27607, 40908])
        self.assertTrue(self.report.get("skipped (SKIP)"))

    def test_fields(self):
        so = self.by[27607]
        self.assertEqual((so["name"], so["short"], so["status"]), ("SAUDISAT 1C (SO-50)", "SO-50", "active"))
        self.assertEqual(len(so["tle"]), 2)
        t = so["transmitters"][0]
        self.assertEqual((t["mode"], t["up"], t["down"], t["tone"], t["invert"]),
                         ("FM", [145850000, 145850000], [436795000, 436795000], "67.0", False))
        self.assertIn(so["status"], ("active", "inactive", "unknown"))

    def test_so50_arming_tone(self):
        # SO-50: 74.4 Hz arms the timer, 67.0 Hz is the access tone (the curated override).
        t = self.by[27607]["transmitters"][0]
        self.assertEqual((t["tone"], t["arm_tone"]), ("67.0", "74.4"))

    def test_arm_tone_absent_elsewhere(self):
        for s in self.out:
            for t in s["transmitters"]:
                if s["id"] != 27607:
                    self.assertNotIn("arm_tone", t, s["name"])

    def test_override_fills_a_missing_access_tone(self):
        t = sats.transmitter(tx(norad_cat_id=27607, description="Mode V/U FM Voice"))
        self.assertEqual((t["tone"], t["arm_tone"]), ("67.0", "74.4"))
        self.assertNotIn("arm_tone", sats.transmitter(tx(norad_cat_id=27607, uplink_low=145900000)))

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


# SO-131 (UNNE-1B): an Alpha-5 TLE as SatNOGS gives it (NORAD 101101 is A1101); CelesTrak's group lacks it.
SO131 = {"norad_cat_id": 101101,
         "tle1": "1 A1101U 26227CP  26328.98040591  .00007157  00000-0  34172-3 0  9999",
         "tle2": "2 A1101  97.4368  37.6217 0002297  65.6307 294.5167 15.19347377  8239"}


class Curated(unittest.TestCase):
    def setUp(self):
        self.gp = load("celestrak.json")
        self.sat_list = load("satnogs-satellites.json") + [
            {"norad_cat_id": 101101, "name": "UNNE-1B", "status": "in orbit"},
            {"norad_cat_id": 101102, "name": "HADES-L", "status": "in orbit"}]
        self.newest = max(g["EPOCH"] for g in self.gp)

    def fresh(self, t, days=0):
        """SO131's lines re-dated to the fixtures' newest epoch less `days` (checksum fixed)."""
        ep = sats.datetime.datetime.fromisoformat(self.newest) - sats.datetime.timedelta(days=days)
        doy = ep.timetuple().tm_yday + (ep.hour * 3600 + ep.minute * 60 + ep.second) / 86400
        l1 = t["tle1"][:18] + f"{ep.year % 100:02d}{doy:012.8f}" + t["tle1"][32:68]
        return dict(t, tle1=l1 + str(sats._checksum(l1)))

    def test_alpha5_tle_reads(self):
        g = sats.omm_of_tle(SO131["tle1"], SO131["tle2"], "UNNE-1B")
        self.assertEqual(g["NORAD_CAT_ID"], 101101)
        self.assertEqual(g["EPOCH"][:10], "2026-11-24")
        self.assertAlmostEqual(g["MEAN_MOTION"], 15.19347377)
        self.assertAlmostEqual(g["ECCENTRICITY"], 0.0002297)
        self.assertAlmostEqual(g["BSTAR"], 0.34172e-3)
        self.assertEqual(sats.tle_of(g), [SO131["tle1"], SO131["tle2"]])
        self.assertIsNone(sats.omm_of_tle(SO131["tle1"][:-1] + "0", SO131["tle2"], "x"))  # checksum

    def test_tle_round_trip(self):
        for g in self.gp:
            l1, l2 = sats.tle_of(g)
            r = sats.omm_of_tle(l1, l2, g["OBJECT_NAME"])
            self.assertEqual(r["NORAD_CAT_ID"], g["NORAD_CAT_ID"])
            self.assertAlmostEqual(r["MEAN_MOTION"], g["MEAN_MOTION"], places=7)
            self.assertAlmostEqual(r["INCLINATION"], g["INCLINATION"], places=4)

    def test_curated_from_a_fresh_satnogs_tle(self):
        report = {}
        out = {s["id"]: s for s in sats.join(self.gp, load("satnogs-transmitters.json"), self.sat_list, report,
                                             [self.fresh(SO131)])}
        so = out[101101]
        self.assertEqual(so["short"], "SO-131")
        self.assertEqual(so["tle"][0][2:7], "A1101")
        t = so["transmitters"][0]
        self.assertEqual((t["mode"], t["up"], t["down"]), ("FM", [145925000, 145925000], [436888000, 436888000]))
        self.assertNotIn(101102, out)  # no elements for SO-132 here
        self.assertEqual(report.get("curated: not in orbit or no elements"), len(sats.CURATED) - 2)

    def test_stale_tle_left_out(self):
        report = {}
        out = sats.join(self.gp, [], self.sat_list, report, [self.fresh(SO131, days=sats.FRESH.days + 1)])
        self.assertNotIn(101101, {s["id"] for s in out})
        self.assertEqual(report.get("curated: stale TLE"), 1)
        out = sats.join(self.gp, [], self.sat_list, {}, [self.fresh(SO131, days=sats.FRESH.days - 1)])
        self.assertIn(101101, {s["id"] for s in out})

    def test_listen_only(self):
        report = {}
        sat_list = self.sat_list + [{"norad_cat_id": 67279, "name": "GALAPAGOS-UTE-SWSU", "status": "in orbit"}]
        tle = self.fresh(SO131)
        # HC1PX's elements: SO-131's, renumbered (only the join is under test here).
        l1 = tle["tle1"][:2] + "67279" + tle["tle1"][7:68]
        l2 = tle["tle2"][:2] + "67279" + tle["tle2"][7:68]
        tle = {"norad_cat_id": 67279, "tle1": l1 + str(sats._checksum(l1)), "tle2": l2 + str(sats._checksum(l2))}
        out = {s["id"]: s for s in sats.join(self.gp, [], sat_list, report, [tle])}
        t = out[67279]["transmitters"][0]
        self.assertEqual((out[67279]["short"], t["mode"], t["up"], t["down"]), ("HC1PX", "FM", None, [437050000, 437050000]))
        self.assertIn((67279, "FM", (), (437050000, 437050000)), sats.row_keys([json.dumps({"satellites": list(out.values())})]))

    def test_listen_only_satellites_come_last(self):
        sat_list = self.sat_list + [{"norad_cat_id": 67279, "name": "GALAPAGOS-UTE-SWSU", "status": "in orbit"}]
        tle = self.fresh(SO131)
        l1 = tle["tle1"][:2] + "67279" + tle["tle1"][7:68]
        l2 = tle["tle2"][:2] + "67279" + tle["tle2"][7:68]
        tles = [self.fresh(SO131), {"norad_cat_id": 67279, "tle1": l1 + str(sats._checksum(l1)),
                                    "tle2": l2 + str(sats._checksum(l2))}]
        out = sats.join(self.gp, load("satnogs-transmitters.json"), sat_list, {}, tles)
        ids = [s["id"] for s in out]
        # HC1PX (67279, listen only) after SO-131 (101101), though its number is lower.
        self.assertEqual(ids[-1], 67279)
        self.assertEqual(ids[:-1], sorted(ids[:-1]))
        self.assertTrue(all(sats.two_way(s["transmitters"]) for s in out[:-1]))

    def test_order_listen_after_two_way(self):
        two = sats._fm(145_000_000, 435_000_000, "a")
        rx = sats._listen(435_100_000, "b")
        aprs = sats._aprs(145_825_000)
        self.assertEqual(sorted([aprs, rx, two], key=sats.order), [two, rx, aprs])

    def test_curated_and_skip_tables(self):
        self.assertFalse(set(sats.CURATED) & set(sats.SKIP))
        for n, c in sats.CURATED.items():
            self.assertTrue(0 < len(c["short"]) <= 16 and c["short"].isascii(), n)
            self.assertTrue(c["src"].startswith("https://www.amsat.org/"), n)
            for t in c["tx"]:
                self.assertTrue(all(sats.in_band(f) for f in (t["up"] or []) + t["down"]), (n, t))
        self.assertLessEqual(len(sats.CURATED), sats.RADIO_MAX)


class Output(unittest.TestCase):
    def test_write_and_keys(self):
        out = sats.join(load("celestrak.json"), load("satnogs-transmitters.json"), load("satnogs-satellites.json"))
        meta = {"source": "satellites", "build_date": "2026-10-31", "licence": "L", "attribution": "A"}
        with tempfile.TemporaryDirectory() as d:
            index = sats.write(d, "satellites", out, meta)
            self.assertEqual(index["rows"], 3)
            text = open(os.path.join(d, "satellites", "sats.json"), encoding="utf-8").read()
            doc = json.loads(text)
            self.assertEqual(doc["format"], "satellites-1")
            self.assertLessEqual(doc["oldest_epoch"], doc["newest_epoch"])
            self.assertEqual(len(doc["satellites"]), 3)
            so = next(s for s in doc["satellites"] if s["id"] == 27607)
            self.assertEqual(so["transmitters"][0]["arm_tone"], "74.4")
            keys = sats.row_keys([text])
            self.assertIn((27607,), keys)
            self.assertGreater(len(keys), 4)

    def test_build_knows_the_source(self):
        self.assertIs(build.SOURCES["satellites"], sats)


if __name__ == "__main__":
    unittest.main()
