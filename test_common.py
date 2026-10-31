"""Tests for common/: python3 -m unittest (from the repository root)."""

import unittest

import common
from common import (BUSINESS, GOVERNMENT, MARINE, PUBLIC_SAFETY, SCHOOLS, TRANSIT, UTILITIES, category,
                    columnar)


class Category(unittest.TestCase):
    def check(self, want, *names):
        for n in names:
            self.assertEqual(category(n), want, n)

    def test_public_safety(self):
        self.check(PUBLIC_SAFETY, "Vancouver Police Board", "City of Vancouver Fire Rescue Services",
                   "Royal Canadian Mounted Police", "RCMP E Division", "E-Comm Emergency Communications",
                   "BC Emergency Health Services", "King County Sheriff's Office", "Service de sécurité incendie",
                   "Ambulance New Brunswick", "Kitsap 9-1-1")

    def test_transit(self):
        self.check(TRANSIT, "South Coast British Columbia Transportation Authority (TransLink)",
                   "Canadian National Railway Company", "BNSF Railway Co", "National Railroad Passenger Corp",
                   "Coast Mountain Bus Company")

    def test_utilities(self):
        self.check(UTILITIES, "British Columbia Hydro and Power Authority", "FortisBC Energy Inc.",
                   "Fortis BC", "Puget Sound Energy (gas)", "Snohomish County PUD No. 1", "Hydro-Québec")

    def test_marine(self):
        self.check(MARINE, "Vancouver Fraser Port Authority", "British Columbia Ferry Services Inc.",
                   "Canadian Coast Guard", "Pacific Pilotage Authority", "Seaspan Marine Corp")

    def test_schools(self):
        self.check(SCHOOLS, "Board of Education of School District No. 39", "University of British Columbia",
                   "Douglas College", "SD 43 Coquitlam", "Commission scolaire de Montréal")

    def test_government(self):
        self.check(GOVERNMENT, "City of Burnaby", "Vancouver, City of", "Corporation of the District of Saanich",
                   "Metro Vancouver Regional District", "Ministry of Transportation and Infrastructure",
                   "Snohomish County", "Township of Langley", "State of Washington Dept of Transportation",
                   "City of Port Moody", "Ville de Montréal", "His Majesty the King in right of Canada")

    def test_business(self):
        self.check(BUSINESS, "Acme Towing Ltd", "Firestone Tire", "Business Radio Rentals", "Airport Parking Inc",
                   "Watermark Hotels", "Powerhouse Gym", "Transport Leclerc")

    def test_service_decides(self):
        self.assertEqual(category("Acme Towing", "PW"), PUBLIC_SAFETY)
        self.assertEqual(category("City of Seattle", "YW"), PUBLIC_SAFETY)
        self.assertEqual(category("Acme Towing", "IG"), BUSINESS)
        self.assertEqual(category("Port of Seattle", "IG"), MARINE)


class Columns(unittest.TestCase):
    def rows(self, ks):
        return [{"c": "A", "l": [49.0, -123.0 + i / 100], "f": 150000 + i, "k": k} for i, k in enumerate(ks)]

    def test_k_column(self):
        self.assertEqual(columnar(self.rows([1, 0, 6]))["k"], [1, 0, 6])

    def test_k_left_out_when_all_zero(self):
        self.assertNotIn("k", columnar(self.rows([0, 0])))

    def test_rows_keep_a_category(self):
        rows = common.Rows()
        rows.add("A", 49, -123, 150000)
        rows.add("A", 49, -123, 150000, k=PUBLIC_SAFETY)
        tile = next(iter(rows.tiles().values()))
        self.assertEqual(tile[0]["k"], PUBLIC_SAFETY)

    def test_digital_only_rows_dropped(self):
        rows = common.Rows()
        rows.add("A", 49, -123, 150000, m="dig")
        rows.add("A", 49, -123, 150000, m="nfm")  # analog listing for the same row: kept
        rows.add("B", 49, -123, 151000, m="dig")
        rows.add("C", 49, -123, 152000)  # unknown: kept
        self.assertEqual(rows.drop_digital(), 1)
        self.assertEqual(sorted(k[0] for k in rows.rows), ["A", "C"])


if __name__ == "__main__":
    unittest.main()
