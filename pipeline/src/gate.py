"""Fail-Closed-Gate vor dem Publish.

Die Quelle ist eine WordPress-Seite mit Tabellen-Plugin. Ein Plugin-Upgrade
oder eine geaenderte Tabellen-ID bricht den Parser -- und dann wuerde er
stillschweigend 0 Einträge liefern und eine funktionierende Blockliste mit
einer leeren ueberschreiben. Der Schutz waere weg, ohne Fehler und ohne
Signal. Deshalb: im Zweifel NICHT publizieren.

Siehe SPEC.md Paragraph 5.4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

#: Faellt die Anzahl unter diesen Anteil der publizierten Liste, brechen wir ab.
#: 0.8 laesst normale Schwankungen durch (Quelle streicht Einträge), faengt
#: aber einen halb kaputten Parser.
MIN_RATIO = 0.8

#: Unter dieser Anzahl ist die Liste per se unplausibel -- die SKS-Liste lag
#: 2026-08 bei ~1590 Domains. Greift auch beim allerersten Build (kein
#: published_count vorhanden), wo MIN_RATIO nichts pruefen kann.
MIN_ABSOLUTE = 100


class GateError(Exception):
    """Publish verweigert. Die alte Liste bleibt unveraendert stehen."""


@dataclass
class GateResult:
    ok: bool
    reason: str = ""
    new_count: int = 0
    published_count: Optional[int] = None


def check(
    new_count: int,
    published_count: Optional[int] = None,
    min_ratio: float = MIN_RATIO,
    min_absolute: int = MIN_ABSOLUTE,
) -> GateResult:
    """Pruefen, ob die neue Liste publiziert werden darf.

    Args:
        new_count: Anzahl Einträge im frisch gebauten Stand.
        published_count: Anzahl im aktuell publizierten Stand; ``None`` beim
            ersten Build.

    Returns:
        :class:`GateResult` -- ``ok=False`` heisst: nicht schreiben, alarmieren.
    """
    if new_count < min_absolute:
        return GateResult(
            ok=False,
            reason=(
                f"nur {new_count} Einträge (< {min_absolute} absolutes Minimum) "
                "-- Parser liefert unplausibel wenig"
            ),
            new_count=new_count,
            published_count=published_count,
        )

    if published_count:
        threshold = published_count * min_ratio
        if new_count < threshold:
            drop = 100 * (1 - new_count / published_count)
            return GateResult(
                ok=False,
                reason=(
                    f"{new_count} Einträge vs. {published_count} publiziert "
                    f"= {drop:.1f}% Rueckgang (Limit "
                    f"{100 * (1 - min_ratio):.0f}%)"
                ),
                new_count=new_count,
                published_count=published_count,
            )

    return GateResult(
        ok=True, new_count=new_count, published_count=published_count
    )
