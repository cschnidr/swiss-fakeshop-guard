"""Lambda-Handler: alles I/O-Behaftete.

Trennung zu ``build.py`` ist Absicht -- hier liegt der ``boto3``-Kram, dort
die testbare Logik. ``boto3`` wird lazy importiert, damit die Tests ohne
AWS-SDK laufen.

Ablauf pro Lauf:

1. Quellen holen (mit Last-Known-Good-Cache, SPEC Paragraph 5.3)
2. Overrides aus dem Repo-Snapshot im Bundle lesen
3. Blockliste bauen
4. Fail-Closed-Gate (SPEC Paragraph 5.4)
5. Bei OK: nach S3 schreiben + CloudFront invalidieren
   Bei NICHT-OK: nichts schreiben, SNS-Alarm, non-zero raise
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import urllib.error
import urllib.request

from . import build as build_mod
from .model import SourceError
from .sources import sks

log = logging.getLogger()
log.setLevel(logging.INFO)

USER_AGENT = (
    "swiss-fakeshop-guard/1.0 "
    "(+https://github.com/cschnidr/swiss-fakeshop-guard) "
    "1 request/day"
)
FETCH_TIMEOUT = 60

BUCKET = os.environ.get("BUCKET_NAME", "")
DISTRIBUTION_ID = os.environ.get("DISTRIBUTION_ID", "")
ALARM_TOPIC_ARN = os.environ.get("ALARM_TOPIC_ARN", "")

KEY_BLOCKLIST = "v1/blocklist.json"
KEY_META = "v1/meta.json"
KEY_RAW_TMPL = "raw/{source_id}/latest.html"

#: Pfad zu data/overrides.json IM BUNDLE. Der Deploy-Workflow kopiert die
#: Datei aus dem Repo-Root nach pipeline/data/, bevor `sam build` laeuft --
#: dadurch liegt sie in der Lambda unter /var/task/data/overrides.json.
_OVERRIDES_PATH = pathlib.Path(
    os.environ.get(
        "OVERRIDES_PATH",
        pathlib.Path(__file__).resolve().parents[1] / "data" / "overrides.json",
    )
)


def _s3():
    import boto3  # lazy: nicht in den Tests gebraucht
    return boto3.client("s3")


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "de-CH,de;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _get_source_html(source_id: str, url: str) -> tuple:
    """Quelle holen; bei Fehlschlag Last-Known-Good aus S3.

    Eine kurzzeitig nicht erreichbare Website darf nicht die halbe Blockliste
    loeschen (SPEC Paragraph 5.3).

    Returns:
        ``(html, used_cache: bool)``
    """
    try:
        html_text = _fetch(url)
        if BUCKET:
            try:
                _s3().put_object(
                    Bucket=BUCKET,
                    Key=KEY_RAW_TMPL.format(source_id=source_id),
                    Body=html_text.encode("utf-8"),
                    ContentType="text/html; charset=utf-8",
                )
            except Exception:  # noqa: BLE001 -- Cache-Write ist best effort
                log.warning("LKG-Cache fuer %s nicht geschrieben", source_id,
                            exc_info=True)
        return html_text, False
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("Quelle %s nicht erreichbar (%s) -- versuche LKG-Cache",
                    source_id, exc)
        if not BUCKET:
            raise
        obj = _s3().get_object(
            Bucket=BUCKET, Key=KEY_RAW_TMPL.format(source_id=source_id)
        )
        return obj["Body"].read().decode("utf-8", errors="replace"), True


def _published_count() -> "int | None":
    """entry_count des aktuell publizierten Stands, oder None beim ersten Lauf."""
    if not BUCKET:
        return None
    try:
        obj = _s3().get_object(Bucket=BUCKET, Key=KEY_META)
        return int(json.loads(obj["Body"].read())["entry_count"])
    except Exception:  # noqa: BLE001 -- kein meta.json = erster Lauf
        log.info("kein publiziertes meta.json -- erster Lauf")
        return None


def _load_overrides() -> dict:
    try:
        return json.loads(_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        log.info("keine overrides.json im Bundle")
        return {}
    except json.JSONDecodeError:
        log.warning("overrides.json ist kein gueltiges JSON -- ignoriert",
                    exc_info=True)
        return {}


def _alarm(subject: str, message: str) -> None:
    log.error("%s: %s", subject, message)
    if not ALARM_TOPIC_ARN:
        return
    try:
        import boto3
        boto3.client("sns").publish(
            TopicArn=ALARM_TOPIC_ARN,
            Subject=subject[:100],
            Message=message,
        )
    except Exception:  # noqa: BLE001 -- Alarm darf den Raise nicht verschlucken
        log.exception("SNS-Alarm konnte nicht gesendet werden")


def _publish(blocklist: dict, meta: dict) -> None:
    s3 = _s3()
    # Blockliste zuerst, meta.json danach: der Client pollt meta und darf
    # nie einen Hash sehen, zu dem die Liste noch nicht da ist.
    s3.put_object(
        Bucket=BUCKET,
        Key=KEY_BLOCKLIST,
        Body=build_mod.serialize(blocklist).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
        CacheControl="public, max-age=3600",
    )
    s3.put_object(
        Bucket=BUCKET,
        Key=KEY_META,
        Body=json.dumps(meta, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
        CacheControl="public, max-age=300",
    )
    if DISTRIBUTION_ID:
        import boto3
        boto3.client("cloudfront").create_invalidation(
            DistributionId=DISTRIBUTION_ID,
            InvalidationBatch={
                "Paths": {"Quantity": 2,
                          "Items": [f"/{KEY_META}", f"/{KEY_BLOCKLIST}"]},
                "CallerReference": meta["generated_at"],
            },
        )


def handler(event=None, context=None) -> dict:  # noqa: ARG001
    """EventBridge-Ziel. Wirft bei Gate-Ablehnung, damit der Lauf in
    CloudWatch als Fehler sichtbar ist."""
    try:
        html_text, used_cache = _get_source_html(sks.SOURCE_ID, sks.SOURCE_URL)
    except Exception as exc:  # noqa: BLE001
        _alarm("swiss-fakeshop-guard: Quelle nicht verfuegbar",
               f"SKS konnte weder geladen noch aus dem Cache gelesen werden: {exc}")
        raise

    try:
        blocklist = build_mod.build_blocklist(
            {"sks": html_text}, overrides=_load_overrides()
        )
        build_mod.validate(blocklist)
    except (SourceError, ValueError) as exc:
        _alarm("swiss-fakeshop-guard: Build abgebrochen (Struktur)", str(exc))
        raise

    result = build_mod.evaluate_gate(blocklist, _published_count())
    if not result.ok:
        _alarm("swiss-fakeshop-guard: Publish verweigert (Fail-Closed)",
               f"{result.reason}\n\nDie bisherige Liste bleibt unveraendert.")
        raise RuntimeError(f"Fail-Closed-Gate: {result.reason}")

    meta = build_mod.build_meta(blocklist)
    _publish(blocklist, meta)

    log.info("publiziert: %s Einträge, sha256=%s, cache=%s",
             blocklist["entry_count"], meta["sha256"][:12], used_cache)
    return {
        "entry_count": blocklist["entry_count"],
        "sha256": meta["sha256"],
        "used_lkg_cache": used_cache,
    }
