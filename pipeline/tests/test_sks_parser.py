"""Parser-Tests gegen die eingecheckte Fixture.

Die Fixture spiegelt die real beobachtete TablePress-Struktur. Bricht einer
dieser Tests nach einem Fixture-Refresh, hat die Quelle ihr Layout geaendert --
genau das soll CI melden, bevor es der Produktions-Build tut.
"""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from src.model import SourceError  # noqa: E402
from src.sources import sks  # noqa: E402

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "sks_sample.html"


class SksParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = FIXTURE.read_text(encoding="utf-8")
        cls.entries = sks.parse(cls.html)
        cls.by_domain = {e.domain: e for e in cls.entries}

    def test_greift_die_richtige_tabelle(self):
        # tablepress-12 steht VOR der Zieltabelle und darf nicht erwischt werden.
        self.assertNotIn("falsche-tabelle.ch", self.by_domain)
        self.assertIn("swisstailored.ch", self.by_domain)

    def test_ueberspringt_zeilen_ohne_domain(self):
        for entry in self.entries:
            self.assertTrue(entry.domain)
        self.assertNotIn("", self.by_domain)

    def test_firmenname_erste_zeile_ohne_adresse(self):
        # Die Zelle enthaelt Firma + zwei Adresszeilen via <br>.
        self.assertEqual(self.by_domain["zv-nt.com"].company, "Credom")

    def test_uwg_sentinel_ist_kein_firmenname(self):
        """Der haeufigste Fallstrick: 694 von 1602 Zeilen tragen hier keinen
        Firmennamen, sondern den Impressums-Verstoss."""
        entry = self.by_domain["adamandrose-clo.com"]
        self.assertIsNone(entry.company)
        self.assertIn("no_imprint", entry.reasons)

    def test_echter_firmenname_erhaelt_kein_no_imprint(self):
        entry = self.by_domain["adams-fashion.com"]
        self.assertEqual(entry.company, "E-COM BUY-UP COMPANY LIMITED")
        self.assertNotIn("no_imprint", entry.reasons)

    def test_land_emoji_wird_gestrippt_und_gemappt(self):
        self.assertEqual(self.by_domain["swisstailored.ch"].country, "CH")
        self.assertEqual(self.by_domain["adams-fashion.com"].country, "GB")
        self.assertEqual(self.by_domain["zv-nt.com"].country, "NL")
        self.assertEqual(self.by_domain["eudorashops.com"].country, "CN")
        self.assertEqual(self.by_domain["ever-shape.nl"].country, "AT")

    def test_unbekanntes_land_wird_none_statt_fehler(self):
        self.assertIsNone(self.by_domain["adamandrose-clo.com"].country)
        # Kiribati steht nicht in der Mapping-Tabelle -> None, kein Crash.
        self.assertIsNone(self.by_domain["neuland-shop.example"].country)

    def test_domain_normalisierung(self):
        self.assertIn("gemischte-schreibweise.ch", self.by_domain)
        self.assertNotIn("WWW.Gemischte-Schreibweise.CH", self.by_domain)

    def test_idn_wird_punycode(self):
        self.assertIn("xn--bcher-beispiel-gsb.ch", self.by_domain)

    def test_status_und_registry(self):
        self.assertEqual(self.by_domain["eu.craftdlondon.com"].site_status, "online")
        self.assertEqual(self.by_domain["adams-fashion.com"].site_status, "offline")
        self.assertEqual(self.by_domain["adams-fashion.com"].registry_id, "13705169")
        self.assertIsNone(self.by_domain["eudorashops.com"].registry_id)

    def test_parser_dedupliziert_nicht_selbst(self):
        """Dedup ist Aufgabe von merge(); der Parser gibt Rohzeilen zurueck.
        Die Fixture enthaelt swisstailored.ch zweimal."""
        doms = [e.domain for e in self.entries]
        self.assertEqual(doms.count("swisstailored.ch"), 2)

    def test_alle_eintraege_tragen_quelle(self):
        """source_url steht NICHT pro Eintrag (waere 38% des Roh-JSON), sondern
        im sources-Block. Der Eintrag traegt nur die source_ids, ueber die der
        Client die URL auflöst."""
        for entry in self.entries:
            self.assertEqual(entry.source_ids, ["sks"])
        self.assertTrue(sks.SOURCE_URL.startswith("https://"))
        self.assertFalse(hasattr(self.entries[0], "source_url"))

    def test_default_tier_ist_warn(self):
        """Gelistete Shops werden gewarnt, nicht geblockt -- SPEC Paragraph 4."""
        for entry in self.entries:
            self.assertEqual(entry.tier, "warn")


class SksFailClosedTest(unittest.TestCase):
    """Strukturprobleme muessen werfen, nicht still leere Listen liefern."""

    def test_fehlende_tabelle_wirft(self):
        with self.assertRaises(SourceError) as ctx:
            sks.parse("<html><body><p>kein tablepress hier</p></body></html>")
        self.assertIn("tablepress-57", str(ctx.exception))

    def test_geaenderte_tabellen_id_wirft(self):
        html = FIXTURE.read_text(encoding="utf-8").replace(
            'id="tablepress-57"', 'id="tablepress-58"'
        )
        with self.assertRaises(SourceError):
            sks.parse(html)

    def test_fehlender_header_wirft(self):
        html = FIXTURE.read_text(encoding="utf-8").replace(
            '<th class="column-1">Website</th>',
            '<th class="column-1">URL</th>',
        )
        with self.assertRaises(SourceError) as ctx:
            sks.parse(html)
        self.assertIn("Header-Labels fehlen", str(ctx.exception))

    def test_fehlender_thead_wirft(self):
        html = FIXTURE.read_text(encoding="utf-8")
        start = html.index("<thead>", html.index('id="tablepress-57"'))
        end = html.index("</thead>", start) + len("</thead>")
        with self.assertRaises(SourceError) as ctx:
            sks.parse(html[:start] + html[end:])
        self.assertIn("thead", str(ctx.exception))

    def test_umgestellte_spalten_werden_korrekt_gelesen(self):
        """Header-basiertes Mapping statt fester Indizes: wird eine Spalte
        vorangestellt, muessen die Werte trotzdem stimmen."""
        html = FIXTURE.read_text(encoding="utf-8")
        html = html.replace(
            '<th class="column-1">Website</th>',
            '<th class="column-0">Nr</th><th class="column-1">Website</th>',
        )
        html = html.replace("\t<td>swisstailored.ch</td>",
                            "\t<td>1</td>\n\t<td>swisstailored.ch</td>", 1)
        entries = {e.domain: e for e in sks.parse(html)}
        self.assertEqual(entries["swisstailored.ch"].company, "OG Commerce GmbH")
        self.assertEqual(entries["swisstailored.ch"].country, "CH")

    def test_tabelle_ohne_datenzeilen_wirft(self):
        html = FIXTURE.read_text(encoding="utf-8")
        start = html.index('<tbody class="row-hover">')
        end = html.index("</tbody>", start) + len("</tbody>")
        broken = html[:start] + '<tbody class="row-hover"></tbody>' + html[end:]
        with self.assertRaises(SourceError) as ctx:
            sks.parse(broken)
        self.assertIn("0 verwertbare Zeilen", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
