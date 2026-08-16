# Swiss FakeShop Guard

Warnt auf dem iPhone vor bekannten Fake- und Dropshipping-Shops — **bevor**
bestellt wird, nicht danach.

Safari Web Extension (iOS 15+), die gegen eine täglich aktualisierte Liste
öffentlich gemeldeter Problem-Shops prüft. Datenbasis: die Warnlisten der
[Stiftung für Konsumentenschutz](https://www.konsumentenschutz.ch/online-ratgeber/dropshipping-die-stolpersteine-beim-onlinehandel-mit-billigware-aus-china/)
(~1 600 Domains) und der österreichischen
[Watchlist Internet](https://www.watchlist-internet.at/liste-betruegerischer-shops/).

**Status: Spec-Phase, kein Code.** Architektur und Datenmodell stehen in
[`SPEC.md`](SPEC.md) und sind zur Review offen.

## Wie es funktioniert

Drei Stufen statt eines binären Blocks:

- 🔴 **Block** — bestätigte Fakeshops (Ware wird nie geliefert). Seite lädt nicht.
- 🟠 **Warnung** — gelistete Dropshipping-Shops. Overlay mit Grund, Quelle und
  „Trotzdem weiter"-Option. Der Nutzer entscheidet informiert.
- 🟡 **Hinweis** — unbekannter Shop, lokale Heuristik schlägt an. Nur ein
  dezentes Badge.

Der Default für gelistete Shops ist **Warnung, nicht Block** — siehe Begründung
in [`SPEC.md` §4](SPEC.md).

## Privacy

Die Extension sendet **keine besuchte URL an irgendeinen Server**. Die Blockliste
wird heruntergeladen, der Abgleich passiert vollständig lokal auf dem Gerät.
Kein Telemetrie-Ping, kein Tracking. Der einzige Netzwerk-Request geht an die
CDN-Adresse der Liste.

## Aufbau

| Verzeichnis | Inhalt |
|---|---|
| `pipeline/` | AWS Lambda: holt die Quelllisten täglich, normalisiert, publiziert JSON nach S3/CloudFront |
| `extension/` | Safari Web Extension (MV3): Sync, Blockregeln, Warn-Overlay |
| `ios/` | Xcode-Projekt — App-Wrapper, den iOS für die Extension verlangt |
| `data/overrides.json` | Manuell gepflegte Ergänzungen, sofort wirksam ohne auf die Quellen zu warten |

## Voraussetzungen

- Mac mit Xcode (Safari Web Extensions lassen sich nur dort bauen)
- Apple Developer Program (99 $/Jahr) — auch für rein privaten Sideload, weil
  ein kostenloses Personal Team nur 7-Tage-Provisioning-Profile ausstellt
- AWS-Account für die Pipeline (Kosten im Cent-Bereich, grösstenteils Free Tier)

## Grenzen

**Nur Safari.** Chrome und Firefox auf iOS unterstützen keine Extensions — wer
dort einkauft, ist nicht geschützt. Als browserübergreifende Ergänzung ist ein
DNS-Profil vorgesehen (blockt hart, ohne Erklärung).

Weitere bekannte Grenzen in [`SPEC.md` §9](SPEC.md).

## Neue Fake-Shops melden

Wenn Sie auf einen Shop stossen, der noch nicht gelistet ist: melden Sie ihn
**direkt bei der Quelle**, nicht hier. Dort wird geprüft und publiziert, und
beim nächsten täglichen Refresh ist er automatisch auch in dieser Liste — und
hilft allen anderen mit, die die Listen nutzen.

- Schweiz: [Meldeformular Konsumentenschutz](https://findmind.ch/c/dropshipping) (anonym)
- Österreich: [Meldeformular Watchlist Internet](https://www.watchlist-internet.at/meldeformular/)

## Datenquellen

Dieses Projekt **spiegelt fremde Warnlisten und erhebt keine eigenen Vorwürfe**.
Jeder Eintrag trägt Quelle und Listendatum, und die Warnung zeigt beides an. Wir
prüfen keine Shops und entscheiden nicht über Aufnahme oder Streichung — das tun
ausschliesslich die Herausgeber der Listen.

Die Listen werden täglich neu abgeholt. Streicht eine Quelle einen Eintrag,
verschwindet er hier beim nächsten Refresh von selbst.

Details, Haftungsausschluss und der Weg für technische Fehlermeldungen:
[`NOTICE.md`](NOTICE.md).

## Lizenz

MIT für den Code. Die Listendaten gehören ihren jeweiligen Herausgebern und
sind nicht Teil dieser Lizenz.
