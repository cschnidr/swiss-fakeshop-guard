"""Tests fuer Domain-Normalisierung und Laender-Mapping."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from src.model import country_to_iso  # noqa: E402
from src.normalize import clean_cell, normalize_domain  # noqa: E402


class NormalizeDomainTest(unittest.TestCase):
    def test_kleinschreibung_und_trim(self):
        self.assertEqual(normalize_domain("  Beispiel-Shop.CH "), "beispiel-shop.ch")

    def test_www_prefix_weg(self):
        self.assertEqual(normalize_domain("www.shop.ch"), "shop.ch")

    def test_subdomain_bleibt(self):
        self.assertEqual(normalize_domain("eu.craftdlondon.com"), "eu.craftdlondon.com")

    def test_schema_pfad_query_fragment_weg(self):
        for raw in (
            "https://shop.ch/produkte",
            "http://shop.ch?a=1",
            "shop.ch#anker",
            "HTTPS://SHOP.CH/",
        ):
            self.assertEqual(normalize_domain(raw), "shop.ch", raw)

    def test_port_und_userinfo_weg(self):
        self.assertEqual(normalize_domain("shop.ch:8443"), "shop.ch")
        self.assertEqual(normalize_domain("user:pw@shop.ch"), "shop.ch")

    def test_trailing_dot_weg(self):
        self.assertEqual(normalize_domain("shop.ch."), "shop.ch")

    def test_nbsp_und_zero_width(self):
        self.assertEqual(normalize_domain("\u00a0shop.ch\u200b"), "shop.ch")

    def test_idn_zu_punycode(self):
        self.assertEqual(normalize_domain("bücher.ch"), "xn--bcher-kva.ch")

    def test_domain_mit_anmerkung_nimmt_ersten_token(self):
        self.assertEqual(normalize_domain("shop.ch (offline)"), "shop.ch")

    def test_muell_gibt_none(self):
        for raw in ("", "   ", "kein punkt", "nicht wirklich eine domain",
                    ".ch", "shop.", "-shop.ch", "shop.c", "@@@"):
            self.assertIsNone(normalize_domain(raw), repr(raw))

    def test_none_safe(self):
        self.assertIsNone(normalize_domain(None))


class CountryTest(unittest.TestCase):
    def test_emoji_wird_gestrippt(self):
        self.assertEqual(country_to_iso("Schweiz 🇨🇭"), "CH")
        self.assertEqual(country_to_iso("Niederlande 🇳🇱"), "NL")

    def test_zwj_piratenflagge(self):
        self.assertIsNone(country_to_iso("Unbekannt 🏴\u200d☠️"))

    def test_umlaut_varianten(self):
        self.assertEqual(country_to_iso("Österreich 🇦🇹"), "AT")
        self.assertEqual(country_to_iso("Oesterreich"), "AT")

    def test_unbekanntes_land_gibt_none(self):
        self.assertIsNone(country_to_iso("Kiribati 🇰🇮"))

    def test_leer_gibt_none(self):
        self.assertIsNone(country_to_iso(""))
        self.assertIsNone(country_to_iso(None))


class CleanCellTest(unittest.TestCase):
    def test_mehrfach_whitespace(self):
        self.assertEqual(clean_cell("a   b\t\tc"), "a b c")

    def test_nbsp(self):
        self.assertEqual(clean_cell("a\u00a0b"), "a b")


if __name__ == "__main__":
    unittest.main()
