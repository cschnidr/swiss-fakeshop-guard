"""Parser fuer die Warnliste der Stiftung fuer Konsumentenschutz (CH).

Struktur verifiziert am 2026-08-15 gegen die Live-Seite:

* TablePress Premium, Tabelle ``id="tablepress-57"``
* **vollstaendig server-seitig gerendert** -- keine Pagination, kein AJAX,
  kein JS. Ein GET liefert alle Zeilen (damals 1602 / 1588 eindeutige Domains).
* Der CSV-Button der Seite ist clientseitig (``datatables.buttons.html5``) und
  erzeugt die Datei im Browser aus der schon geladenen Tabelle. Es gibt
  **keinen** Server-Endpoint dafuer -- deshalb parsen wir das HTML.

Drei Eigenheiten, die naiv geparst falsche Daten liefern:

1. Die ``<td>`` tragen **keine** CSS-Klassen. Spalten sind rein positionell,
   deshalb leiten wir die Indizes aus dem ``<thead>`` per Header-Label ab.
   Eine eingefuegte Spalte wuerde sonst still alle Felder verschieben.
2. ``Unternehmen`` ist **ueberladen**: entweder ein Firmenname (teils
   mehrzeilig mit Adresse) *oder* der Sentinel-Satz "Keine gueltige Adresse,
   moeglicher Verstoss gegen Art. 3 Abs. 1 lit. s UWG" -- das ist kein
   Firmenname, sondern ein Grund (694 von 1602 Zeilen).
3. ``Land`` enthaelt Flag-Emoji.
"""

from __future__ import annotations

import html
import re
from typing import Optional

from ..model import (
    TIER_WARN,
    Entry,
    SourceError,
    country_to_iso,
)
from ..normalize import clean_cell, normalize_domain

SOURCE_ID = "sks"
SOURCE_NAME = "Stiftung fuer Konsumentenschutz"
SOURCE_URL = (
    "https://www.konsumentenschutz.ch/online-ratgeber/"
    "dropshipping-die-stolpersteine-beim-onlinehandel-mit-billigware-aus-china/"
)

#: Anker auf die konkrete Tabelle. Aendert sich diese ID, ist die Seite
#: umgebaut und wir brechen ab statt zu raten (Fail-Closed, SPEC Paragraph 5.4).
TABLE_ID = "tablepress-57"

#: Erwartete Header-Labels. Fehlt eines, ist die Feldzuordnung unsicher.
REQUIRED_HEADERS = ("website", "unternehmen", "land", "status")
OPTIONAL_HEADERS = ("handelsregister",)

#: Der Sentinel in der Unternehmen-Spalte. Robust gegen Umbrueche und
#: Abweichungen in der Paragraphen-Schreibweise.
_NO_IMPRINT_RE = re.compile(
    r"keine\s+g(?:ü|ue)ltige\s+adresse", re.IGNORECASE
)

_TABLE_RE_TMPL = r'<table[^>]*\bid="{tid}"[^>]*>(?P<body>.*?)</table>'
_THEAD_RE = re.compile(r"<thead[^>]*>(.*?)</thead>", re.S | re.I)
_TH_RE = re.compile(r"<th[^>]*>(.*?)</th>", re.S | re.I)
_TBODY_RE = re.compile(r"<tbody[^>]*>(.*?)</tbody>", re.S | re.I)
_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>|</p\s*>|</div\s*>", re.I)


def _cell_text(cell_html: str) -> str:
    """HTML einer Zelle in Klartext, Umbrueche als \\n erhalten."""
    text = _BR_RE.sub("\n", cell_html)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    lines = [clean_cell(line) for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def _column_map(table_html: str) -> dict:
    """Header-Labels -> Spaltenindex.

    Raises:
        SourceError: wenn kein ``<thead>`` existiert oder ein Pflicht-Header
            fehlt. Beides heisst: Layout geaendert, Zuordnung unsicher.
    """
    thead = _THEAD_RE.search(table_html)
    if not thead:
        raise SourceError(
            f"Tabelle {TABLE_ID}: kein <thead> gefunden -- "
            "Layout geaendert, Spaltenzuordnung nicht ableitbar"
        )

    labels = [
        _cell_text(th).casefold().strip()
        for th in _TH_RE.findall(thead.group(1))
    ]
    if not labels:
        raise SourceError(f"Tabelle {TABLE_ID}: <thead> enthaelt keine <th>")

    mapping = {label: idx for idx, label in enumerate(labels)}
    missing = [h for h in REQUIRED_HEADERS if h not in mapping]
    if missing:
        raise SourceError(
            f"Tabelle {TABLE_ID}: Header-Labels fehlen {missing}; "
            f"gefunden: {labels}"
        )
    return mapping


def _extract_table(page_html: str) -> str:
    pattern = re.compile(_TABLE_RE_TMPL.format(tid=re.escape(TABLE_ID)), re.S | re.I)
    match = pattern.search(page_html)
    if not match:
        raise SourceError(
            f"Tabelle id={TABLE_ID} nicht im HTML gefunden -- "
            "Seite umgebaut oder Tabelle verschoben"
        )
    return match.group("body")


def _split_company(raw: str) -> tuple:
    """Unternehmen-Zelle aufloesen.

    Returns:
        ``(company_or_None, extra_reasons)``
    """
    if not raw:
        return None, []
    if _NO_IMPRINT_RE.search(raw):
        # Kein Firmenname, sondern der UWG-Hinweis.
        return None, ["no_imprint"]
    # Erste Zeile ist der Firmenname, Folgezeilen sind die Adresse.
    company = raw.split("\n", 1)[0].strip()
    return (company or None), []


def _status(raw: str) -> Optional[str]:
    value = (raw or "").strip().casefold()
    if value in ("online", "offline"):
        return value
    return None


def parse(page_html: str) -> list:
    """Seiten-HTML -> Liste von :class:`Entry`.

    Zeilen ohne brauchbare Domain werden uebersprungen (nicht geworfen) --
    einzelne Muell-Zeilen duerfen den Build nicht kippen. Strukturprobleme
    werfen dagegen :class:`SourceError`.
    """
    table = _extract_table(page_html)
    cols = _column_map(table)

    i_domain = cols["website"]
    i_company = cols["unternehmen"]
    i_country = cols["land"]
    i_status = cols["status"]
    i_registry = cols.get("handelsregister")

    body = _TBODY_RE.search(table)
    rows_html = _TR_RE.findall(body.group(1) if body else table)

    max_idx = max(i_domain, i_company, i_country, i_status)
    entries = []

    for row_html in rows_html:
        cells = [_cell_text(td) for td in _TD_RE.findall(row_html)]
        if len(cells) <= max_idx:
            # Header-Zeile (nur <th>) oder Layout-Ausreisser.
            continue

        domain = normalize_domain(cells[i_domain])
        if not domain:
            continue

        company, reasons = _split_company(cells[i_company])
        registry = None
        if i_registry is not None and len(cells) > i_registry:
            registry = cells[i_registry].strip() or None

        entries.append(
            Entry(
                domain=domain,
                tier=TIER_WARN,
                company=company,
                country=country_to_iso(cells[i_country]),
                registry_id=registry,
                reasons=list(reasons),
                source_ids=[SOURCE_ID],
                site_status=_status(cells[i_status]),
            )
        )

    if not entries:
        raise SourceError(
            f"Tabelle {TABLE_ID} geparst, aber 0 verwertbare Zeilen -- "
            "Zeilenstruktur geaendert"
        )
    return entries
