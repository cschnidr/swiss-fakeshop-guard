# Datenquellen, Haftung und Korrekturen

## Was dieses Projekt tut — und was nicht

Dieses Projekt **erhebt keine eigenen Vorwürfe gegen Unternehmen.** Es spiegelt
Warnlisten, die Dritte bereits öffentlich publizieren, und macht sie auf dem
iPhone zum Zeitpunkt des Ladens eines Shops sichtbar.

Jeder Eintrag trägt die Quelle und das Datum, an dem diese Quelle ihn gelistet
hat. Die Warnung im Browser zeigt beides an. Die Wertung („irreführend",
„gefälschte Bewertungen", „kein Impressum") ist immer die Wertung der jeweiligen
Quelle, nicht unsere.

## Quellen

| ID | Herausgeber | Liste |
|---|---|---|
| `sks` | Stiftung für Konsumentenschutz (Bern, CH) | [Problematische Dropshipping-Shops](https://www.konsumentenschutz.ch/online-ratgeber/dropshipping-die-stolpersteine-beim-onlinehandel-mit-billigware-aus-china/) |
| `wli` | Österreichisches Institut für angewandte Telekommunikation | [Liste betrügerischer Online-Shops](https://www.watchlist-internet.at/liste-betruegerischer-shops/) |

Die Listendaten gehören ihren jeweiligen Herausgebern und stehen **nicht** unter
der MIT-Lizenz dieses Repositorys. Die MIT-Lizenz deckt ausschliesslich den
Code.

Abrufverhalten: ein HTTP-Request pro Quelle pro Tag, mit `If-Modified-Since`
und einem `User-Agent`, der auf dieses Repository verweist. Das ist unterhalb
jeder sinnvollen Rate-Limit-Schwelle und greift ausschliesslich öffentlich
zugängliche Seiten ab.

Sind Sie Herausgeber einer der Listen und möchten den Abruf anders geregelt
haben — oder können einen strukturierten Feed anbieten? Dann eröffnen Sie bitte
ein Issue; ein offizieller Feed wäre für beide Seiten robuster als das Abgreifen
von HTML.

## Neue Fake- oder Dropshipping-Shops melden

Diese Listen leben davon, dass Betroffene melden. Wenn Sie auf einen Shop
gestossen sind, der hier fehlt, melden Sie ihn **direkt bei der Quelle** — dort
wird geprüft und publiziert, und beim nächsten täglichen Refresh ist er
automatisch auch hier drin:

- **Schweiz — Dropshipping / problematische Shops:**
  [Meldeformular Konsumentenschutz](https://findmind.ch/c/dropshipping)
  (anonym, dauert Sekunden)
- **Österreich — betrügerische Shops:**
  [Meldeformular Watchlist Internet](https://www.watchlist-internet.at/fake-shop-melden/)
- **Irreführende Schweiz-Werbung (UWG):** über das SECO — Einstieg via
  [seco.admin.ch](https://www.seco.admin.ch/) unter „Werbe- und
  Geschäftsmethoden" (Deeplink hier absichtlich nicht gesetzt, das SECO
  verschiebt die Seite regelmässig)

Meldungen an dieses Repository ergänzen die Listen **nicht** — wir führen keine
eigene Liste und prüfen keine Shops. Der Weg über die Quelle ist der einzige,
der wirkt, und er hilft allen anderen Nutzer:innen der Listen mit.

## Keine Gewähr

- Die Liste kann veraltet, unvollständig oder fehlerhaft sein.
- Ein fehlender Eintrag ist **keine Aussage darüber, dass ein Shop
  vertrauenswürdig ist.** Die überwiegende Mehrheit problematischer Shops ist
  auf keiner Liste.
- Ein vorhandener Eintrag ist keine rechtliche Feststellung, sondern die
  Wiedergabe einer Einschätzung der genannten Quelle.
- Die Warnstufe ist immer übergehbar. Es wird niemand daran gehindert, dort zu
  kaufen.
- Dies ist ein unbezahltes Freizeitprojekt ohne Support, ohne Verfügbarkeits-
  garantie und ohne zugesagte Reaktionszeiten.

## Sie betreiben einen gelisteten Shop?

**Zuständig ist die Quelle, die den Eintrag publiziert hat** (Tabelle oben) —
nicht dieses Projekt. Wir treffen keine Einschätzung über Ihren Shop, prüfen
keine Einträge und entscheiden nicht über Aufnahme oder Streichung.

Die Listen werden **täglich neu abgeholt**, wie oben beschrieben. Sobald die
Quelle Ihren Eintrag streicht oder ändert, verschwindet bzw. ändert er sich hier
beim nächsten Refresh von selbst. Sie müssen uns dafür nicht kontaktieren, und
wir können Ihnen umgekehrt auch nicht helfen, solange der Eintrag bei der Quelle
steht.

Für rein **technische** Fehler in diesem Projekt — eine falsch geparste Domain,
ein Feld-Mapping, das eine Quelle unzutreffend wiedergibt — können Sie ein Issue
eröffnen (Template „Korrektur eines Eintrags"). Das ist ein Bug-Report an ein
Freizeitprojekt, keine Beschwerdestelle: es gibt keine zugesagte Bearbeitungs-
oder Reaktionszeit.

## Für Nutzer:innen

Eine Warnung ist ein Hinweis zum Nachdenken, keine Kaufentscheidung — und ein
fehlender Eintrag ist kein Gütesiegel. Wenn Sie bei einem gelisteten oder noch
nicht gelisteten Shop schlechte Erfahrungen gemacht haben: melden Sie das bei
der Quelle (Links oben). Das ist es, was diese Listen wachsen und aktuell
bleiben lässt.
