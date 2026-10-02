# Architektur

Diese Datei ist der Vertrag zwischen den Schritten. Wer einen Schritt ändert,
hält sich an die Formate hier; wer ein Format ändert, ändert es hier zuerst.

## Grundsatz

- **Urteil gegen Code.** Was gesagt wird, wo geschnitten wird, welcher Satz
  vorn steht, welcher Text unter dem Beitrag steht: das entscheidet ein Modell,
  immer über `pipeline/urteil.py`. Zeiten, Maße, Dateien, Sendeplätze, Grenzen:
  das ist Code.
- **Nie still scheitern.** Jeder Schritt liefert `Ergebnis(status, meldung)`
  mit `status` aus `ok`, `befund`, `fehler`, `nichts`. Ein Befund stoppt das
  Stück nicht, er steht sichtbar am Stück. Der Tageslauf fängt jeden Schritt
  einzeln ab.
- **Pixel statt Zeichen.** Ob Text passt, wird am gerenderten Text gemessen
  (`pipeline/schrift.py`), nie an der Zeichenzahl.
- **Schrift im Bild über Pillow.** Das Homebrew-ffmpeg hat kein drawtext und
  kein libass. Jeder Text im Video ist ein PNG, das ffmpeg darüberlegt.
- **Trocken ist Standard.** `posten` sendet nur mit `--echt`, und nur
  freigegebene Einträge.

## Ordner zur Laufzeit

```
eingang/                       Rohvideos, die neu hereinkommen (mov, mp4, m4v)
arbeit/<take>/take.json        {"id","quelle","dauer_s","eingang_am","status"}
arbeit/<take>/quelle.<ext>     das Rohvideo, verschoben aus eingang/
arbeit/<take>/audio.wav        16 kHz mono, für Whisper
arbeit/<take>/woerter.json     [{"w": "Heute", "s": 0.52, "e": 0.81}, …]  Quellzeit in s
arbeit/<take>/transkript.txt   Fließtext
arbeit/<take>/saetze.json      [{"nr","von_wort","bis_wort","s","e","text"}]
arbeit/<take>/reste.json       [{"text","s","e","grund"}]  Sätze mit Aussage, zu kurz fürs Reel
arbeit/<take>/stuecke/<nn>/rezept.json   siehe unten
arbeit/plan.json               siehe unten
arbeit/postlog.json            siehe unten
arbeit/urteile.jsonl           jedes Modellurteil, eine Zeile je Aufruf
arbeit/cache/urteile/<hash>.json   Zwischenspeicher, 7 Tage
arbeit/logs/<datum>.log        Protokoll je Tag
arbeit/ki_budget.json          KI-Buchungen des Monats und Deckelstatus
arbeit/ki_rotation.json        Zähler für die Wahl der KI-Einblendung
arbeit/eingang_beobachtet.json Größe, Änderungszeit und Beobachtungsbeginn je zusätzlicher Eingangsdatei
ausgabe/<stueck_id>/           fertige Dateien je Stück, siehe unten
ausgabe/bilder/<bild_id>/      fertige Bildbeiträge, siehe unten
medien/hintergruende/          eigene Fotos für Pinterest-Stile mit Foto (optional)
```

`stueck_id` = `<take>-<nn>`, z. B. `beispiel-01`.
Zusatzstücke heißen `<take>-lese` und `<take>-uebermalt`; ihr `stueck.json`
trägt zusätzlich `"stil": "lesereel"` beziehungsweise `"uebermalt"`.
Das Lese-Reel erhält sein Thema aus `titel` und `aussage` der Rezepte eines
Takes. Beide Zusatzstücke lassen im selben Modellurteil eine kurze Caption
erzeugen, die mit einer Frage endet.
`[kurzstuecke].vorrat_hoechstens` begrenzt den ungeposteten Vorrat je Stil;
eine erfolgreiche Zeile in `postlog.json` zählt dabei als veröffentlicht.
`abstand_tage` hält beim Planen und Vorziehen je Kanal den Kalenderabstand
zwischen Lese-Reels beziehungsweise übermalten Sätzen ein.
Aufgenommene fertige Videos heißen `U01`, `U02` für Umbauten und `W01`, `W02`
für Werbeclips. Ihr Rezept liegt unter `arbeit/<id>/stuecke/01/`, ihr Manifest
trägt `"stil": "umbau"` beziehungsweise `"werbeclip"`.

Weitere Eingangsordner stehen als `weitere_ordner` unter `[eingang]` in
`konfig/pipeline.toml`. Der Eingang übernimmt daraus nur fertige Video-Dateien,
deren Größe und Änderungszeit mindestens 180 Sekunden unverändert beobachtet
wurden. Er kopiert sie erst mit einer Teil-Datei nach `eingang/` und verschiebt das Original
anschließend nach `übernommen/` im Quellordner. In `zeitachse.json` steht nach
dem Rohschnitt zusätzlich `wortanfang_korrigiert`, die Zahl der am Toneinsatz
nachgezogenen Wortanfänge.

## rezept.json (ein Stück aus einem Take)

```json
{
  "id": "beispiel-01", "take": "beispiel", "nr": 1, "von_stuecken": 3,
  "von_satz": 0, "bis_satz": 7, "s": 0.52, "e": 58.3,
  "titel": "Kurzer Titel, zwei Zeilen erlaubt mit \n",
  "aussage": "Ein Satz, was das Stück sagt",
  "hook": {"von_satz": 5, "punkte": 8, "einstieg_punkte": 3, "grund": "…"} ,
  "stil": {"reel": "klar", "tiktok": "klar", "youtube": "klar"},
  "schluss": "Text der Schlusskarte",
  "status": "zerlegt | gebaut | fertig | befund",
  "befunde": ["…"]
}
```

`hook` darf `null` sein (Einstieg bleibt). Zeiten sind Quellzeit.

## ausgabe/<stueck_id>/

```
roh.mp4            Rohschnitt 1080x1920, 30 fps, Ton normalisiert, ohne Schrift
roh_ki.mp4         optional: Rohschnitt mit einer KI-Einblendung, Ton unverändert
zeitachse.json     {"segmente": [[s,e],…] (Quellzeit), "woerter": [{"w","s","e"}] (neue Zeit), "dauer_s"}
instagram.mp4      Fassung mit Schrift-Ebene, ≤ 82 MB
tiktok.mp4         Untertitel höher (TikTok-Leiste), H.264
youtube.mp4        nur wenn ≤ 179 s
cover.jpg          1080x1920 JPEG mit Titelband
texte.json         siehe unten
stueck.json        {"id","dauer_s","dateien": {"instagram": "instagram.mp4", …}, "status", "befunde": []}
```

## texte.json

```json
{
  "instagram": {"caption": "…"},
  "tiktok": {"caption": "…"},
  "youtube": {"titel": "…", "beschreibung": "…"},
  "pinterest": {"titel": "…", "beschreibung": "…", "link": "…"},
  "threads": {"text": "…"},
  "befunde": []
}
```

## ausgabe/bilder/<bild_id>/

`bild_id` = `<take>-<art>-<nn>`, z. B. `beispiel-pin-01`.

```
bild.json   {"id","take","plattform": "instagram|pinterest|tiktok|threads",
             "art": "bild|karussell|pin|fotobeitrag|text",
             "stil": "zitat_standbild|…|spickzettel|…",
             "dateien": ["01.jpg", …], "texte": {…wie texte.json für diese Plattform…},
             "status": "fertig|befund", "befunde": []}
01.jpg …    Bilder (JPEG, sRGB)
```

Threads-Texte ohne Bild: `art: "text"`, `dateien: []`, Text in `texte.threads.text`.

## Stile

Jede Plattform hat eigene Stile. Welche an sind, steht in `konfig/stile.toml`.
`stil.tiktok` und `stil.youtube` halten den tatsächlich gebauten Stil fest. Ist
der Instagram-Stil dort nicht erlaubt, steht dort `klar`; YouTube erhält dann
eine eigene Fassung, sonst bleibt es die Kopie der Instagram-Fassung.

| Plattform | Art | Stile |
|---|---|---|
| Instagram | Reel | `klar` (Tipp-Titel + Karaoke), `titelband` (festes Band oben), `stichworte` (Stichwort-Kacheln), `einwort`, `schwarzbild` |
| Instagram | Bild 1080x1350 | `zitat_standbild`, `zahl`, `einwand`, `vorher_nachher`, `raster`, `notiz` |
| Instagram | Karussell 1080x1350 | `schritte`, `kette`, `woche_hell`, `foto`, `handschrift_liste`, `rasterposter` |
| TikTok | Video | wie Reel, eigene Untertitelhöhe |
| TikTok | Fotobeitrag 1080x1920 | `foto_schritte`, `foto_zitat` |
| YouTube | Short | wie Reel, eigener Titel, nur ≤ 179 s |

Bei `einwort` und `schwarzbild` ergänzt der Bau `bausteine` im Rezept. Die
sortierte Liste enthält nur tatsächlich gesetzte Karten sowie `wortstil_<name>`
und gegebenenfalls `zoom_punch`. `gesicht.json` im Ausgabeordner enthält die
zwischengespeicherten Gesichtszonen.
| Pinterest | Pin 1000x1500 | `spickzettel`, `szene`, `notizbuch`, `editorial`, `typomix`, `tabelle`, `toolraster`, `statistik` |
| Threads | Text | `merksatz`, `einwand`, `zahl`, `frage`, `kette`, `bild_zeile` |

## plan.json

```json
{"eintraege": [
  {"id": "p-0001", "kanal": "instagram", "art": "reel|bild|karussell|pin|fotobeitrag|text|short|video",
   "quelle": "beispiel-01", "take": "beispiel", "teil": 1, "von_teilen": 3,
   "dateien": ["ausgabe/beispiel-01/instagram.mp4"], "text": "…", "titel": "…",
   "zeit": "2026-10-21T09:40:00+02:00", "slot": 3,
   "stil": "lesereel|uebermalt|null",
   "freigegeben": false, "freigegeben_am": null,
   "status": "geplant|laeuft|veroeffentlicht|fehler", "befunde": []}
]}
```

## postlog.json

Eine Liste. **Schlüssel ist immer (kanal, plan_id).** Wer liest, filtert nach Kanal.

```json
[{"plan_id": "p-0001", "kanal": "instagram", "zeit": "…", "status": "laeuft|ok|fehler",
  "trocken": true, "weg": "upload_post", "anfrage": {…ohne Schlüssel…},
  "antwort": {…}, "extern_id": "…", "url": "…", "fehler": null}]
```

## Befehle und wer sie baut

| Modul | Befehle |
|---|---|
| `rohmaterial.py`, `transkript.py`, `zerlegen.py`, `hook.py`, `urteil.py`, `beispiel.py` | beispiel, eingang, transkript, zerlegen, hook |
| `schnitt.py`, `video.py`, `ebenen.py`, `titelband.py` | bauen, fassungen |
| `texte.py`, `stile/` | texte, bilder |
| `kurzstuecke.py` | kurzstuecke |
| `plan.py`, `posten/`, `betrieb.py` | planen, zeigen, freigeben, posten, vorrat, status, zeitplan, instagram-token, youtube-anmelden |
| `cli.py`, `pruefen.py` | pruefen, tag |
| `ki_einblendung.py`, `umbau/budget.py` | ki-budget |
| `aufnehmen.py` | aufnehmen |
