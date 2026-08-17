"""Datenmodell der Blockliste.

Bewusst ohne externe Dependencies -- die Lambda braucht damit keinen Layer,
und die Tests laufen mit der reinen Standardbibliothek.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

SCHEMA_VERSION = 1

# --- Tiers ------------------------------------------------------------------
# "hint" ist absichtlich NICHT hier: das ist eine rein clientseitige Heuristik
# auf unbekannten Shops und darf nie wie eine belegte Feststellung aussehen.
# Siehe SPEC.md Paragraph 4.
TIER_BLOCK = "block"
TIER_WARN = "warn"

#: Reihenfolge = Strenge. Bei Duplikaten gewinnt das strengere Tier.
TIER_SEVERITY = {TIER_WARN: 1, TIER_BLOCK: 2}
VALID_TIERS = frozenset(TIER_SEVERITY)


def stricter_tier(a: str, b: str) -> str:
    """Das strengere von zwei Tiers."""
    return a if TIER_SEVERITY[a] >= TIER_SEVERITY[b] else b


# --- Reason codes -----------------------------------------------------------
# Stabile Enum-Codes, keine Fliesstexte. Die Uebersetzung lebt in der
# Extension (extension/i18n/), damit mehrsprachig ohne Pipeline-Aenderung
# moeglich ist und die Wertung reproduzierbar bleibt.
REASONS = frozenset({
    "misleading_origin",          # falsche Herkunftsangabe ("Schweizer Design")
    "misleading_description",     # irrefuehrende Produktangaben
    "fake_reviews",               # gefaelschte Bewertungen / Guetesiegel
    "fake_discount",              # Fantasie-Vergleichspreise (PBV Art. 16)
    "undisclosed_dropshipping",   # Dropshipping nicht offengelegt
    "no_imprint",                 # fehlendes/unvollstaendiges Impressum
    "no_returns",                 # Retouren nicht oder nur kostspielig moeglich
    "inflated_price",             # ueberhoehte Preise fuer AliExpress-Ware
    "no_delivery",                # Ware wird nicht geliefert -> Betrug
    "low_quality",                # minderwertige Qualitaet
})

#: Reasons, die einen Eintrag als Betrugsfall qualifizieren -> tier "block".
BLOCKING_REASONS = frozenset({"no_delivery"})


@dataclass
class Entry:
    """Ein Eintrag der Blockliste."""

    domain: str
    tier: str = TIER_WARN
    company: Optional[str] = None
    country: Optional[str] = None          # ISO-3166-alpha-2 oder None
    registry_id: Optional[str] = None
    reasons: list = field(default_factory=list)
    source_ids: list = field(default_factory=list)
    first_seen: Optional[str] = None       # ISO-Datum
    site_status: Optional[str] = None      # "online" | "offline" | None

    def __post_init__(self) -> None:
        if self.tier not in VALID_TIERS:
            raise ValueError(f"unbekanntes tier: {self.tier!r}")
        unknown = set(self.reasons) - REASONS
        if unknown:
            raise ValueError(f"unbekannte reason codes: {sorted(unknown)}")

    def to_dict(self) -> dict:
        """Kompakte Serialisierung.

        Leere Felder werden weggelassen -- bei ~1600 Einträgen sind das ueber
        70 KB, die das Mobilgeraet sonst taeglich parsen und speichern muesste.
        Der Client behandelt fehlende Keys als None/[].

        ``source_url`` steht bewusst NICHT pro Eintrag: die URL haengt am
        ``sources``-Block und wird ueber ``source_ids`` aufgeloest. Pro Eintrag
        wiederholt waere sie allein 38 % des Roh-JSON.
        """
        data = {
            "domain": self.domain,
            "tier": self.tier,
            "company": self.company,
            "country": self.country,
            "registry_id": self.registry_id,
            "reasons": sorted(self.reasons),
            "source_ids": sorted(self.source_ids),
            "first_seen": self.first_seen,
            "site_status": self.site_status,
        }
        return {k: v for k, v in data.items() if v not in (None, [], "")}


class SourceError(Exception):
    """Quelle konnte nicht verarbeitet werden -- Struktur unerwartet.

    Wird vom Fail-Closed-Gate als harter Abbruchgrund behandelt: lieber die
    alte Liste behalten als eine kaputt geparste publizieren.
    """


# --- Laendernamen -> ISO ----------------------------------------------------
# Die Quelle liefert deutsche Klartextnamen mit angehaengtem Flag-Emoji.
COUNTRY_TO_ISO = {
    "schweiz": "CH",
    "deutschland": "DE",
    "oesterreich": "AT",
    "österreich": "AT",
    "niederlande": "NL",
    "grossbritannien": "GB",
    "großbritannien": "GB",
    "vereinigtes koenigreich": "GB",
    "china": "CN",
    "hong kong": "HK",
    "hongkong": "HK",
    "usa": "US",
    "vereinigte staaten": "US",
    "zypern": "CY",
    "irland": "IE",
    "frankreich": "FR",
    "italien": "IT",
    "spanien": "ES",
    "polen": "PL",
    "tschechien": "CZ",
    "litauen": "LT",
    "lettland": "LV",
    "estland": "EE",
    "bulgarien": "BG",
    "rumaenien": "RO",
    "rumänien": "RO",
    "schweden": "SE",
    "daenemark": "DK",
    "dänemark": "DK",
    "belgien": "BE",
    "luxemburg": "LU",
    "malta": "MT",
    "singapur": "SG",
    "japan": "JP",
    "tuerkei": "TR",
    "türkei": "TR",
    "israel": "IL",
    "kanada": "CA",
    "australien": "AU",
    "indien": "IN",
    "unbekannt": None,
}

#: Emoji, Variation Selectors, ZWJ und Regional Indicators.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # Symbole, Piktogramme, Flaggen (Regional Ind.)
    "\U00002600-\U000027BF"   # Misc symbols, Dingbats
    "\U0001F1E6-\U0001F1FF"   # Regional Indicator Symbols
    "\U0000FE00-\U0000FE0F"   # Variation Selectors
    "\U0000200D"              # Zero Width Joiner
    "\U000020E3"              # Combining Enclosing Keycap
    "]+",
    flags=re.UNICODE,
)


def country_to_iso(raw: str) -> Optional[str]:
    """'Schweiz CH-Flagge' -> 'CH'; 'Unbekannt Piratenflagge' -> None.

    Unbekannte Laendernamen geben None zurueck statt zu werfen: ein neues Land
    in der Quelle darf den Build nicht kippen, das Feld ist rein informativ.
    """
    cleaned = _EMOJI_RE.sub("", raw or "").strip()
    if not cleaned:
        return None
    return COUNTRY_TO_ISO.get(cleaned.casefold())
