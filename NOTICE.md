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
und einem `User-Agent`, der auf dieses Repository und eine Kontaktadresse
verweist. Wenn Sie Herausgeber einer der Listen sind und den Abruf anders
geregelt haben möchten — oder einen strukturierten Feed anbieten können —
melden Sie sich bitte, wir stellen um.

## Keine Gewähr

- Die Liste kann veraltet, unvollständig oder fehlerhaft sein.
- Ein fehlender Eintrag ist **keine Aussage darüber, dass ein Shop
  vertrauenswürdig ist.** Die überwiegende Mehrheit problematischer Shops ist
  auf keiner Liste.
- Ein vorhandener Eintrag ist keine rechtliche Feststellung, sondern die
  Wiedergabe einer Einschätzung der genannten Quelle.
- Die Warnstufe ist immer übergehbar. Es wird niemand daran gehindert, dort zu
  kaufen.

## Sie betreiben einen gelisteten Shop?

**Bitte wenden Sie sich zuerst an die Quelle, die den Eintrag publiziert hat**
(Tabelle oben). Wir übernehmen deren Korrektur automatisch beim nächsten
täglichen Build — eine Streichung dort wirkt hier binnen 24 Stunden, ohne dass
Sie uns kontaktieren müssen.

Für Fehler, die bei **uns** entstanden sind — falsches Feld-Mapping, Tippfehler
in einer Domain, eine Verwechslung durch Domain-Normalisierung, eine falsche
Warnstufe — eröffnen Sie bitte ein Issue mit dem Template „Korrektur eines
Eintrags" oder schreiben an die Kontaktadresse unten. Wir behandeln solche
Meldungen vorrangig und nehmen einen strittigen Eintrag im Zweifel bis zur
Klärung heraus.

Kontakt: siehe Repository-Profil auf GitHub.

## Für Nutzer:innen

Eine Warnung ist ein Hinweis zum Nachdenken, keine Kaufentscheidung. Wenn Sie
bei einem gelisteten Shop schlechte Erfahrungen gemacht haben, melden Sie das
bitte direkt an die Quelle — das ist es, was diese Listen wachsen und aktuell
bleiben lässt:

- Schweiz: [Meldeformular Konsumentenschutz](https://findmind.ch/c/dropshipping)
- Irreführende Schweiz-Werbung: [SECO UWG-Beschwerde](https://www.seco.admin.ch/seco/de/home/Werbe_Geschaeftsmethoden/Unlauterer_Wettbewerb/Beschwerde_melden.html)
