"""Tests fuer Dedup, Tier-Eskalation und Overrides."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from src.merge import merge  # noqa: E402
from src.model import TIER_BLOCK, TIER_WARN, Entry  # noqa: E402


def e(domain, **kw):
    kw.setdefault("source_ids", ["sks"])
    return Entry(domain=domain, **kw)


class DedupTest(unittest.TestCase):
    def test_dedupliziert_nach_domain(self):
        out = merge([e("a.ch"), e("a.ch"), e("b.ch")])
        self.assertEqual([x.domain for x in out], ["a.ch", "b.ch"])

    def test_sortiert_nach_domain(self):
        out = merge([e("z.ch"), e("a.ch"), e("m.ch")])
        self.assertEqual([x.domain for x in out], ["a.ch", "m.ch", "z.ch"])

    def test_reasons_werden_vereinigt(self):
        out = merge([
            e("a.ch", reasons=["no_imprint"]),
            e("a.ch", reasons=["fake_reviews"]),
        ])
        self.assertEqual(out[0].reasons, ["fake_reviews", "no_imprint"])

    def test_source_ids_werden_vereinigt(self):
        out = merge([
            e("a.ch", source_ids=["sks"]),
            e("a.ch", source_ids=["wli"]),
        ])
        self.assertEqual(out[0].source_ids, ["sks", "wli"])

    def test_strengeres_tier_gewinnt(self):
        out = merge([
            e("a.ch", tier=TIER_WARN),
            e("a.ch", tier=TIER_BLOCK),
        ])
        self.assertEqual(out[0].tier, TIER_BLOCK)
        # Reihenfolge darf keine Rolle spielen.
        out = merge([
            e("b.ch", tier=TIER_BLOCK),
            e("b.ch", tier=TIER_WARN),
        ])
        self.assertEqual(out[0].tier, TIER_BLOCK)

    def test_leere_felder_werden_aus_zweitquelle_gefuellt(self):
        out = merge([
            e("a.ch", company=None, country=None),
            e("a.ch", company="Firma AG", country="CH", registry_id="CHE-1"),
        ])
        self.assertEqual(out[0].company, "Firma AG")
        self.assertEqual(out[0].country, "CH")
        self.assertEqual(out[0].registry_id, "CHE-1")

    def test_gesetzte_felder_werden_nicht_ueberschrieben(self):
        out = merge([
            e("a.ch", company="Erste AG"),
            e("a.ch", company="Zweite AG"),
        ])
        self.assertEqual(out[0].company, "Erste AG")


class BlockingReasonTest(unittest.TestCase):
    def test_no_delivery_eskaliert_auf_block(self):
        """Betrug (Ware kommt nie an) ist der einzige Grund fuer hartes
        Blocken -- SPEC Paragraph 4."""
        out = merge([e("a.ch", tier=TIER_WARN, reasons=["no_delivery"])])
        self.assertEqual(out[0].tier, TIER_BLOCK)

    def test_andere_reasons_bleiben_warn(self):
        out = merge([e("a.ch", reasons=["inflated_price", "fake_discount",
                                        "no_imprint", "low_quality"])])
        self.assertEqual(out[0].tier, TIER_WARN)

    def test_eskalation_greift_auch_nach_merge(self):
        out = merge([
            e("a.ch", reasons=["no_imprint"]),
            e("a.ch", reasons=["no_delivery"]),
        ])
        self.assertEqual(out[0].tier, TIER_BLOCK)


class OverridesTest(unittest.TestCase):
    def test_add_neuer_domain(self):
        out = merge([e("a.ch")], {"entries": [
            {"domain": "neu.ch", "action": "add", "tier": "warn",
             "reasons": ["undisclosed_dropshipping"], "added": "2026-08-16"},
        ]})
        got = {x.domain: x for x in out}
        self.assertIn("neu.ch", got)
        self.assertEqual(got["neu.ch"].source_ids, ["override"])
        self.assertEqual(got["neu.ch"].first_seen, "2026-08-16")

    def test_add_normalisiert_die_domain(self):
        out = merge([], {"entries": [
            {"domain": "https://WWW.Neu.CH/x", "action": "add"},
        ]})
        self.assertEqual(out[0].domain, "neu.ch")

    def test_remove_unterdrueckt_quelleintrag(self):
        """Der Weg, einen strittigen Eintrag sofort rauszunehmen, ohne auf die
        Quelle zu warten."""
        out = merge([e("a.ch"), e("b.ch")], {"entries": [
            {"domain": "a.ch", "action": "remove"},
        ]})
        self.assertEqual([x.domain for x in out], ["b.ch"])

    def test_remove_auf_unbekannte_domain_ist_harmlos(self):
        out = merge([e("a.ch")], {"entries": [
            {"domain": "gibtsnicht.ch", "action": "remove"},
        ]})
        self.assertEqual([x.domain for x in out], ["a.ch"])

    def test_override_eskaliert_bestehenden_eintrag(self):
        out = merge([e("a.ch", tier=TIER_WARN)], {"entries": [
            {"domain": "a.ch", "action": "add", "tier": "block"},
        ]})
        self.assertEqual(out[0].tier, TIER_BLOCK)
        self.assertIn("override", out[0].source_ids)
        self.assertIn("sks", out[0].source_ids)

    def test_override_schwaecht_nicht_ab(self):
        out = merge([e("a.ch", tier=TIER_BLOCK)], {"entries": [
            {"domain": "a.ch", "action": "add", "tier": "warn"},
        ]})
        self.assertEqual(out[0].tier, TIER_BLOCK)

    def test_ungueltige_override_eintraege_werden_uebersprungen(self):
        """Ein Tippfehler in der handgepflegten Datei darf den taeglichen
        Build nicht anhalten."""
        out = merge([e("a.ch")], {"entries": [
            {"domain": "kein-punkt", "action": "add"},
            {"domain": "x.ch", "action": "add", "tier": "quatsch"},
            {"domain": "y.ch", "action": "unbekannte-aktion"},
            {"domain": "", "action": "add"},
            {"domain": "z.ch", "action": "add", "reasons": ["erfunden"]},
        ]})
        got = {x.domain for x in out}
        self.assertEqual(got, {"a.ch", "z.ch"})
        # Der erfundene Reason wurde verworfen, der Eintrag selbst bleibt.
        self.assertEqual([x for x in out if x.domain == "z.ch"][0].reasons, [])

    def test_ohne_overrides_unveraendert(self):
        self.assertEqual(len(merge([e("a.ch")], None)), 1)
        self.assertEqual(len(merge([e("a.ch")], {})), 1)


class EntryValidationTest(unittest.TestCase):
    def test_ungueltiges_tier_wirft(self):
        with self.assertRaises(ValueError):
            Entry(domain="a.ch", tier="quatsch")

    def test_ungueltiger_reason_wirft(self):
        with self.assertRaises(ValueError):
            Entry(domain="a.ch", reasons=["erfunden"])


if __name__ == "__main__":
    unittest.main()
