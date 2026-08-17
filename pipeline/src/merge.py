"""Zusammenfuehren von Quell-Einträgen und manuellen Overrides."""

from __future__ import annotations

from typing import Iterable, Optional

from .model import (
    BLOCKING_REASONS,
    REASONS,
    TIER_BLOCK,
    VALID_TIERS,
    Entry,
    stricter_tier,
)
from .normalize import normalize_domain

OVERRIDE_SOURCE_ID = "override"


def _fold(into: Entry, other: Entry) -> None:
    """``other`` in ``into`` einschmelzen (gleiche Domain)."""
    into.tier = stricter_tier(into.tier, other.tier)
    into.reasons = sorted(set(into.reasons) | set(other.reasons))
    into.source_ids = sorted(set(into.source_ids) | set(other.source_ids))
    # Erstes nicht-leeres Feld gewinnt -- Quellen ergaenzen sich.
    for attr in ("company", "country", "registry_id",
                 "site_status", "first_seen"):
        if getattr(into, attr) is None:
            setattr(into, attr, getattr(other, attr))


def _apply_blocking_reasons(entry: Entry) -> None:
    """Ein Betrugs-Reason hebt den Eintrag auf ``block``.

    Warum nicht generell blocken: eine eingetragene Firma, deren Shop "nur"
    ueberteuert und irrefuehrend ist, hart wegzublocken waere unverhaeltnis-
    maessig. Betrug (Ware wird nie geliefert) ist die Ausnahme.
    Siehe SPEC.md Paragraph 4.
    """
    if set(entry.reasons) & BLOCKING_REASONS:
        entry.tier = TIER_BLOCK


def merge(
    source_entries: Iterable[Entry],
    overrides: Optional[dict] = None,
) -> list:
    """Einträge deduplizieren und Overrides anwenden.

    Die SKS-Tabelle enthaelt Mehrfachnennungen derselben Domain (1602 Zeilen
    -> 1588 eindeutige Domains), deshalb ist Dedup nicht optional.

    Args:
        source_entries: Einträge aus allen Quellen, in beliebiger Reihenfolge.
        overrides: Inhalt von ``data/overrides.json`` (bereits geladen).

    Returns:
        Nach Domain sortierte, deduplizierte Liste.
    """
    by_domain = {}
    for entry in source_entries:
        existing = by_domain.get(entry.domain)
        if existing is None:
            by_domain[entry.domain] = entry
        else:
            _fold(existing, entry)

    for entry in by_domain.values():
        _apply_blocking_reasons(entry)

    if overrides:
        _apply_overrides(by_domain, overrides)

    return sorted(by_domain.values(), key=lambda e: e.domain)


def _apply_overrides(by_domain: dict, overrides: dict) -> None:
    """``data/overrides.json`` anwenden.

    Ungueltige Einträge werden uebersprungen statt geworfen: ein Tippfehler in
    der manuellen Datei soll den taeglichen Build nicht anhalten. Die
    Schema-Validierung vor dem Publish faengt echte Struktur-Fehler.
    """
    for raw in overrides.get("entries") or []:
        domain = normalize_domain(raw.get("domain", ""))
        if not domain:
            continue

        action = (raw.get("action") or "add").strip().casefold()
        if action == "remove":
            by_domain.pop(domain, None)
            continue
        if action != "add":
            continue

        tier = (raw.get("tier") or "warn").strip().casefold()
        if tier not in VALID_TIERS:
            continue
        reasons = [r for r in (raw.get("reasons") or []) if r in REASONS]

        existing = by_domain.get(domain)
        if existing is None:
            entry = Entry(
                domain=domain,
                tier=tier,
                company=raw.get("company") or None,
                country=raw.get("country") or None,
                reasons=reasons,
                source_ids=[OVERRIDE_SOURCE_ID],
                first_seen=raw.get("added") or None,
            )
            _apply_blocking_reasons(entry)
            by_domain[domain] = entry
        else:
            existing.tier = stricter_tier(existing.tier, tier)
            existing.reasons = sorted(set(existing.reasons) | set(reasons))
            existing.source_ids = sorted(
                set(existing.source_ids) | {OVERRIDE_SOURCE_ID}
            )
            _apply_blocking_reasons(existing)
