# Pipeline

Baut die Blockliste aus den Warnlisten und publiziert sie als statisches JSON.

## Ausführen

Keine Dependencies — der Code nutzt ausschliesslich die Standardbibliothek.

```bash
cd pipeline
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Gegen die Live-Quelle prüfen, ohne AWS:

```bash
cd pipeline
python3 - <<'PY'
import sys, urllib.request
sys.path.insert(0, '.')
from src import build as build_mod
from src.sources import sks
req = urllib.request.Request(sks.SOURCE_URL, headers={"User-Agent": "swiss-fakeshop-guard/1.0 local"})
html = urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "replace")
bl = build_mod.build_blocklist({"sks": html})
build_mod.validate(bl)
print(bl["entry_count"], "Einträge,", len(build_mod.serialize(bl)), "B")
print(build_mod.build_meta(bl))
PY
```

## Aufbau

| Datei | Rolle |
|---|---|
| `src/model.py` | `Entry`, Tiers, Reason-Codes, Länder-Mapping |
| `src/normalize.py` | Domain-Normalisierung (der Teil, der Fehltreffer verhindert) |
| `src/sources/sks.py` | Parser für konsumentenschutz.ch |
| `src/merge.py` | Dedup, Tier-Eskalation, Overrides |
| `src/gate.py` | Fail-Closed-Prüfung vor dem Publish |
| `src/build.py` | Orchestrierung — **kein AWS**, deshalb ohne Mocks testbar |
| `src/handler.py` | Lambda-Entry, alles I/O-Behaftete, `boto3` lazy importiert |

Die Trennung `build.py` / `handler.py` ist der Grund, warum die Tests ohne
AWS-SDK und ohne Mocking-Framework laufen.

## Deploy

Läuft über GitHub Actions mit OIDC — es liegt nirgends ein statischer AWS-Key.

**Einmalig**, mit Admin-Rechten:

```bash
aws cloudformation deploy \
  --template-file pipeline/bootstrap-oidc.yaml \
  --stack-name swiss-fakeshop-guard-oidc \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-central-2 \
  --parameter-overrides GitHubRepo=cschnidr/swiss-fakeshop-guard
```

Den Output `RoleArn` als Repository-**Variable** `AWS_DEPLOY_ROLE_ARN`
eintragen (Settings → Secrets and variables → Actions → Variables). Kein
Secret nötig: ohne den OIDC-Trust ist der ARN wertlos.

Danach deployt jeder Push auf `main`, der `pipeline/**` berührt. Manuell:
Actions → Deploy → Run workflow (optional mit `run_after_deploy`, um sofort
einen Build-Lauf auszulösen).

Optional beim Deploy: `AlarmEmail` als Parameter setzen, dann gehen
Fail-Closed-Alarme per SNS an diese Adresse.

## Was schiefgehen kann

Die Quelle ist eine WordPress-Seite mit Tabellen-Plugin. Bricht deren Layout,
liefert ein naiver Parser still 0 Einträge und überschreibt eine
funktionierende Blockliste mit einer leeren — Schutz weg, ohne Fehler, ohne
Signal. Dagegen drei Abbruchgründe (`src/gate.py`, `src/sources/sks.py`):

- Tabelle `tablepress-57` nicht gefunden
- Header-Labels weichen ab (Spaltenzuordnung unsicher)
- Anzahl fällt unter 80 % des publizierten Stands, oder unter 100 absolut

In jedem Fall: **kein Write nach S3**, SNS-Alarm, Lauf endet mit Fehler. Die
bisherige Liste bleibt ausgeliefert.

Fällt die Quelle nur kurzzeitig aus (HTTP-Fehler, Timeout), greift der
Last-Known-Good-Cache unter `s3://<bucket>/raw/<source_id>/latest.html` —
eine nicht erreichbare Website darf nicht die halbe Liste löschen.

## Fixture aktualisieren

`tests/fixtures/sks_sample.html` ist ein **handkuratierter** Auszug, nicht ein
Dump. Sie enthält bewusst je einen Fall für: UWG-Sentinel statt Firmenname,
mehrzeilige Firma mit Adresse, Flag-Emoji, unbekanntes Land, IDN-Domain,
Zeile ohne Domain, doppelte Domain, sowie eine Störtabelle mit anderer ID.

Ändert die Quelle ihr Layout, die neue Struktur übernehmen und die
Sonderfälle beibehalten — sie sind der Grund, warum die Tests etwas aussagen.
Zum Vergleich das Live-HTML holen:

```bash
curl -sL -A "swiss-fakeshop-guard/1.0 (fixture refresh)" \
  "https://www.konsumentenschutz.ch/online-ratgeber/dropshipping-die-stolpersteine-beim-onlinehandel-mit-billigware-aus-china/" \
  | grep -o '<table id="tablepress-57".*</table>' | head -c 4000
```
