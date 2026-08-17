# Swiss FakeShop Guard — Spec

Status: **Draft zur Review** · Autor: Christoph Schnidrig · 2026-08-15

Warnt auf dem iPhone vor bekannten Fake- und Dropshipping-Shops, bevor bestellt
wird. Basiert auf öffentlich publizierten Warnlisten (Stiftung für
Konsumentenschutz CH, Watchlist Internet AT), die täglich automatisch
aktualisiert werden.

---

## 1. Ziel / Nicht-Ziel

**Ziel**

- Nutzer sieht **beim Betreten** eines gelisteten Shops eine erklärende Warnung
  mit Grund und Quelle — nicht erst nach der Bestellung.
- Liste aktualisiert sich ohne App-Update.
- Meldeweg zurück an die Quelle ist ein Klick entfernt.
- Kein Tracking: das Gerät fragt nie „ist Domain X verdächtig" beim Server an.
  Die Liste wird geladen, der Abgleich passiert **ausschliesslich lokal**.

**Nicht-Ziel (MVP)**

- Keine Erkennung unbekannter Shops per ML/AI (das macht der österreichische
  [Fake-Shop Detector](https://github.com/mal2-project/fake-shop-detection_browser-plugin)
  schon; Heuristik nur als Tier 3, siehe §4).
- Keine Android-Version.
- Keine Abdeckung von Chrome/Firefox auf iOS — technisch unmöglich, siehe §9.
- Kein Preisvergleich, keine Produkt-Analyse.

---

## 2. Architektur

Zwei entkoppelte Komponenten, verbunden nur über ein statisches JSON:

```
  ┌─────────────────── AWS (eu-central-2, Zürich) ──────────┐
  │                                                          │
  │  EventBridge RULE (täglich 04:00 UTC)                    │
  │              │                                           │
  │              ▼                                           │
  │       Lambda "builder"  (python3.12, arm64)              │
  │         ├── fetch konsumentenschutz.ch                   │
  │         ├── merge + data/overrides.json                  │
  │         ├── FAIL-CLOSED Gate (§5.4)                      │
  │         └── put S3                                       │
  │              │                                           │
  │              ▼                                           │
  │       S3 (privat, versioned, OAC)                        │
  │         /v1/meta.json      ~183 B                        │
  │         /v1/blocklist.json ~215 KB roh / ~27 KB gzip     │
  │              │                                           │
  │              ▼                                           │
  │       CloudFront (CORS *, compress, PriceClass_100)      │
  └──────────────┬───────────────────────────────────────────┘
                 │  conditional GET, 1x/Tag
                 ▼
       Safari Web Extension (iOS 15+)
         ├── background: sync + Regelaufbau
         ├── declarativeNetRequest → tier "block"
         └── content script → tier "warn" Overlay
```

Serving ist bewusst **statisch**. Lambda läuft 1x/Tag, nicht pro
Client-Request: die Liste ändert sich täglich, wird aber von N Geräten
täglich abgefragt.

**EventBridge Rule, nicht Scheduler.** Rules gibt es seit CloudWatch Events in
jeder Region; ob EventBridge *Scheduler* in `eu-central-2` vollständig
verfügbar ist, liess sich nicht belastbar verifizieren. Für einen Trigger pro
Tag bringt Scheduler null funktionalen Vorteil — damit ist die Frage vom Tisch
statt offen.

Deploy läuft über **GitHub Actions mit OIDC** (`pipeline/bootstrap-oidc.yaml`
einmalig, dann `.github/workflows/deploy.yml`). Es liegt nirgends ein
statischer AWS-Key — bei einem öffentlichen Repo doppelt relevant, weil die
IAM-Rolle per `sub`-Bedingung auf `repo:…:ref:refs/heads/main` festgenagelt
ist und ein Fork-PR sie damit nicht annehmen kann.

---

## 3. Datenmodell

### 3.1 `/v1/meta.json` (~200 B)

Der Client pollt nur diese Datei. Nur bei geändertem `sha256` wird die grosse
Liste nachgeladen.

```json
{
  "schema": 1,
  "generated_at": "2026-08-15T04:00:12Z",
  "entry_count": 412,
  "sha256": "9f2b…",
  "blocklist_path": "/v1/blocklist.json"
}
```

### 3.2 `/v1/blocklist.json`

```json
{
  "schema": 1,
  "generated_at": "2026-08-16T04:00:12Z",
  "entry_count": 1581,
  "sources": [
    {
      "id": "sks",
      "name": "Stiftung fuer Konsumentenschutz",
      "url": "https://www.konsumentenschutz.ch/online-ratgeber/dropshipping-die-stolpersteine-beim-onlinehandel-mit-billigware-aus-china/",
      "fetched_at": "2026-08-16T04:00:03Z",
      "row_count": 1597
    }
  ],
  "entries": [
    {
      "domain": "adams-fashion.com",
      "tier": "warn",
      "company": "E-COM BUY-UP COMPANY LIMITED",
      "country": "GB",
      "registry_id": "13705169",
      "source_ids": ["sks"],
      "site_status": "offline"
    },
    {
      "domain": "adamandrose-clo.com",
      "tier": "warn",
      "reasons": ["no_imprint"],
      "source_ids": ["sks"],
      "site_status": "offline"
    }
  ]
}
```

**Designentscheide:**

- `reasons` sind **stabile Enum-Codes**, keine Fliesstexte. Die Übersetzung
  lebt in der Extension → mehrsprachig ohne Pipeline-Änderung, und die
  Wertung bleibt reproduzierbar.
  Codes: `misleading_origin`, `misleading_description`, `fake_reviews`,
  `fake_discount`, `undisclosed_dropshipping`, `no_imprint`, `no_returns`,
  `inflated_price`, `no_delivery`, `low_quality`.
- `tier` steht **in den Daten**, nicht als Logik im Client. Policy-Änderung =
  Pipeline-Deploy, kein App-Update.
- **Kein `source_url` pro Eintrag.** Die URL hängt am `sources`-Block und wird
  über `source_ids` aufgelöst. Pro Eintrag wiederholt wäre sie bei ~1600
  Einträgen allein 194 KB — 38 % des Roh-JSON. Die Warnung zeigt trotzdem
  immer, *wer* das sagt.
- **Leere Felder werden weggelassen.** Ein Eintrag ohne Firmenangabe ist fünf
  Keys statt elf. Der Client behandelt fehlende Keys als `null`/`[]`.
  Zusammen mit dem Punkt oben: **512 KB → 215 KB roh, 30 KB → 27 KB gzip.**
  Das Mobilgerät muss das täglich parsen und in `browser.storage.local` halten,
  deshalb zählt die Rohgrösse, nicht nur die übertragene.
- `site_status: offline` bleibt in der Liste — geparkte Domains werden
  reaktiviert. (Stand 2026-08-16: 1307 von 1581 `offline`.)
- `company` ist **nullable**: bei 694 Einträgen nennt die Quelle keine Firma,
  sondern nur den Impressums-Verstoss (§5.2).

---

## 4. Tier-Policy

| Tier | Datenquelle | Verhalten | Begründung |
|---|---|---|---|
| `block` | Als **Fakeshop** klassifiziert: Ware wird nie geliefert (Watchlist-Internet-Fakeshop-Liste, bzw. SKS-Einträge mit `no_delivery`) | `declarativeNetRequest` — Seite lädt nicht | Betrug. Kein legitimes Interesse des Nutzers, dort zu bestellen. |
| `warn` | SKS-Liste „problematische Dropshipping-Shops" | Overlay mit Grund + Quelle + **„Trotzdem weiter"** | Shop liefert, ist aber irreführend/überteuert. Nutzer entscheidet informiert. |
| `hint` | **Nicht in den Daten.** Rein clientseitige Heuristik auf unbekannten Shops | Kleines dezentes Badge, kein Blocken, kein Overlay | Verdacht ohne Beleg — darf nie wie eine Feststellung aussehen. |

Der Default für gelistete Shops ist **`warn`, nicht `block`**. Ein eingetragenes
Schweizer Unternehmen hart wegzublocken, dessen Shop „nur" überteuert und
irreführend ist, wäre unverhältnismässig und angreifbar. Eine Warnung mit
Quellenangabe und Weiterklick-Option ist Information.

`hint`-Heuristiken für den MVP (alle rein lokal, DOM-basiert):
kein Impressum-Link auffindbar · alle Artikel „reduziert" · Countdown-Timer,
der bei Reload neu startet · `.ch`-Domain ohne CH-Adresse im Footer.
Mindestens 2 Treffer nötig, sonst kein Badge.

---

## 5. Pipeline (Lambda `builder`)

### 5.1 Ablauf

1. Pro Quelle: ein HTTP GET, Tabelle extrahieren (§5.2).
2. Normalisieren: Domain lowercase, `www.` strippen, Punycode → ASCII,
   Pfad/Query verwerfen (Matching ist rein hostname-basiert).
3. Deduplizieren: die SKS-Tabelle enthält Mehrfachnennungen derselben Domain
   (1602 Zeilen → 1588 eindeutige Domains). Bei Duplikat: Felder mergen,
   `reasons` vereinigen, strengeres `tier` gewinnt.
4. Mergen über alle Quellen + `data/overrides.json`. Bei Konflikt gewinnt das
   **strengere** Tier. `source_ids` sammelt alle Quellen, die den Eintrag nennen.
5. Fail-Closed-Gate (§5.4).
6. `blocklist.json` + `meta.json` nach S3, CloudFront-Invalidation.

### 5.2 Quelle SKS — konkrete Struktur

Stand 2026-08-15 verifiziert. Die Seite nutzt **TablePress Premium**; die
Tabelle `id="tablepress-57"` ist **vollständig server-seitig gerendert** —
keine Pagination, kein AJAX, kein JS nötig. Ein GET liefert alle Zeilen.

> **Kein CSV-Endpoint.** Die Seite zeigt einen CSV-Button, der wird aber von
> `datatables.buttons.html5.min.js` **im Browser** aus der bereits geladenen
> Tabelle erzeugt. Es gibt keine Server-URL zum Abholen. Da das HTML ohnehin
> alle Daten enthält, ist das kein Verlust — ein Headless-Browser nur für den
> CSV-Export wäre reiner Overhead.

Kennzahlen: **1602 Datenzeilen, 1588 eindeutige Domains**, davon 280 `online`
und 1322 `offline`. Länderverteilung: Unbekannt 694, Schweiz 433,
Niederlande 194, UK 64, China 63, Hong Kong 50, USA 26, Deutschland 20.

Spalten: `Website` · `Unternehmen` · `Land` · `Handelsregister` · `Status`

**Die `<td>` tragen keine Klassen — Spalten sind rein positionell.** Deshalb:
Spaltenindizes aus dem `<thead>` per Header-Label ableiten, nicht hart
kodieren. Eine eingefügte Spalte würde sonst still alle Felder verschieben.

Zwei Eigenheiten beim Parsen:

- **`Unternehmen` ist überladen.** Die Zelle enthält *entweder* einen
  Firmennamen (teils mehrzeilig mit Adresse, z. B. `Credom\nKeizersgracht 572\n1017 EM Amsterdam`)
  *oder* den Sentinel-Satz „Keine gültige Adresse, möglicher Verstoss gegen
  Art. 3 Abs. 1 lit. s UWG" — das ist **kein Firmenname, sondern ein Grund**.
  Betrifft 694 von 1602 Zeilen. Mapping: `company = null` +
  `reasons += ["no_imprint"]`.
- **`Land` enthält Flag-Emoji** (`Schweiz 🇨🇭`, `Unbekannt 🏴‍☠️`). Emoji strippen,
  Klartext auf ISO-3166-alpha-2 mappen, `Unbekannt` → `null`.

### 5.3 Per-Source Last-Known-Good

Jede Quelle wird einzeln nach `s3://…/raw/<source_id>/latest.json` gecacht.
Fällt eine Quelle aus (HTTP-Fehler, Timeout, 0 Treffer), werden **ihre**
Einträge aus dem Cache übernommen statt weggelassen — eine kurzzeitig nicht
erreichbare Website darf nicht die halbe Blockliste löschen. Notification an
den Betreiber, aber der Build läuft durch.

### 5.4 Fail-Closed-Gate (kritisch)

Die Quelle ist eine WordPress-Seite mit Tabellen-Plugin. Ein Plugin-Upgrade oder
eine geänderte Tabellen-ID bricht den Parser, und dann liefert er stillschweigend
0 Einträge und überschreibt eine funktionierende Liste mit einer leeren — der
Schutz wäre weg, ohne Fehler und ohne Signal. Deshalb drei harte Abbruchgründe,
die klar unterschieden werden (die Diagnose ist je Fall eine andere):

| Fall | Bedeutung | Reaktion |
|---|---|---|
| Tabelle `tablepress-57` nicht gefunden | Seite umgebaut oder Tabelle verschoben | Abbruch + Alarm |
| Header-Labels weichen ab | Spalte eingefügt/umbenannt → Feldzuordnung unsicher | Abbruch + Alarm |
| `new_count < 0.8 * published_count` | Parser läuft, liefert aber zu wenig | Abbruch + Alarm |

```
→ KEIN Write nach S3
→ Alarm-Notification (SNS → konfigurierbare Email)
→ Exit non-zero (sichtbar in CloudWatch)
```

Zusätzlich: Schema-Validierung vor dem Write. Ungültiges JSON wird nie publiziert.
S3 Versioning ist an, damit ein Fehlpublish per Objekt-Version zurückrollbar ist.

### 5.5 Etikette gegenüber den Quellen

1 Request pro Quelle pro Tag, aussagekräftiger `User-Agent` mit Repo-URL und
Kontaktadresse, `If-Modified-Since`. Das ist unterhalb jeder sinnvollen
Rate-Limit-Schwelle — aber die Kontaktadresse ist der Punkt: wenn es die
Quellen stört, sollen sie uns erreichen können. Vor Go-Live der öffentlichen
Version: SKS anschreiben und fragen, ob ein Datenfeed existiert oder gewünscht
ist (schont auch unsere Pipeline vor HTML-Änderungen).

---

## 6. Extension

### 6.1 Sync (background service worker)

- `browser.alarms`, 1x/24 h + einmal bei Extension-Start.
- Conditional GET auf `meta.json` (`If-None-Match`). Bei unverändertem
  `sha256`: fertig, kein weiterer Traffic.
- Sonst `blocklist.json` laden, gegen Schema validieren, in
  `browser.storage.local` ablegen. **Bei Validierungsfehler: alte Liste behalten.**
- `declarativeNetRequest` dynamische Regeln für alle `tier: block` neu setzen.
  (Safari-Limit: 30 000 dynamische Regeln. Die Gesamtliste liegt bei ~1 600
  Domains, davon ist nur die Teilmenge `block` regelrelevant — also mindestens
  19× Luft, selbst wenn alles `block` wäre.)

### 6.2 Warnung (content script, `document_start`)

- Hostname gegen die lokale `warn`-Map prüfen (exakt + Registrable-Domain).
- Bei Treffer: Overlay in einem **Shadow DOM** (kein CSS-Leak in die Shop-Seite,
  und die Shop-Seite kann unser Overlay nicht wegstylen).
- Inhalt: Firma, Land, übersetzte `reasons`, Quelle + Listendatum,
  Buttons `Zurück` · `Trotzdem weiter` · `Melden`.
- `Melden` → Deep-Link auf das SKS-Meldeformular (findmind.ch), Domain
  vorbefüllt soweit möglich.
- `Trotzdem weiter` → Domain für 24 h in einer lokalen Allowlist, kein Re-Nag.

### 6.3 Privacy (harte Anforderung)

Die Extension macht **keinerlei** Netzwerk-Request ausser dem Liste-Download
von der eigenen CloudFront-Domain. Kein Telemetrie-Ping, keine besuchte URL
verlässt das Gerät. Das ist sowohl Vertrauensgrundlage als auch der Grund,
warum die Liste heruntergeladen statt online abgefragt wird — und es macht das
App-Store-Review erheblich einfacher.

---

## 7. Repo-Layout

```
swiss-fakeshop-guard/
├── README.md
├── SPEC.md                  ← dieses Dokument
├── LICENSE                  ← MIT (Code)
├── NOTICE.md                ← Datenquellen-Attribution + Disclaimer + Korrekturweg
├── .github/ISSUE_TEMPLATE/
│   └── correction.yml       ← Korrekturmeldung für gelistete Shop-Betreiber
├── data/
│   └── overrides.json       ← manuell gepflegt, im Repo
├── pipeline/
│   ├── src/                 ← Lambda (Python)
│   ├── template.yaml        ← SAM: Lambda + Scheduler + S3 + CloudFront
│   └── tests/
│       └── fixtures/        ← reduzierte HTML-Snapshots der Quellseiten
├── extension/
│   ├── manifest.json        ← MV3
│   ├── background.js
│   ├── content.js
│   ├── i18n/
│   └── ui/
└── ios/
    └── SwissFakeShopGuard.xcodeproj  ← App-Wrapper um die Extension
```

Die generierte Blockliste ist **nicht** im Repo (Entscheid E1) — `.gitignore`
schliesst `blocklist.json` und `meta.json` explizit aus.

Die Parser-Tests laufen gegen **eingecheckte HTML-Fixtures** der Quellseiten.
Damit merkt CI eine Layout-Änderung nicht erst im Produktions-Build — und die
Fixtures dokumentieren, worauf der Parser sich verlässt (Tabellen-ID,
Header-Labels, der Sentinel-Satz aus §5.2). Fixture-Grösse: die SKS-Seite ist
~500 KB HTML; für Tests auf ein paar Dutzend repräsentative Zeilen reduzieren
statt die ganze Seite einzuchecken.

---

## 8. Rechtliches / Attribution (relevant weil öffentlich)

Kein Rechtsrat — das sind die Punkte, die ich für abklärungswürdig halte, wenn
das Repo öffentlich wird und wächst:

- **Wir publizieren keine eigenen Vorwürfe.** Jeder Eintrag trägt Quelle und
  Listendatum; die Extension zeigt beides. Wir spiegeln, was der
  Konsumentenschutz bereits öffentlich sagt, und attribuieren es ihm.
- **Korrektur-/Takedown-Weg** muss existieren und auffindbar sein: Issue-Template
  + Kontaktadresse in `NOTICE.md`. Ein Shop-Betreiber, der zu Recht
  widerspricht, braucht einen Weg, der nicht über eine Klage führt.
- **Disclaimer**: keine Gewähr für Aktualität/Richtigkeit, keine
  Kaufempfehlung/-warnung im rechtlichen Sinn, Weiterklick immer möglich.
- Die `block`-Stufe bleibt bewusst auf Betrugsfälle beschränkt (§4).
- Falls das Projekt Traktion bekommt: einmal mit der Stiftung für
  Konsumentenschutz sprechen. Deren Segen (oder ein offizieller Feed) macht das
  Projekt belastbarer als jedes Disclaimer-Wording.

---

## 9. Bekannte Grenzen

- **Nur Safari.** Chrome/Firefox auf iOS nutzen zwar WebKit, haben aber keine
  Extension-Unterstützung. Wer primär Chrome nutzt, ist ungeschützt.
  Optionale Ergänzung: DNS-Profil (`.mobileconfig` auf einen DoH-Resolver mit
  derselben Blockliste) — browserübergreifend, aber ohne Erklärung, blockt hart.
- **Hostname-Matching.** Ein Shop, der die Domain wechselt, ist bis zur
  nächsten Listung unsichtbar. Genau dafür ist `data/overrides.json` da.
- **Kostenpflichtiger Apple-Account nötig** (99 $/Jahr), auch für rein privaten
  Sideload — ein kostenloses Personal Team stellt nur 7-Tage-Profile aus.
- **Nicht verifiziert**: der gesamte iOS-Teil ist bisher nicht gebaut. Alles in
  §6 folgt der dokumentierten API, ist aber nicht auf einem Gerät gelaufen.
  Safari-Web-Extensions lassen sich nur auf einem Mac mit Xcode bauen.

---

## 10. MVP-Scope

**In:** Pipeline (SKS-Quelle) · `block`/`warn` · Sync · Overlay · Melden-Link ·
Sideload auf ein Gerät.

**Später:** Watchlist-Internet als zweite Quelle · `hint`-Heuristiken ·
i18n FR/IT · App-Store-Release · DNS-Profil-Variante · Android/Firefox
(MV3 macht die Extension portabel — beim Schreiben mitdenken, nicht mitbauen).

---

## 11. Entscheidungen

| # | Frage | Entscheid |
|---|---|---|
| E1 | Generierte Liste ins Git-Repo, oder nur S3? | **Entschieden: nur S3** (versioniert). Das Repo bleibt Code, nicht Vorwurfs-Datenbank — sonst wäre jeder Commit ein Publikationsakt gegen namentlich genannte Firmen. Im Repo nur `overrides.json` + Fixtures. |
| E2 | Lizenz | **MIT** für Code. Daten sind nicht unsere — separat in `NOTICE.md` attribuiert, nicht mitlizenziert. |
| E3 | App Store oder nur Sideload? | **Sideload zuerst.** Review kostet Zeit und zwingt zu Support-Zusagen. Wenn's läuft und andere es wollen, dann Store. |
| E4 | Repo-Name | **Entschieden: `swiss-fakeshop-guard`** |
| E5 | Eigene Domain für die Liste? | Offen. Fürs MVP CloudFront-Default-Domain. Eigene Domain erst, wenn Dritte die Liste konsumieren (dann ist sie ein Contract). Achtung: ACM-Zertifikat müsste dann in `us-east-1` liegen, nicht in `eu-central-2`. |
| E6 | AWS-Region | **Entschieden: `eu-central-2`** (Zürich). Die lokal installierte AWS CLI (1.18.69 / botocore 1.16.19, von 2020) kennt diese Region nicht — Deploy läuft deshalb ohnehin über GitHub Actions mit aktueller Toolchain. |
| E7 | Zweite Quelle (Watchlist Internet) | Offen. Der Parser ist quellenweise gekapselt (`src/sources/`), `merge()` und das Datenmodell sind schon mehrquellenfähig (`source_ids` als Liste, Tier-Eskalation bei Konflikt). Reine Ergänzung, keine Umbaute. |
