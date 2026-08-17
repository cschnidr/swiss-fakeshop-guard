"""Build der Blockliste -- reine Logik, kein AWS.

Bewusst frei von ``boto3``: so laufen die Tests ohne AWS-SDK, und die
Geschaeftslogik ist ohne Mocks pruefbar. Alles I/O-Behaftete liegt in
``handler.py``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional

from .gate import GateResult, check as gate_check
from .merge import merge
from .model import SCHEMA_VERSION, Entry
from .sources import sks


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_blocklist(
    sources: dict,
    overrides: Optional[dict] = None,
    generated_at: Optional[str] = None,
) -> dict:
    """Quell-HTML -> blocklist.json (als dict).

    Args:
        sources: ``{"sks": "<html>...", ...}`` -- Roh-HTML pro Quelle.
        overrides: Inhalt von ``data/overrides.json``.
        generated_at: Zeitstempel; Default ist jetzt (fuer Tests injizierbar).

    Raises:
        SourceError: wenn eine Quelle strukturell unerwartet ist.
    """
    timestamp = generated_at or _now_iso()
    all_entries = []
    source_meta = []

    if "sks" in sources:
        entries = sks.parse(sources["sks"])
        all_entries.extend(entries)
        source_meta.append({
            "id": sks.SOURCE_ID,
            "name": sks.SOURCE_NAME,
            "url": sks.SOURCE_URL,
            "fetched_at": timestamp,
            "row_count": len(entries),
        })

    merged = merge(all_entries, overrides)

    return {
        "schema": SCHEMA_VERSION,
        "generated_at": timestamp,
        "entry_count": len(merged),
        "sources": source_meta,
        "entries": [e.to_dict() for e in merged],
    }


def serialize(blocklist: dict) -> str:
    """Kanonisches JSON -- stabil sortiert, damit der Hash nur bei echten
    Inhaltsaenderungen wechselt."""
    return json.dumps(
        blocklist, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def content_hash(blocklist: dict) -> str:
    """SHA-256 ueber die *Inhalte*, ohne ``generated_at``.

    Sonst wechselt der Hash bei jedem Build und die Clients laden die Liste
    jeden Tag neu, obwohl sich nichts geaendert hat.
    """
    stable = {k: v for k, v in blocklist.items() if k != "generated_at"}
    stable["sources"] = [
        {k: v for k, v in s.items() if k != "fetched_at"}
        for s in blocklist.get("sources", [])
    ]
    payload = json.dumps(
        stable, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_meta(blocklist: dict, blocklist_path: str = "/v1/blocklist.json") -> dict:
    """Die kleine Datei, die der Client taeglich pollt (~200 B)."""
    return {
        "schema": SCHEMA_VERSION,
        "generated_at": blocklist["generated_at"],
        "entry_count": blocklist["entry_count"],
        "sha256": content_hash(blocklist),
        "blocklist_path": blocklist_path,
    }


def validate(blocklist: dict) -> None:
    """Minimale Schema-Pruefung vor dem Publish.

    Kein jsonschema -- das waere eine Dependency fuer eine Struktur, die wir
    selbst erzeugen. Geprueft wird, was ein Client voraussetzt.
    """
    if blocklist.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"schema != {SCHEMA_VERSION}")
    entries = blocklist.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("entries fehlt oder ist leer")
    if blocklist.get("entry_count") != len(entries):
        raise ValueError(
            f"entry_count {blocklist.get('entry_count')} != "
            f"len(entries) {len(entries)}"
        )
    seen = set()
    for entry in entries:
        domain = entry.get("domain")
        if not domain:
            raise ValueError("Eintrag ohne domain")
        if domain in seen:
            raise ValueError(f"Domain doppelt nach Merge: {domain}")
        seen.add(domain)
        if entry.get("tier") not in ("block", "warn"):
            raise ValueError(f"{domain}: ungueltiges tier {entry.get('tier')!r}")


def evaluate_gate(blocklist: dict, published_count: Optional[int]) -> GateResult:
    return gate_check(blocklist["entry_count"], published_count)


__all__ = [
    "build_blocklist",
    "build_meta",
    "content_hash",
    "evaluate_gate",
    "serialize",
    "validate",
    "Entry",
]
