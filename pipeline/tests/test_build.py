"""Tests fuer Fail-Closed-Gate und den Build-Orchestrator."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from src import build as build_mod  # noqa: E402
from src.gate import MIN_ABSOLUTE, check  # noqa: E402

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "sks_sample.html"


class GateTest(unittest.TestCase):
    def test_normaler_build_geht_durch(self):
        self.assertTrue(check(1588, 1590).ok)

    def test_kleiner_rueckgang_geht_durch(self):
        # -10% ist normale Pflege durch die Quelle.
        self.assertTrue(check(1431, 1590).ok)

    def test_grosser_rueckgang_blockt(self):
        result = check(800, 1590)
        self.assertFalse(result.ok)
        self.assertIn("49.7%", result.reason)

    def test_null_eintraege_blockt(self):
        """Der Hauptfall: Parser bricht, liefert leer, wuerde eine
        funktionierende Liste ueberschreiben."""
        result = check(0, 1590)
        self.assertFalse(result.ok)

    def test_absolutes_minimum_greift_auch_ohne_vorgaenger(self):
        """Beim allerersten Build gibt es kein published_count -- die
        Ratio-Pruefung kann dann nichts fangen."""
        result = check(5, None)
        self.assertFalse(result.ok)
        self.assertIn(str(MIN_ABSOLUTE), result.reason)

    def test_erster_build_mit_plausibler_menge_geht_durch(self):
        self.assertTrue(check(1588, None).ok)

    def test_wachstum_geht_durch(self):
        self.assertTrue(check(2000, 1590).ok)

    def test_published_count_null_wird_wie_kein_vorgaenger_behandelt(self):
        self.assertTrue(check(1588, 0).ok)


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE.read_text(encoding="utf-8")

    def build(self, overrides=None):
        return build_mod.build_blocklist(
            {"sks": self.html},
            overrides=overrides,
            generated_at="2026-08-16T04:00:00Z",
        )

    def test_struktur_und_entry_count(self):
        bl = self.build()
        self.assertEqual(bl["schema"], 1)
        self.assertEqual(bl["generated_at"], "2026-08-16T04:00:00Z")
        self.assertEqual(bl["entry_count"], len(bl["entries"]))

    def test_dedupliziert_gegenueber_rohzeilen(self):
        """Fixture hat swisstailored.ch doppelt -- nach dem Build einmal."""
        bl = self.build()
        doms = [x["domain"] for x in bl["entries"]]
        self.assertEqual(doms.count("swisstailored.ch"), 1)
        self.assertEqual(len(doms), len(set(doms)))

    def test_quellen_metadaten(self):
        src = self.build()["sources"][0]
        self.assertEqual(src["id"], "sks")
        self.assertTrue(src["url"].startswith("https://www.konsumentenschutz.ch/"))
        self.assertGreater(src["row_count"], 0)

    def test_validate_akzeptiert_echten_build(self):
        build_mod.validate(self.build())

    def test_validate_faengt_falschen_count(self):
        bl = self.build()
        bl["entry_count"] += 1
        with self.assertRaises(ValueError):
            build_mod.validate(bl)

    def test_validate_faengt_leere_liste(self):
        bl = self.build()
        bl["entries"] = []
        bl["entry_count"] = 0
        with self.assertRaises(ValueError):
            build_mod.validate(bl)

    def test_validate_faengt_doppelte_domain(self):
        bl = self.build()
        bl["entries"].append(dict(bl["entries"][0]))
        bl["entry_count"] = len(bl["entries"])
        with self.assertRaises(ValueError) as ctx:
            build_mod.validate(bl)
        self.assertIn("doppelt", str(ctx.exception))

    def test_meta_ist_klein_und_vollstaendig(self):
        bl = self.build()
        meta = build_mod.build_meta(bl)
        self.assertEqual(
            set(meta),
            {"schema", "generated_at", "entry_count", "sha256", "blocklist_path"},
        )
        self.assertEqual(len(meta["sha256"]), 64)
        self.assertEqual(meta["entry_count"], bl["entry_count"])

    def test_hash_ignoriert_generated_at(self):
        """Sonst wechselt der Hash taeglich und jeder Client laedt die Liste
        neu, obwohl sich inhaltlich nichts geaendert hat."""
        a = build_mod.build_blocklist({"sks": self.html},
                                      generated_at="2026-08-16T04:00:00Z")
        b = build_mod.build_blocklist({"sks": self.html},
                                      generated_at="2026-08-17T04:00:00Z")
        self.assertEqual(build_mod.content_hash(a), build_mod.content_hash(b))
        self.assertNotEqual(a["generated_at"], b["generated_at"])

    def test_hash_aendert_sich_bei_inhaltsaenderung(self):
        a = self.build()
        b = self.build(overrides={"entries": [
            {"domain": "zusatz.ch", "action": "add"},
        ]})
        self.assertNotEqual(build_mod.content_hash(a), build_mod.content_hash(b))

    def test_serialize_ist_deterministisch(self):
        a = build_mod.serialize(self.build())
        b = build_mod.serialize(self.build())
        self.assertEqual(a, b)

    def test_overrides_wirken_im_build(self):
        bl = self.build(overrides={"entries": [
            {"domain": "swisstailored.ch", "action": "remove"},
            {"domain": "handverdaechtig.ch", "action": "add", "tier": "block",
             "reasons": ["no_delivery"]},
        ]})
        got = {x["domain"]: x for x in bl["entries"]}
        self.assertNotIn("swisstailored.ch", got)
        self.assertEqual(got["handverdaechtig.ch"]["tier"], "block")

    def test_leere_felder_werden_weggelassen(self):
        """Bei ~1600 Einträgen sind die Null-Felder ueber 70 KB, die das
        Mobilgeraet sonst taeglich parsen und speichern muesste."""
        bl = self.build()
        ohne_firma = [e for e in bl["entries"] if "company" not in e]
        self.assertTrue(ohne_firma, "erwartet Einträge ohne company (UWG-Sentinel)")
        for entry in bl["entries"]:
            self.assertNotIn(None, entry.values())
            self.assertNotIn([], entry.values())
            # domain und tier sind immer da.
            self.assertIn("domain", entry)
            self.assertIn("tier", entry)

    def test_keine_source_url_pro_eintrag(self):
        bl = self.build()
        for entry in bl["entries"]:
            self.assertNotIn("source_url", entry)
        # Die URL haengt am sources-Block und ist ueber source_ids auflösbar.
        src_ids = {s["id"] for s in bl["sources"]}
        for entry in bl["entries"]:
            self.assertTrue(set(entry["source_ids"]) <= src_ids | {"override"})

    def test_gate_auf_echtem_build(self):
        bl = self.build()
        # Fixture ist klein -> unter MIN_ABSOLUTE, Gate muss ablehnen.
        self.assertFalse(build_mod.evaluate_gate(bl, None).ok)


if __name__ == "__main__":
    unittest.main()
