"""Domain-Normalisierung.

Das Matching in der Extension ist rein hostname-basiert. Alles, was hier
nicht normalisiert wird, fuehrt spaeter zu einem Treffer, der nicht greift --
oder schlimmer: zu einem Treffer auf der falschen Domain.
"""

from __future__ import annotations

import re
from typing import Optional

#: Sehr bewusst konservativ: Labels aus a-z, 0-9, Bindestrich; mindestens ein
#: Punkt; TLD mindestens zwei Buchstaben. Kein Anspruch auf PSL-Genauigkeit,
#: aber genug, um Muell aus der Quelle auszusortieren.
_DOMAIN_RE = re.compile(
    r"^(?=.{4,253}$)"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z]{2,63}$"
)

_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)


def normalize_domain(raw: str) -> Optional[str]:
    """Rohen Zellenwert in eine vergleichbare Domain ueberfuehren.

    Gibt None zurueck, wenn der Wert keine plausible Domain ist -- der Aufrufer
    zaehlt solche Zeilen als uebersprungen, statt sie zu publizieren.

    >>> normalize_domain("  WWW.Beispiel-Shop.CH/produkte?a=1 ")
    'beispiel-shop.ch'
    >>> normalize_domain("https://sub.shop.example.com.")
    'sub.shop.example.com'
    >>> normalize_domain("nicht wirklich eine domain")
    """
    if not raw:
        return None

    value = raw.strip()
    # Die Quelle setzt gelegentlich Zero-Width-Zeichen oder NBSP in die Zelle.
    value = value.replace("\u200b", "").replace("\u00a0", " ").strip()
    # Manche Zellen enthalten die Domain gefolgt von einer Anmerkung.
    value = value.split()[0] if value.split() else ""
    if not value:
        return None

    value = _SCHEME_RE.sub("", value)
    # Pfad, Query, Fragment, Port und Userinfo abschneiden.
    for sep in ("/", "?", "#"):
        value = value.split(sep, 1)[0]
    if "@" in value:
        value = value.rsplit("@", 1)[1]
    if ":" in value:
        value = value.split(":", 1)[0]

    value = value.strip().strip(".").casefold()
    if value.startswith("www."):
        value = value[4:]
    if not value:
        return None

    # IDN -> ASCII (Punycode). Schlaegt das fehl, ist es keine nutzbare Domain.
    try:
        value = value.encode("idna").decode("ascii").casefold()
    except (UnicodeError, UnicodeDecodeError):
        return None

    if not _DOMAIN_RE.match(value):
        return None
    return value


def clean_cell(raw: str) -> str:
    """Zellentext entschlacken: NBSP, Zero-Width, Mehrfach-Whitespace."""
    if not raw:
        return ""
    text = raw.replace("\u00a0", " ").replace("\u200b", "")
    return re.sub(r"\s+", " ", text).strip()
